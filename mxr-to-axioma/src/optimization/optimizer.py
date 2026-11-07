"""Bayesian optimization for preset parameter tuning."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional
import uuid

import numpy as np
from skopt import gp_minimize
from skopt.space import Real, Integer, Categorical

from ..device_adapters.axioma_preset import AxiomaPreset, Waveform
from ..device_adapters.mapping import get_optimization_bounds, vector_to_axioma_params
from ..audio_analysis.comparison import compute_similarity_score
from ..config import settings


@dataclass
class OptimizationConfig:
    """Configuration for optimization run."""

    max_iterations: int = 100
    convergence_threshold: float = 0.001
    initial_points: int = 10
    acquisition_function: str = "EI"
    random_state: Optional[int] = None
    optimize_waveforms: bool = True
    optimize_osc2: bool = True
    optimize_sub: bool = True


@dataclass
class OptimizationIteration:
    """Record of a single optimization iteration."""

    iteration: int
    parameters: list[float]
    similarity_score: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class OptimizationResult:
    """Result of an optimization run."""

    id: str
    status: str
    best_preset: Optional[AxiomaPreset]
    best_score: float
    iterations: int
    history: list[OptimizationIteration]
    started_at: datetime
    completed_at: Optional[datetime]
    config: OptimizationConfig

    def get_convergence_plot_data(self) -> tuple[list[int], list[float]]:
        """Get data for convergence plot."""
        iterations = [h.iteration for h in self.history]
        scores = [h.similarity_score for h in self.history]
        return iterations, scores

    def get_best_iterations(self, n: int = 5) -> list[OptimizationIteration]:
        """Get top N iterations by score."""
        sorted_history = sorted(self.history, key=lambda x: x.similarity_score, reverse=True)
        return sorted_history[:n]


class PresetOptimizer:
    """Bayesian optimizer for Axioma preset parameters."""

    def __init__(
        self,
        reference_audio: np.ndarray,
        sample_rate: int,
        initial_preset: AxiomaPreset,
        config: Optional[OptimizationConfig] = None,
    ):
        """Initialize optimizer.

        Args:
            reference_audio: Reference MXR audio samples
            sample_rate: Sample rate
            initial_preset: Starting Axioma preset
            config: Optimization configuration
        """
        self.reference_audio = reference_audio
        self.sample_rate = sample_rate
        self.initial_preset = initial_preset
        self.config = config or OptimizationConfig()

        self.history: list[OptimizationIteration] = []
        self.best_score = 0.0
        self.best_params: Optional[list[float]] = None
        self.iteration_count = 0

        self._audio_callback: Optional[Callable[[AxiomaPreset], np.ndarray]] = None

    def set_audio_callback(self, callback: Callable[[AxiomaPreset], np.ndarray]) -> None:
        """Set callback function to generate Axioma audio.

        The callback receives an AxiomaPreset and should return the audio
        samples produced by the Axioma with those settings.

        For automated testing, this would be connected to actual hardware.
        For manual testing, this raises an exception prompting user intervention.
        """
        self._audio_callback = callback

    def _get_search_space(self) -> list:
        """Build search space for optimization."""
        space = []

        if self.config.optimize_waveforms:
            space.append(Real(0.0, 1.0, name="osc1_waveform"))
        else:
            space.append(Real(0.0, 0.0, name="osc1_waveform_fixed"))

        space.append(Real(0.0, 1.0, name="osc1_level"))

        if self.config.optimize_osc2:
            if self.config.optimize_waveforms:
                space.append(Real(0.0, 1.0, name="osc2_waveform"))
            else:
                space.append(Real(0.0, 0.0, name="osc2_waveform_fixed"))
            space.append(Real(0.0, 1.0, name="osc2_level"))
            space.append(Real(0.0, 1.0, name="osc2_tune"))
            space.append(Real(0.0, 1.0, name="osc2_detune"))
        else:
            space.extend([Real(0.0, 0.0, name=f"osc2_fixed_{i}") for i in range(4)])

        if self.config.optimize_sub:
            space.append(Real(0.0, 1.0, name="sub_level"))
        else:
            space.append(Real(0.0, 0.0, name="sub_level_fixed"))

        space.extend([
            Real(0.0, 1.0, name="filter_cutoff"),
            Real(0.0, 1.0, name="filter_resonance"),
            Real(0.0, 1.0, name="filter_env_amount"),
            Real(0.0, 1.0, name="filter_env_decay"),
            Real(0.0, 1.0, name="envelope_attack"),
            Real(0.0, 1.0, name="envelope_release"),
            Real(0.0, 1.0, name="mixer_blend"),
        ])

        return space

    def _objective(self, params: list[float]) -> float:
        """Objective function for optimization (to minimize).

        Args:
            params: Parameter vector

        Returns:
            Negative similarity score (for minimization)
        """
        preset = vector_to_axioma_params(params, self.initial_preset)

        if self._audio_callback is None:
            raise RuntimeError(
                "No audio callback set. Cannot evaluate preset without Axioma audio output. "
                "Use set_audio_callback() or run in manual mode."
            )

        axioma_audio = self._audio_callback(preset)

        similarity = compute_similarity_score(
            self.reference_audio, axioma_audio, self.sample_rate
        )

        self.iteration_count += 1
        iteration_record = OptimizationIteration(
            iteration=self.iteration_count,
            parameters=list(params),
            similarity_score=similarity,
        )
        self.history.append(iteration_record)

        if similarity > self.best_score:
            self.best_score = similarity
            self.best_params = list(params)

        return -similarity

    def optimize(self) -> OptimizationResult:
        """Run optimization.

        Returns:
            OptimizationResult with best preset and history
        """
        result_id = str(uuid.uuid4())
        started_at = datetime.utcnow()

        self.history = []
        self.best_score = 0.0
        self.best_params = None
        self.iteration_count = 0

        space = self._get_search_space()

        x0 = self.initial_preset.get_parameter_vector()

        try:
            opt_result = gp_minimize(
                self._objective,
                space,
                n_calls=self.config.max_iterations,
                n_initial_points=self.config.initial_points,
                x0=x0,
                acq_func=self.config.acquisition_function,
                random_state=self.config.random_state,
            )

            best_preset = vector_to_axioma_params(opt_result.x, self.initial_preset)
            status = "completed"

        except Exception as e:
            if self.best_params is not None:
                best_preset = vector_to_axioma_params(self.best_params, self.initial_preset)
            else:
                best_preset = self.initial_preset
            status = f"error: {str(e)}"

        return OptimizationResult(
            id=result_id,
            status=status,
            best_preset=best_preset,
            best_score=self.best_score,
            iterations=self.iteration_count,
            history=self.history,
            started_at=started_at,
            completed_at=datetime.utcnow(),
            config=self.config,
        )

    def suggest_next(self) -> AxiomaPreset:
        """Suggest next preset to try in manual optimization mode.

        Returns:
            AxiomaPreset with suggested parameters
        """
        if len(self.history) == 0:
            return self.initial_preset

        space = self._get_search_space()

        from skopt import Optimizer

        opt = Optimizer(space, base_estimator="GP", acq_func=self.config.acquisition_function)

        for record in self.history:
            opt.tell(record.parameters, -record.similarity_score)

        suggested = opt.ask()

        return vector_to_axioma_params(suggested, self.initial_preset)

    def record_result(self, preset: AxiomaPreset, axioma_audio: np.ndarray) -> float:
        """Record result of manual testing.

        Args:
            preset: Preset that was tested
            axioma_audio: Audio output from Axioma

        Returns:
            Similarity score
        """
        similarity = compute_similarity_score(
            self.reference_audio, axioma_audio, self.sample_rate
        )

        self.iteration_count += 1
        params = preset.get_parameter_vector()

        iteration_record = OptimizationIteration(
            iteration=self.iteration_count,
            parameters=params,
            similarity_score=similarity,
        )
        self.history.append(iteration_record)

        if similarity > self.best_score:
            self.best_score = similarity
            self.best_params = params

        return similarity

    def get_current_best(self) -> tuple[Optional[AxiomaPreset], float]:
        """Get current best preset and score.

        Returns:
            Tuple of (best preset or None, best score)
        """
        if self.best_params is None:
            return None, 0.0

        best_preset = vector_to_axioma_params(self.best_params, self.initial_preset)
        return best_preset, self.best_score


def create_grid_search_presets(
    base_preset: AxiomaPreset,
    param_name: str,
    values: list[float],
) -> list[AxiomaPreset]:
    """Create presets for grid search over a single parameter.

    Args:
        base_preset: Base preset to modify
        param_name: Parameter path (e.g., "filter.cutoff")
        values: Values to try

    Returns:
        List of presets with varied parameter
    """
    from ..device_adapters.mapping import apply_parameter_adjustment

    presets = []
    for value in values:
        preset = apply_parameter_adjustment(base_preset, param_name, value)
        presets.append(preset)

    return presets
