# Device Capabilities Research

This document summarizes verified capabilities of the MXR Bass Synth (MB301) and Darkglass Anagram/Axioma, distinguishing confirmed features from assumptions.

## MXR Bass Synth (MB301)

### Overview
The MXR MB301 Bass Synth is a digital bass synthesizer pedal designed by Jim Dunlop with tone consultant Ian Martin Allison. It provides monophonic synth tones with sub-octave, envelope filter, and modulation effects.

### Digital Interface Capabilities

| Capability | Status | Source |
|-----------|--------|--------|
| USB connectivity | **NOT SUPPORTED** | Manual review |
| MIDI In/Out | **NOT SUPPORTED** | Manual review |
| SysEx protocol | **NOT SUPPORTED** | Manual review |
| Editor/Librarian software | **NOT AVAILABLE** | Official website |
| Digital preset extraction | **NOT POSSIBLE** | Device analysis |

**Conclusion:** The MXR MB301 has no digital interface for preset extraction. All preset acquisition must be done manually or via audio analysis.

### Preset System
- **8 user presets** (4 green, 4 red) plus live mode
- Presets store all parameter states including expression pedal mappings
- Preset scrolling via onboard button, external switch, or footswitch
- Factory presets can be reset individually or globally

### Parameter Architecture

The MB301 has **18 parameters** across 6 physical knobs, accessed through three layers:

#### Primary Parameters (Direct Knob Control)
| Parameter | Range | Description |
|-----------|-------|-------------|
| MIX | 0-100% | Dry/synth signal blend |
| SUB MIX | 0-100% | Main oscillator to sub oscillator ratio |
| CUTOFF | 20Hz-20kHz (estimated) | 4-pole low-pass filter cutoff frequency |
| RESONANCE | 0-100% | Filter resonance/Q |
| ENVELOPE | 0-100% | Filter envelope attack/decay time |
| MOD | 0-100% | Modulation depth (chorus/filter LFO) |

#### VOICE Parameters (Hold VOICE + Turn Knob)
| Parameter | Range | Description |
|-----------|-------|-------------|
| VOICE MIX | 0-100% | Main oscillator vs added harmonics |
| NOISE MIX | 0-100% | Oscillator to noise generator ratio |
| FILTER ENV AMOUNT | -100 to +100% | Filter envelope direction and depth |
| GLIDE | 0-100% | Portamento time between notes |
| AMP ENVELOPE | 0-100% | Note attack/fade-in time |
| MOD BLEND | 0-100% | Chorus vs filter LFO balance |

#### SHAPE Parameters (Hold SHAPE + Turn Knob)
| Parameter | Range | Notes |
|-----------|-------|-------|
| COMPRESSION | 0-100% | Dynamics control |
| OUTPUT GAIN | ±18dB | Output level adjustment |
| GATE SENSITIVITY | 0-100% | **GLOBAL** - Note trigger threshold |
| TRACKING | 3 positions | **GLOBAL** - 5-string/4-string/Guitar |
| DRY THRU FX | On/Off | Process dry signal through effects |
| OUTPUT MODE | Mono/Wet-Dry/Stereo | **GLOBAL** - Output routing |

#### Switch States
| Control | States |
|---------|--------|
| VOICE button | Triangle / Sawtooth / Square oscillator |
| SHAPE button | Shape selection (waveform modifier) |
| Bypass | On/Off |

### Expression Pedal
- Can control any VOICE parameter
- Heel/toe positions stored per preset
- Connected via CTR jack with TRS cable

### Audio Specifications
| Specification | Value |
|--------------|-------|
| Input Impedance | 1MΩ |
| Output Impedance | 100Ω |
| Maximum Input Level | +5 dBV |
| Noise Floor | -97 dBV |
| Current Draw | 330 mA |
| Power Supply | 9V DC center-negative |

### Factory Preset Reference
| Preset | Name | Sonic Character |
|--------|------|-----------------|
| Green 1 | THRILLENGANES | Michael Jackson "Thriller" - octave-down |
| Green 2 | WONDERFUL | Stevie Wonder TONTO - short funky resonant |
| Green 3 | LIZARD SYNTH | Herbie Hancock "Chameleon" - resonant funk |
| Green 4 | SYNTHADELIC | Parliament "Flashlight" - wide octave-down |
| Red 1 | SLEDGE | Peter Gabriel "Sledgehammer" - analog octave + chorus |
| Red 2 | ARMY OF SYNTH | Björk "Army of Me" - expression pedal |
| Red 3 | NINE INCH SYNTH | NIN "Head Like a Hole" - aggressive |
| Red 4 | SYNTHMAU5 | EDM sidechain - rhythmic pumping |

---

## Darkglass Anagram with Axioma

### Overview
The Darkglass Anagram is a multi-effect processor running KosmOS, featuring DSP blocks including the Axioma monophonic synthesizer plugin (introduced in v1.18.0).

### Digital Interface Capabilities

| Capability | Status | Source |
|-----------|--------|--------|
| USB-C connectivity | **SUPPORTED** | Manual, hardware |
| USB Audio Class 2.0 | **SUPPORTED** | 12 channels (3in/9out) @ 48kHz |
| USB MIDI | **SUPPORTED** | Manual confirmed |
| MIDI In/Out (3.5mm TRS-A) | **SUPPORTED** | Hardware ports |
| Darkglass Suite software | **SUPPORTED** | Official download |
| Preset backup/restore | **SUPPORTED** | Suite 6.8.0+ |
| Native preset file format | **UNDOCUMENTED** | No public spec |
| Direct parameter injection | **LIMITED** | Via MIDI CC only |

### Preset System
- **126 user presets** organized in 42 banks of 3 (01A-42C)
- Factory presets can be copied to user area
- Presets contain: signal chain, block settings, scenes, bindings, metadata
- Scenes: up to 3 variations per preset (A, B, C)
- MIDI Program Change for preset recall (PC 1-126)

### MIDI Implementation

#### System Control
| Function | Type | CC/PC | Values |
|----------|------|-------|--------|
| Bank Select | CC | 102 | 1-42 |
| Preset Select | PC | - | 1-126 |
| Preset Increment | CC | 105 | 1-127 |
| Preset Decrement | CC | 106 | 1-127 |
| Scene Select | CC | 107 | 1-126, 127=default |
| Mode Select | CC | 85 | 1=Preset, 2=Stomp, 3=Scene |

#### Parameter Bindings (Default CCs)
| Binding | CC | Notes |
|---------|-----|-------|
| Stomp Foot A | 17 | Editable |
| Stomp Foot B | 18 | Editable |
| Stomp Foot C | 19 | Editable |
| Knob 1 | 20 | Editable |
| Knob 2 | 21 | Editable |
| Knob 3 | 22 | Editable |
| Knob 4 | 23 | Editable |
| Knob 5 | 24 | Editable |
| Knob 6 | 25 | Editable |
| Expression | 89 | Editable |

**Reserved CCs (unavailable for custom bindings):** 0, 7, 14-32, 85-87, 89, 102-119

### Axioma Synthesizer Block

#### Oscillator Section
| Parameter | Range | Description |
|-----------|-------|-------------|
| OSC 1 Waveform | Saw/Square/Triangle | Primary oscillator shape |
| OSC 1 Level | 0-100% | Oscillator 1 volume |
| OSC 2 Waveform | Saw/Square/Triangle | Secondary oscillator shape |
| OSC 2 Level | 0-100% | Oscillator 2 volume |
| OSC 2 Tune | ±24 semitones (est.) | Coarse pitch offset |
| OSC 2 Detune | ±100 cents | Fine pitch offset |
| SUB Level | 0-100% | Sub oscillator volume (1 octave down) |
| Blend | 0-100% | Dry bass to synth mix |

#### Filter Section
| Parameter | Range | Description |
|-----------|-------|-------------|
| Cutoff | 20Hz-20kHz (est.) | Filter cutoff frequency |
| Resonance | 0-100% | Filter Q/resonance |
| Env Amount | 0-100% | Filter envelope modulation depth |
| Env Decay | 0-10s (est.) | Envelope decay time |

#### Envelope Section
| Parameter | Range | Description |
|-----------|-------|-------------|
| Attack | 0-10s (est.) | Amplitude envelope attack |
| Release | 0-10s (est.) | Amplitude envelope release |

#### Arpeggiator
| Parameter | Options |
|-----------|---------|
| Direction | Up, Down, Up-Down, Random |
| Chord Type | Major, Minor, Maj7, Min7, MinMaj7 |
| Octaves | 1, 2, 3 |
| Tempo | Variable BPM |
| Note Division | 16th notes |

#### Instrument Modes
| Mode | Tracking Range |
|------|---------------|
| 4-String Bass | Low E to high G |
| 5-String Bass | Low B to high C |
| Extended Range | Full low B to high C (24-fret 6-string) |
| Guitar | Standard 24-fret guitar range |
| Baritone | Extended low range |

### Darkglass Suite Integration
- Firmware updates (KosmOS)
- Preset backup and restore (Suite 6.8.0+)
- Asset transfer (NAM models, IRs)
- Bank management and preset organization
- Cloud backup/sync to Darkglass account

### Technical Specifications
| Specification | Value |
|--------------|-------|
| Input Impedance | 1MΩ |
| Max Input Level | +12 dBu |
| Output Impedance | 100Ω |
| Base Latency | 1.31 ms |
| Latency w/ FX Loop | 2.62 ms |
| USB Sample Rate | 48 kHz (fixed) |
| Dimensions | 210×105×62 mm |
| Weight | 815g |

---

## Parameter Mapping Matrix

### Direct Equivalents
| MXR Parameter | Axioma Parameter | Confidence |
|--------------|------------------|------------|
| MIX | Blend | HIGH - same function |
| SUB MIX | SUB Level | HIGH - same function |
| CUTOFF | Cutoff | HIGH - same function |
| RESONANCE | Resonance | HIGH - same function |
| ENVELOPE | Env Decay | MEDIUM - similar function |
| AMP ENVELOPE | Attack | MEDIUM - related function |

### Approximate Equivalents (Require Translation)
| MXR Parameter | Axioma Mapping | Notes |
|--------------|----------------|-------|
| VOICE button (waveforms) | OSC 1 + OSC 2 Waveforms | MXR has 3; Axioma has 3×2 |
| VOICE MIX | OSC 1/OSC 2 Level balance | Different architecture |
| FILTER ENV AMOUNT | Env Amount | Range/polarity may differ |
| GLIDE | Not available | **GAP** - Axioma lacks glide |
| MOD | Not available | **GAP** - Axioma lacks LFO mod |
| MOD BLEND | Not available | **GAP** - No chorus/LFO blend |
| NOISE MIX | Not available | **GAP** - Axioma lacks noise |

### Features Without Equivalent
| MXR Feature | Status |
|-------------|--------|
| Noise generator | **NOT AVAILABLE** in Axioma |
| LFO modulation (chorus/filter) | **NOT AVAILABLE** in Axioma |
| Glide/Portamento | **NOT AVAILABLE** in Axioma |
| Compression | Available via separate Anagram block |
| Gate sensitivity | Axioma has instrument modes instead |

| Axioma Feature | Status |
|----------------|--------|
| Arpeggiator | **NOT AVAILABLE** in MXR |
| Dual oscillators | MXR has VOICE for harmonics |
| OSC 2 tuning/detune | **NOT AVAILABLE** in MXR |
| Scenes | **NOT AVAILABLE** in MXR |

---

## Preset Acquisition Strategy

Given the MXR's lack of digital interface, preset acquisition must use one of:

### Method A: Manual Parameter Capture (PRIMARY)
- User interface for entering all 18 parameters
- Support for photo/screenshot input with OCR assistance
- Validation against parameter ranges

### Method B: Audio-Based Reconstruction
- Record reference audio through MXR
- Analyze spectral characteristics
- Estimate filter cutoff, resonance, envelope timing
- Compare against known parameter signatures

### Method C: Factory Preset Library
- Pre-defined settings for all 8 factory presets
- User can select as starting point

---

## Preset Export Strategy

### Option 1: Guided Configuration (RECOMMENDED)
- Generate complete parameter sheet
- Display values for manual entry in Anagram
- Include Axioma block settings
- Optionally suggest additional blocks (compression, EQ)

### Option 2: MIDI-Based Configuration
- Generate MIDI CC sequence to set parameters
- Requires user to configure CC bindings first
- Limited to 6 active bindings at a time

### Option 3: Native Preset File (FUTURE)
- Darkglass Suite uses undocumented format
- Would require reverse engineering
- Risk of device incompatibility
- **NOT RECOMMENDED** without official documentation

---

## References

1. MXR MB301 Bass Synth Manual - https://www.jimdunlop.com/content/manuals/MB301.pdf
2. Darkglass Anagram Manual (KosmOS 1.17) - https://api.darkglass.com/static/Anagram-Manual.pdf
3. Darkglass Axioma Release Notes - KosmOS 1.18.0
4. Darkglass Suite - https://www.darkglass.com/products/darkglass-suite
5. TalkBass Anagram MIDI Reference - https://www.talkbass.com/wiki/anagram-midi/

---

*Document generated: 2026-10-12*
*Last verified: 2026-10-12*
