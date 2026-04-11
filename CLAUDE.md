# CLAUDE.md — RumbleOS Hackathon Project

## Project Overview

**RumbleOS** is a multi-agent Python system that removes mechanical noise from elephant
infrasound recordings and discovers communication patterns. 44 WAV files contain 212
documented elephant calls (10–24 Hz fundamental, harmonics to 1000 Hz) buried under
airplane, car, or generator noise.

## Repository Layout

```
rumbleos/         ← all Python source lives here
  agents/         ← 9 pipeline agents (each a separate OS process)
  edge/           ← Raspberry Pi live-capture listener
  dashboard/      ← Streamlit visualization app
  data/
    recordings/   ← put WAV files here
    timestamps.csv← call index: filename, start_time, end_time, noise_type
  results/        ← output WAVs, spectrograms, CSVs, JSON
  main.py         ← launcher (sequential or parallel mode)
  requirements.txt
frontend/         ← (reserved for web UI if needed)
backend/          ← (reserved for API layer if needed)
```

## Critical Parameters — DO NOT CHANGE

```python
TARGET_SR          = 4000    # downsample rate — gives 1.95 Hz/bin at n_fft=2048
N_FFT              = 2048
HOP_LENGTH         = 512
N_COMPONENTS       = 10      # NMF components
PROP_DECREASE      = 0.75    # noise mask strength
ELEPHANT_THRESHOLD = 0.35    # harmonic score cutoff
BANDPASS_LOW       = 10      # Hz
BANDPASS_HIGH      = 1000    # Hz
F0_MIN / F0_MAX    = 10/35   # elephant fundamental range
```

## Pipeline Stages

| Stage | Agent | What it does |
|-------|-------|--------------|
| 1 | `PreprocessAgent` | Load WAV → resample 4 kHz → bandpass 10-1000 Hz → extract segment + noise ref |
| 2 | `FingerprintAgent` | Classify noise: generator_60hz / generator_90hz / generator_45hz / airplane / car |
| 3 | `NMFMaskingAgent` | **Core ML** — STFT → NMF (10 components, KL loss) → harmonic score → soft Wiener mask |
| 4 | `ReconstructionAgent` | Exponential decay fit → reconstruct damaged harmonics → ISTFT |
| 5 | `OverlapAgent` | Detect dual F0 peaks → separate two simultaneous callers via dual NMF |
| 6 | `QualityScorerAgent` | SNR before/after, harmonic completeness, validity flag, SenseCAP event |
| 7 | `ClusteringAgent` | UMAP + K-means → Tribe similarity graph → Claude API behavioral hypotheses |

`SenseCapAgent` runs in parallel and streams detection events to the SenseCAP Indicator
device over USB serial at `/dev/ttyUSB0` (115200 baud).

## Running the System

```bash
cd rumbleos

# Install deps
pip install -r requirements.txt

# Debug — sequential, no multiprocessing
# Edit main.py: set SEQUENTIAL_MODE = True
python main.py

# Full run — parallel (4 workers)
# Edit main.py: set SEQUENTIAL_MODE = False
python main.py

# Dashboard
streamlit run dashboard/app.py
```

## Quick Smoke Tests

```bash
# Stage 1 import check
python -c "from agents.base import BaseAgent, SENTINEL; print('base OK')"

# Stage 3 NMF correctness (synthetic 18 Hz signal)
python -c "
import numpy as np; from agents.nmf_masking import NMFMaskingAgent
sr=4000; t=np.linspace(0,10,40000)
sig=sum(np.sin(2*np.pi*18*n*t)/n for n in range(1,8))
noisy=sig+np.random.randn(len(t))*0.5
r=NMFMaskingAgent(0,None,None,name='T').process({'segment':noisy,'sr':sr,'noise_type':'airplane','original':noisy,'call_id':'t'})
assert 14<=r['detected_f0']<=22, r['detected_f0']
print('Stage 3 OK — F0=',r['detected_f0'])
"
```

## Common Errors

| Error | Fix |
|-------|-----|
| `librosa.load` fails | `pip install soundfile` |
| `iircomb` not found | `pip install scipy --upgrade` (needs ≥1.9) |
| NMF slow | Reduce `max_iter` to 200 for testing |
| SenseCAP not found | Try `/dev/ttyACM0` |
| UMAP install fails | Falls back to PCA automatically |
| Queue deadlock | Set `SEQUENTIAL_MODE = True` |
| Out of memory (RPi) | Reduce `N_WORKERS` to 2 |
| NMF F0 wrong | Increase `max_iter` to 600; verify `n_fft=2048`, `sr=4000` |

## SenseCAP Firmware

1. Clone `Seeed-Solution/SenseCAP_Indicator_ESP32`
2. Open in ESP-IDF v5.1.x (VS Code + ESP-IDF extension)
3. Start from `indicator_basis` example
4. Add JSON serial parse loop (see Master Architecture doc)
5. Flash via ESP32-S3 USB-C port (not RP2040 port)

## Custom Commands

- `/plan` — plan a feature or algorithm change
- `/review` — review code for correctness and signal-processing accuracy
- `/ship` — run tests, commit, and push

## Key Conventions

- All agents inherit from `BaseAgent` (multiprocessing.Process)
- Messages flow as plain `dict` objects through `mp.Queue`
- `SENTINEL = None` is the poison pill to shut down a worker
- `valid=False` calls are forwarded through the pipeline (never dropped silently)
- Array fields (`magnitude`, `phase`, `mask`, `segment`, `cleaned`) are NumPy arrays
  — they do NOT survive CSV serialization; only scalar fields land in `batch_results.csv`
