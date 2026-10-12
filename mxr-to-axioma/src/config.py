"""Application configuration."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    app_name: str = "MXR-to-Axioma Translator"
    debug: bool = False
    host: str = "127.0.0.1"
    port: int = 8000

    database_path: Path = Path("data/presets.db")
    uploads_path: Path = Path("uploads")
    presets_path: Path = Path("presets")

    max_upload_size_mb: int = 100
    supported_audio_formats: list[str] = [".wav", ".flac", ".aiff", ".mp3", ".ogg"]

    default_sample_rate: int = 48000
    analysis_fft_size: int = 4096
    analysis_hop_size: int = 1024

    optimization_max_iterations: int = 100
    optimization_convergence_threshold: float = 0.001

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    class Config:
        env_prefix = "MXR_AXIOMA_"
        env_file = ".env"


settings = Settings()


def ensure_directories() -> None:
    """Create required directories if they don't exist."""
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    settings.uploads_path.mkdir(parents=True, exist_ok=True)
    settings.presets_path.mkdir(parents=True, exist_ok=True)
    (settings.presets_path / "mxr").mkdir(exist_ok=True)
    (settings.presets_path / "axioma").mkdir(exist_ok=True)
