"""FastAPI web application for MXR-to-Axioma translator."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import aiofiles

from ..config import settings, ensure_directories
from ..preset_parsers.mxr_preset import (
    MXRPreset,
    MXRPrimaryParams,
    MXRVoiceParams,
    MXRShapeParams,
    MXRSwitchStates,
    MXRPresetMetadata,
    VoiceWaveform,
    TrackingMode,
    OutputMode,
    PresetSource,
)
from ..preset_parsers.mxr_factory import get_factory_preset, list_factory_presets
from ..device_adapters.mapping import translate_mxr_to_axioma
from ..device_adapters.axioma_preset import AxiomaPreset
from ..audio_analysis.loader import load_audio
from ..audio_analysis.features import extract_features
from ..audio_analysis.comparison import compare_audio


BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"


class MXRPresetInput(BaseModel):
    """Input model for creating MXR preset."""

    name: str
    mix: float = 0.5
    sub_mix: float = 0.5
    cutoff: float = 0.5
    resonance: float = 0.0
    envelope: float = 0.5
    mod: float = 0.0
    voice_mix: float = 0.5
    noise_mix: float = 0.0
    filter_env_amount: float = 0.5
    glide: float = 0.0
    amp_envelope: float = 0.0
    mod_blend: float = 0.5
    compression: float = 0.0
    output_gain: float = 0.0
    gate_sensitivity: float = 0.5
    tracking: str = "5string"
    dry_thru_fx: bool = False
    output_mode: str = "mono"
    voice_waveform: str = "sawtooth"
    notes: str = ""


presets_db: dict[str, dict] = {}
audio_files_db: dict[str, dict] = {}
translations_db: dict[str, dict] = {}


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    ensure_directories()

    app = FastAPI(
        title=settings.app_name,
        description="Translate MXR Bass Synth presets to Darkglass Axioma",
        version="0.1.0",
    )

    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        """Render main dashboard."""
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "title": settings.app_name,
                "presets": list(presets_db.values()),
                "translations": list(translations_db.values()),
            },
        )

    @app.get("/mxr/new", response_class=HTMLResponse)
    async def mxr_input_form(request: Request):
        """Render MXR preset input form."""
        return templates.TemplateResponse(
            request,
            "mxr_input.html",
            {
                "title": "Create MXR Preset",
                "factory_presets": list_factory_presets(),
            },
        )

    @app.get("/api/factory-presets")
    async def get_factory_presets():
        """List available factory presets."""
        return {"presets": list_factory_presets()}

    @app.get("/api/factory-presets/{name}")
    async def get_factory_preset_details(name: str):
        """Get factory preset details."""
        preset = get_factory_preset(name)
        if not preset:
            raise HTTPException(status_code=404, detail=f"Factory preset '{name}' not found")
        return preset.model_dump()

    @app.post("/api/presets/mxr")
    async def create_mxr_preset(data: MXRPresetInput):
        """Create a new MXR preset from manual input."""
        preset_id = str(uuid.uuid4())

        preset = MXRPreset(
            id=preset_id,
            name=data.name,
            primary=MXRPrimaryParams(
                mix=data.mix,
                sub_mix=data.sub_mix,
                cutoff=data.cutoff,
                resonance=data.resonance,
                envelope=data.envelope,
                mod=data.mod,
            ),
            voice=MXRVoiceParams(
                voice_mix=data.voice_mix,
                noise_mix=data.noise_mix,
                filter_env_amount=data.filter_env_amount,
                glide=data.glide,
                amp_envelope=data.amp_envelope,
                mod_blend=data.mod_blend,
            ),
            shape=MXRShapeParams(
                compression=data.compression,
                output_gain=data.output_gain,
                gate_sensitivity=data.gate_sensitivity,
                tracking=TrackingMode(data.tracking),
                dry_thru_fx=data.dry_thru_fx,
                output_mode=OutputMode(data.output_mode),
            ),
            switches=MXRSwitchStates(
                voice_waveform=VoiceWaveform(data.voice_waveform),
            ),
            metadata=MXRPresetMetadata(
                source=PresetSource.MANUAL,
                notes=data.notes,
            ),
        )

        presets_db[preset_id] = {
            "id": preset_id,
            "device": "mxr",
            "name": preset.name,
            "data": preset.model_dump(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        return {"id": preset_id, "preset": preset.model_dump()}

    @app.post("/api/presets/mxr/factory/{name}")
    async def create_from_factory(name: str):
        """Create preset from factory preset."""
        preset = get_factory_preset(name)
        if not preset:
            raise HTTPException(status_code=404, detail=f"Factory preset '{name}' not found")

        presets_db[preset.id] = {
            "id": preset.id,
            "device": "mxr",
            "name": preset.name,
            "data": preset.model_dump(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        return {"id": preset.id, "preset": preset.model_dump()}

    @app.get("/api/presets")
    async def list_presets(device: Optional[str] = None):
        """List all presets, optionally filtered by device."""
        presets = list(presets_db.values())
        if device:
            presets = [p for p in presets if p["device"] == device]
        return {"presets": presets}

    @app.get("/api/presets/{preset_id}")
    async def get_preset(preset_id: str):
        """Get preset by ID."""
        if preset_id not in presets_db:
            raise HTTPException(status_code=404, detail="Preset not found")
        return presets_db[preset_id]

    @app.delete("/api/presets/{preset_id}")
    async def delete_preset(preset_id: str):
        """Delete a preset."""
        if preset_id not in presets_db:
            raise HTTPException(status_code=404, detail="Preset not found")
        del presets_db[preset_id]
        return {"status": "deleted"}

    @app.post("/api/translate/{mxr_preset_id}")
    async def translate_preset(mxr_preset_id: str):
        """Translate MXR preset to Axioma."""
        if mxr_preset_id not in presets_db:
            raise HTTPException(status_code=404, detail="MXR preset not found")

        preset_record = presets_db[mxr_preset_id]
        if preset_record["device"] != "mxr":
            raise HTTPException(status_code=400, detail="Not an MXR preset")

        mxr_preset = MXRPreset(**preset_record["data"])

        axioma_preset = translate_mxr_to_axioma(mxr_preset)

        presets_db[axioma_preset.id] = {
            "id": axioma_preset.id,
            "device": "axioma",
            "name": axioma_preset.name,
            "data": axioma_preset.model_dump(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        translation_id = str(uuid.uuid4())
        translations_db[translation_id] = {
            "id": translation_id,
            "source_id": mxr_preset_id,
            "target_id": axioma_preset.id,
            "source_name": mxr_preset.name,
            "target_name": axioma_preset.name,
            "confidence": axioma_preset.translation.overall_confidence if axioma_preset.translation else 1.0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        return {
            "translation_id": translation_id,
            "axioma_preset": axioma_preset.model_dump(),
        }

    @app.get("/api/translations/{translation_id}")
    async def get_translation(translation_id: str):
        """Get translation details."""
        if translation_id not in translations_db:
            raise HTTPException(status_code=404, detail="Translation not found")
        return translations_db[translation_id]

    @app.get("/api/export/{preset_id}/guide")
    async def export_configuration_guide(preset_id: str):
        """Export Axioma preset as configuration guide."""
        if preset_id not in presets_db:
            raise HTTPException(status_code=404, detail="Preset not found")

        preset_record = presets_db[preset_id]
        if preset_record["device"] != "axioma":
            raise HTTPException(status_code=400, detail="Not an Axioma preset")

        axioma_preset = AxiomaPreset(**preset_record["data"])
        guide = axioma_preset.to_configuration_guide()

        return {
            "preset_name": axioma_preset.name,
            "guide": guide,
        }

    @app.post("/api/audio/upload")
    async def upload_audio(
        file: UploadFile = File(...),
        preset_id: Optional[str] = Form(None),
        file_type: str = Form("reference"),
    ):
        """Upload audio file."""
        suffix = Path(file.filename).suffix.lower()
        if suffix not in settings.supported_audio_formats:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported format. Supported: {settings.supported_audio_formats}",
            )

        file_id = str(uuid.uuid4())
        file_path = settings.uploads_path / f"{file_id}{suffix}"

        async with aiofiles.open(file_path, "wb") as f:
            content = await file.read()
            await f.write(content)

        audio = load_audio(file_path)

        audio_files_db[file_id] = {
            "id": file_id,
            "preset_id": preset_id,
            "file_type": file_type,
            "original_name": file.filename,
            "file_path": str(file_path),
            "duration_seconds": audio.duration_seconds,
            "sample_rate": audio.sample_rate,
            "channels": audio.channels,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        return audio_files_db[file_id]

    @app.get("/api/audio/{file_id}/analysis")
    async def get_audio_analysis(file_id: str):
        """Get audio analysis for uploaded file."""
        if file_id not in audio_files_db:
            raise HTTPException(status_code=404, detail="Audio file not found")

        audio_record = audio_files_db[file_id]
        audio = load_audio(audio_record["file_path"])
        features = extract_features(audio.samples, audio.sample_rate)

        return {
            "file_id": file_id,
            "duration_seconds": audio.duration_seconds,
            "sample_rate": audio.sample_rate,
            "features": features.get_summary(),
        }

    @app.post("/api/audio/compare")
    async def compare_audio_files(reference_id: str, target_id: str):
        """Compare two audio files."""
        if reference_id not in audio_files_db:
            raise HTTPException(status_code=404, detail="Reference audio not found")
        if target_id not in audio_files_db:
            raise HTTPException(status_code=404, detail="Target audio not found")

        ref_audio = load_audio(audio_files_db[reference_id]["file_path"])
        tgt_audio = load_audio(audio_files_db[target_id]["file_path"])

        if ref_audio.sample_rate != tgt_audio.sample_rate:
            tgt_audio = load_audio(
                audio_files_db[target_id]["file_path"],
                target_sr=ref_audio.sample_rate,
            )

        comparison = compare_audio(
            ref_audio.samples, tgt_audio.samples, ref_audio.sample_rate
        )

        return {
            "reference_id": reference_id,
            "target_id": target_id,
            "overall_similarity": comparison.overall_similarity,
            "spectral_similarity": comparison.spectral_similarity,
            "envelope_similarity": comparison.envelope_similarity,
            "harmonic_similarity": comparison.harmonic_similarity,
            "transient_similarity": comparison.transient_similarity,
            "timbral_similarity": comparison.timbral_similarity,
            "dynamic_similarity": comparison.dynamic_similarity,
            "summary": comparison.get_summary(),
        }

    @app.get("/translate/{mxr_preset_id}", response_class=HTMLResponse)
    async def translation_page(request: Request, mxr_preset_id: str):
        """Render translation result page."""
        if mxr_preset_id not in presets_db:
            raise HTTPException(status_code=404, detail="Preset not found")

        return templates.TemplateResponse(
            request,
            "translation.html",
            {
                "title": "Translation Result",
                "mxr_preset_id": mxr_preset_id,
            },
        )

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "version": "0.1.0",
            "presets_count": len(presets_db),
            "translations_count": len(translations_db),
        }

    return app
