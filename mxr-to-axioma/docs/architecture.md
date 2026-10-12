# MXR-to-Axioma Preset Translator Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MXR-to-Axioma Translator                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │   Preset    │───▶│  Analysis   │───▶│ Translation │───▶│   Export    │  │
│  │ Acquisition │    │   Engine    │    │   Engine    │    │   Engine    │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│         │                 │                  │                  │          │
│         ▼                 ▼                  ▼                  ▼          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        Data Layer (JSON Schemas)                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                 │                  │                  │          │
│         ▼                 ▼                  ▼                  ▼          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Web UI (FastAPI + HTML/JS)                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Component Architecture

### 1. Preset Acquisition Module (`src/preset_parsers/`)

Responsible for capturing MXR preset data through multiple methods:

```
preset_parsers/
├── __init__.py
├── base.py              # Abstract base classes
├── mxr_manual.py        # Manual parameter entry
├── mxr_factory.py       # Factory preset library
├── mxr_audio.py         # Audio-based reconstruction
└── schemas/
    └── mxr_preset.py    # MXR preset JSON schema
```

#### MXR Preset Schema
```python
{
    "version": "1.0",
    "device": "MXR_MB301",
    "name": str,
    "created_at": datetime,
    "parameters": {
        "primary": {
            "mix": float,           # 0.0-1.0
            "sub_mix": float,       # 0.0-1.0
            "cutoff": float,        # 0.0-1.0
            "resonance": float,     # 0.0-1.0
            "envelope": float,      # 0.0-1.0
            "mod": float            # 0.0-1.0
        },
        "voice": {
            "voice_mix": float,
            "noise_mix": float,
            "filter_env_amount": float,  # -1.0 to 1.0
            "glide": float,
            "amp_envelope": float,
            "mod_blend": float
        },
        "shape": {
            "compression": float,
            "output_gain": float,   # -18 to +18 dB
            "gate_sensitivity": float,
            "tracking": str,        # "5string"|"4string"|"guitar"
            "dry_thru_fx": bool,
            "output_mode": str      # "mono"|"wet_dry"|"stereo"
        },
        "switches": {
            "voice_waveform": str,  # "triangle"|"sawtooth"|"square"
            "shape_waveform": str
        }
    },
    "expression": {
        "heel": {...},  # Parameter snapshot at heel
        "toe": {...}    # Parameter snapshot at toe
    },
    "metadata": {
        "source": str,  # "manual"|"audio"|"factory"
        "confidence": float,
        "notes": str
    }
}
```

### 2. Audio Analysis Module (`src/audio_analysis/`)

DSP pipeline for analyzing reference recordings:

```
audio_analysis/
├── __init__.py
├── loader.py            # Audio file I/O
├── alignment.py         # Time alignment utilities
├── spectral.py          # FFT and spectral analysis
├── envelope.py          # Amplitude envelope extraction
├── pitch.py             # Pitch detection and tracking
├── filter.py            # Filter characteristic estimation
├── dynamics.py          # Dynamic response analysis
├── features.py          # Feature extraction pipeline
└── comparison.py        # A/B comparison engine
```

#### Feature Extraction Pipeline
```
Audio Input ──▶ [Alignment] ──▶ [Windowing] ──▶ [FFT] ──▶ [Feature Extraction]
                                                              │
                    ┌────────────────────────────────────────┘
                    ▼
              ┌───────────┐
              │ Features  │
              ├───────────┤
              │ - RMS     │
              │ - Spectrum│
              │ - MFCC    │
              │ - Centroid│
              │ - Envelope│
              │ - Dynamics│
              └───────────┘
```

### 3. Translation Engine (`src/device_adapters/`)

Maps MXR parameters to Axioma equivalents:

```
device_adapters/
├── __init__.py
├── base.py              # Abstract device adapter
├── mxr_adapter.py       # MXR MB301 adapter
├── axioma_adapter.py    # Darkglass Axioma adapter
├── mapping.py           # Parameter mapping rules
└── schemas/
    └── axioma_preset.py # Axioma preset JSON schema
```

#### Axioma Preset Schema
```python
{
    "version": "1.0",
    "device": "DARKGLASS_AXIOMA",
    "name": str,
    "created_at": datetime,
    "parameters": {
        "oscillators": {
            "osc1_waveform": str,   # "saw"|"square"|"triangle"
            "osc1_level": float,    # 0.0-1.0
            "osc2_waveform": str,
            "osc2_level": float,
            "osc2_tune": int,       # -24 to +24 semitones
            "osc2_detune": float,   # -100 to +100 cents
            "sub_level": float      # 0.0-1.0
        },
        "filter": {
            "cutoff": float,        # 0.0-1.0
            "resonance": float,     # 0.0-1.0
            "env_amount": float,    # 0.0-1.0
            "env_decay": float      # 0.0-1.0
        },
        "envelope": {
            "attack": float,        # 0.0-1.0
            "release": float        # 0.0-1.0
        },
        "mixer": {
            "blend": float          # 0.0-1.0 (dry/synth)
        },
        "arpeggiator": {
            "enabled": bool,
            "direction": str,
            "chord_type": str,
            "octaves": int,
            "tempo": float
        }
    },
    "instrument_mode": str,  # "4string"|"5string"|"extended"|"guitar"|"baritone"
    "translation": {
        "source_preset": str,        # Reference to MXR preset
        "mapping_version": str,
        "approximations": [...],     # List of approximated params
        "gaps": [...],               # List of unmappable features
        "additional_blocks": [...]   # Suggested companion effects
    }
}
```

### 4. Optimization Module (`src/optimization/`)

Iterative refinement through audio comparison:

```
optimization/
├── __init__.py
├── objective.py         # Similarity scoring functions
├── search.py            # Optimization algorithms
├── bayesian.py          # Bayesian optimization
├── constraints.py       # Parameter constraints
└── history.py           # Optimization run tracking
```

#### Optimization Flow
```
┌─────────────────────────────────────────────────────────────────┐
│                    Optimization Loop                            │
│                                                                 │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐     │
│  │Generate │───▶│ Apply   │───▶│ Record  │───▶│ Compare │     │
│  │Candidate│    │Settings │    │ Output  │    │ Audio   │     │
│  └─────────┘    └─────────┘    └─────────┘    └─────────┘     │
│       ▲                                            │           │
│       │         ┌─────────┐                        │           │
│       └─────────│ Update  │◀───────────────────────┘           │
│                 │ Model   │                                    │
│                 └─────────┘                                    │
└─────────────────────────────────────────────────────────────────┘
```

### 5. Web UI Module (`src/web_ui/`)

Local web interface for user interaction:

```
web_ui/
├── __init__.py
├── app.py               # FastAPI application
├── routes/
│   ├── presets.py       # Preset CRUD endpoints
│   ├── analysis.py      # Audio analysis endpoints
│   ├── translation.py   # Translation endpoints
│   ├── optimization.py  # Optimization endpoints
│   └── export.py        # Export endpoints
├── static/
│   ├── css/
│   ├── js/
│   └── images/
└── templates/
    ├── base.html
    ├── dashboard.html
    ├── mxr_input.html
    ├── analysis.html
    ├── translation.html
    ├── optimization.html
    └── export.html
```

## Data Flow

### 1. Manual Preset Entry
```
User Input ──▶ Web Form ──▶ Validation ──▶ MXR Preset JSON ──▶ Database
```

### 2. Audio Analysis Flow
```
Audio Files ──▶ Loader ──▶ Preprocessor ──▶ Feature Extractor ──▶ Analysis Report
     │                                                               │
     └── DI Reference                                                │
     └── MXR Output                                                  │
     └── Axioma Output ◀─────────────────────────────────────────────┘
                              (during optimization)
```

### 3. Translation Flow
```
MXR Preset ──▶ Normalizer ──▶ Mapper ──▶ Axioma Params ──▶ Validator ──▶ Axioma Preset
                                │
                                ├── Direct mappings
                                ├── Scaled/transformed mappings
                                └── Gap annotations
```

### 4. Optimization Flow
```
Initial Axioma Preset ──▶ Optimizer ──▶ Candidates ──┐
         ▲                                           │
         │                                           ▼
         │                                    [Apply to device]
         │                                           │
         │                                           ▼
         │                                    [Record audio]
         │                                           │
         │                                           ▼
         └──────────── Score ◀──────────── [Compare with MXR ref]
```

## Database Schema

Using SQLite for local storage:

```sql
-- Presets table
CREATE TABLE presets (
    id TEXT PRIMARY KEY,
    device TEXT NOT NULL,  -- 'mxr' or 'axioma'
    name TEXT NOT NULL,
    data JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Audio files table
CREATE TABLE audio_files (
    id TEXT PRIMARY KEY,
    preset_id TEXT,
    file_type TEXT NOT NULL,  -- 'di', 'mxr_ref', 'axioma_output'
    file_path TEXT NOT NULL,
    duration_ms INTEGER,
    sample_rate INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (preset_id) REFERENCES presets(id)
);

-- Translations table
CREATE TABLE translations (
    id TEXT PRIMARY KEY,
    source_preset_id TEXT NOT NULL,
    target_preset_id TEXT NOT NULL,
    mapping_version TEXT NOT NULL,
    similarity_score REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_preset_id) REFERENCES presets(id),
    FOREIGN KEY (target_preset_id) REFERENCES presets(id)
);

-- Optimization runs table
CREATE TABLE optimization_runs (
    id TEXT PRIMARY KEY,
    translation_id TEXT NOT NULL,
    status TEXT NOT NULL,  -- 'running', 'completed', 'failed'
    iterations INTEGER DEFAULT 0,
    best_score REAL,
    config JSON,
    results JSON,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (translation_id) REFERENCES translations(id)
);
```

## API Endpoints

### Presets
- `GET /api/presets` - List all presets
- `GET /api/presets/{id}` - Get preset details
- `POST /api/presets/mxr` - Create MXR preset
- `POST /api/presets/axioma` - Create Axioma preset
- `PUT /api/presets/{id}` - Update preset
- `DELETE /api/presets/{id}` - Delete preset

### Audio
- `POST /api/audio/upload` - Upload audio file
- `GET /api/audio/{id}/analysis` - Get audio analysis
- `POST /api/audio/compare` - Compare two audio files

### Translation
- `POST /api/translate` - Translate MXR to Axioma
- `GET /api/translate/{id}` - Get translation details
- `GET /api/translate/{id}/report` - Get translation report

### Optimization
- `POST /api/optimize` - Start optimization run
- `GET /api/optimize/{id}` - Get optimization status
- `POST /api/optimize/{id}/stop` - Stop optimization
- `GET /api/optimize/{id}/history` - Get optimization history

### Export
- `GET /api/export/{id}/guide` - Get configuration guide
- `GET /api/export/{id}/midi` - Get MIDI CC sequence
- `GET /api/export/{id}/json` - Export as JSON

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.9+, FastAPI |
| Audio DSP | NumPy, SciPy, librosa, soundfile |
| Optimization | scikit-optimize, Optuna |
| Database | SQLite |
| Frontend | HTML5, CSS3, Vanilla JS |
| Charts | Chart.js, Plotly.js |
| Audio Visualization | wavesurfer.js |

## Directory Structure

```
mxr-to-axioma/
├── src/
│   ├── __init__.py
│   ├── main.py              # Application entry point
│   ├── config.py            # Configuration management
│   ├── database.py          # Database setup
│   ├── device_adapters/
│   ├── preset_parsers/
│   ├── audio_analysis/
│   ├── optimization/
│   ├── web_ui/
│   └── utils/
│       ├── __init__.py
│       ├── logging.py
│       └── validation.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── docs/
│   ├── architecture.md
│   ├── device-capabilities.md
│   └── api.md
├── presets/
│   ├── mxr/                 # MXR preset library
│   └── axioma/              # Translated presets
├── data/                    # SQLite database
├── uploads/                 # Uploaded audio files
├── requirements.txt
├── pyproject.toml
└── README.md
```

## Extensibility

The architecture supports future extensions:

### Adding New Source Devices
1. Create device adapter in `device_adapters/`
2. Create preset parser in `preset_parsers/`
3. Define JSON schema for preset format
4. Add mapping rules to translation engine

### Adding New Target Devices
1. Create device adapter in `device_adapters/`
2. Define JSON schema for preset format
3. Add mapping rules from all supported source devices
4. Implement export format (if native export supported)

### Plugin Architecture (Future)
```python
class DevicePlugin:
    @abstractmethod
    def get_preset_schema(self) -> dict: ...
    
    @abstractmethod
    def parse_preset(self, data: bytes) -> Preset: ...
    
    @abstractmethod
    def export_preset(self, preset: Preset) -> bytes: ...
    
    @abstractmethod
    def get_mapping_rules(self, target: str) -> list: ...
```
