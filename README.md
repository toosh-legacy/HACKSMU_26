# HACKSMU_26 — RumbleOS

Multi-agent Python pipeline that removes mechanical noise from elephant infrasound
recordings and discovers communication patterns.

## Setup

```bash
pip install -r rumbleos/requirements.txt
```

## Configure paths before running

In `rumbleos/main.py`, update the three path constants at the bottom to match your machine:

```python
# ── CONFIGURE THESE ──────────────────────────────────────────────
CSV_PATH       = r"<absolute path to>\rumbleos\data\timestamps.csv"
AUDIO_DIR      = r"<absolute path to>\recordings\<audio folder>"
OUTPUT_DIR     = r"<absolute path to>\rumbleos\results"
```

**Example (original dev machine — Windows):**

```python
CSV_PATH  = r"C:\Users\tusha\Documents\hackathons\smu\HACKSMU_26\rumbleos\data\timestamps.csv"
AUDIO_DIR = r"C:\Users\tusha\Documents\hackathons\smu\HACKSMU_26\recordings\2026)-20260411T194946Z-3-001\Audio Files (04-10-2026)"
OUTPUT_DIR = r"C:\Users\tusha\Documents\hackathons\smu\HACKSMU_26\rumbleos\results"
```

**Example (Linux / macOS / WSL):**

```python
CSV_PATH   = "/path/to/HACKSMU_26/rumbleos/data/timestamps.csv"
AUDIO_DIR  = "/path/to/HACKSMU_26/recordings/Audio Files (04-10-2026)"
OUTPUT_DIR = "/path/to/HACKSMU_26/rumbleos/results"
```

The WAV files (44 recordings) should live flat inside `AUDIO_DIR` — no subfolders.

## Run

```bash
cd rumbleos
python main.py          # sequential mode (default, good for debugging)
```

To switch to parallel mode (4× faster), open `main.py` and set:

```python
SEQUENTIAL_MODE = False
```

## Dashboard

```bash
cd rumbleos
streamlit run dashboard/app.py
```

## Optional: Claude API hypotheses

Set `CLAUDE_API_KEY` in `main.py` to get AI-generated behavioral hypotheses for each
call cluster saved to `results/ai_hypotheses.txt`.

## Pipeline stages

| Stage | Agent | What it does |
|-------|-------|--------------|
| 1 | PreprocessAgent | Load WAV → resample 4 kHz → bandpass 10–1000 Hz → extract segment |
| 2 | FingerprintAgent | Classify noise: generator / airplane / car |
| 3 | NMFMaskingAgent | STFT → NMF (10 components) → harmonic score → soft Wiener mask |
| 4 | ReconstructionAgent | Exponential decay fit → reconstruct damaged harmonics → ISTFT |
| 5 | OverlapAgent | Detect dual F0 peaks → separate two simultaneous callers |
| 6 | QualityScorerAgent | SNR before/after, harmonic completeness, validity flag |
| 7 | ClusteringAgent | UMAP + K-means → Tribe similarity graph → Claude API hypotheses |

Output WAVs are **full source-file length** — cleaned windows spliced back in place,
non-elephant regions left unchanged.