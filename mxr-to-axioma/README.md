# MXR-to-Axioma Preset Translator

Translate MXR Bass Synth (MB301) presets to Darkglass Anagram Axioma configurations.

## Overview

This tool helps bass players translate their MXR Bass Synth settings to equivalent configurations for the Darkglass Anagram's Axioma synthesizer plugin. The goal is not just to match parameter values, but to reproduce the original sound, including its response to playing dynamics.

## Features

- **Manual Preset Entry**: Enter MXR parameter values through a web interface
- **Factory Presets**: Start with one of the 8 MXR factory presets
- **Parameter Mapping**: Intelligent translation with documented approximations
- **Gap Analysis**: Clear identification of features that cannot be directly mapped
- **Configuration Export**: Generate step-by-step guides for Darkglass Suite
- **Audio Comparison**: Compare reference recordings (optional hardware required)

## Quick Start

### Installation

```bash
# Clone the repository
cd mxr-to-axioma

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Running the Application

```bash
# Start the web server
python -m src.main
```

Open http://127.0.0.1:8000 in your browser.

## Usage Workflow

1. **Import MXR**: Enter your MXR Bass Synth settings manually or select a factory preset
2. **Translate**: The tool maps parameters to Axioma equivalents
3. **Review**: Check the translation report for approximations and gaps
4. **Export**: Get a configuration guide for Darkglass Suite
5. **Optimize** (Optional): Compare audio recordings to refine the translation

## Device Compatibility

### MXR Bass Synth (MB301)

- **No digital interface** - preset extraction is manual only
- 8 user presets + live mode
- 18 parameters across 6 knobs with Voice/Shape modifiers
- Expression pedal support

### Darkglass Anagram with Axioma

- USB-C for MIDI and firmware updates
- Darkglass Suite for preset management
- Axioma plugin provides mono synth with:
  - Dual oscillators (saw/square/triangle)
  - Sub oscillator
  - Filter with envelope
  - Arpeggiator

## Parameter Mapping

### Direct Equivalents
| MXR | Axioma |
|-----|--------|
| MIX | Blend |
| SUB MIX | SUB Level |
| CUTOFF | Filter Cutoff |
| RESONANCE | Filter Resonance |

### Approximate Mappings
| MXR | Axioma | Notes |
|-----|--------|-------|
| VOICE MIX | OSC1/OSC2 balance | Different architectures |
| ENVELOPE | Env Decay | MXR combines attack/decay |
| AMP ENVELOPE | Attack | Direct time mapping |

### Known Gaps
| MXR Feature | Status |
|-------------|--------|
| Glide/Portamento | Not available in Axioma |
| LFO Modulation | Use separate Anagram block |
| Noise Generator | Not available in Axioma |

See `docs/device-capabilities.md` for complete details.

## Project Structure

```
mxr-to-axioma/
├── src/
│   ├── main.py              # Application entry point
│   ├── config.py            # Configuration
│   ├── preset_parsers/      # MXR preset handling
│   ├── device_adapters/     # Translation engine
│   ├── audio_analysis/      # Audio comparison (optional)
│   ├── optimization/        # Parameter tuning (optional)
│   └── web_ui/              # FastAPI web interface
├── tests/
│   ├── unit/
│   └── integration/
├── docs/
│   ├── architecture.md
│   └── device-capabilities.md
├── presets/
│   ├── mxr/                 # Saved MXR presets
│   └── axioma/              # Translated presets
└── requirements.txt
```

## API Reference

### Presets

```
GET  /api/presets              # List all presets
POST /api/presets/mxr          # Create MXR preset
GET  /api/presets/{id}         # Get preset details
DELETE /api/presets/{id}       # Delete preset
```

### Translation

```
POST /api/translate/{mxr_id}   # Translate MXR to Axioma
GET  /api/export/{id}/guide    # Get configuration guide
```

### Audio (requires files)

```
POST /api/audio/upload         # Upload audio file
GET  /api/audio/{id}/analysis  # Get audio analysis
POST /api/audio/compare        # Compare two files
```

## Development

### Running Tests

```bash
pytest tests/ -v
```

### Code Quality

```bash
black src/ tests/
ruff check src/ tests/
mypy src/
```

## Limitations

- **No automated preset injection**: Axioma settings must be entered manually in Darkglass Suite
- **Some MXR features have no equivalent**: Glide, noise generator, and LFO modulation cannot be directly mapped
- **Audio optimization requires hardware**: The comparison and optimization features need actual device recordings

## Contributing

1. Check `docs/device-capabilities.md` for verified device information
2. Do not invent MIDI commands or parameter formats
3. Document all approximations and assumptions
4. Add tests for new functionality

## License

MIT License - See LICENSE file for details.

## Acknowledgments

- MXR/Dunlop for the MB301 Bass Synth documentation
- Darkglass Electronics for Anagram documentation
- The bass player community for feedback and testing

---

**Disclaimer**: This is an unofficial tool. MXR and Darkglass are registered trademarks of their respective owners. This project is not affiliated with or endorsed by Jim Dunlop or Darkglass Electronics.
