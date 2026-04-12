# Tribal

A multi-agent signal processing system that strips mechanical noise from elephant
infrasound recordings and uncovers behavioral communication patterns. Built at HackSMU 2026.

---

## What It Does

Elephants communicate through infrasound — low-frequency rumbles (10–35 Hz fundamental,
harmonics to ~1000 Hz) inaudible to humans. Field recordings are almost always contaminated
by airplane flyovers, vehicle engines, or generator hum at overlapping frequencies.

Tribal takes raw, noisy WAV files and:

1. Classifies the noise type (airplane, car, generator)
2. Runs NMF-based Wiener masking to suppress noise across the entire recording
3. Reconstructs harmonics damaged by the noise
4. Detects two simultaneous callers and separates them into independent tracks
5. Scores each call for SNR improvement and harmonic completeness
6. Clusters all calls by acoustic signature and generates AI behavioral hypotheses via Gemini

Results are displayed in a Vite + React frontend with a knowledge graph, spectrogram
explorer, and cluster analysis view.

---

## Architecture

```
WAV files
    |
    v
[PreprocessAgent]      Stage 1 — load, downsample 4kHz, bandpass 10–1000Hz
    |
    v
[FingerprintAgent]     Stage 2 — classify noise: airplane / car / generator_Nhz
    |
    v
[NMFMaskingAgent]      Stage 3 — STFT → NMF → harmonic scoring → Wiener mask  ← core ML
    |
    v
[ReconstructionAgent]  Stage 4 — exponential decay fit, reconstruct damaged harmonics
    |
    v
[OverlapAgent]         Stage 5 — detect dual callers, competitive Wiener separation
    |
    v
[QualityScorerAgent]   Stage 6 — SNR before/after, harmonic completeness, validity flag
    |
    v
[ClusteringAgent]      Stage 7 — UMAP + K-means, Tribe similarity graph, Gemini hypotheses
```

Each stage is a `BaseAgent` (`multiprocessing.Process`) passing plain `dict` messages
through `mp.Queue`. No shared memory. Crashes forward an `error` key — nothing stalls silently.

### Key Parameters

```python
TARGET_SR      = 4000    # 4kHz → 1.95 Hz/bin at n_fft=2048
N_FFT          = 2048
HOP_LENGTH     = 512
N_COMPONENTS   = 10      # NMF basis vectors
TOP_K_ELEPHANT = 2       # top-K components classified as elephant
MASK_FLOOR     = 0.25
F0_RANGE       = 10–35 Hz
```

Do not change `TARGET_SR`, `N_FFT`, or `HOP_LENGTH` without re-tuning harmonic scoring —
these three are tightly coupled.

---

## Repository Layout

```
rumbleos/
  agents/          9 pipeline agents
  edge/            Raspberry Pi live-capture listener
  data/
    timestamps.csv call index: filename, start_time, end_time, noise_type
  results/         output WAVs, spectrograms, CSVs, JSON, hypotheses
  main.py          pipeline launcher
  gen_hypotheses.py standalone Gemini hypothesis generator
  requirements.txt

frontend/
  src/
    main.js                    routing, data loading, section rendering
    network-graph/             Sigma.js + ForceAtlas2 knowledge graph (React/TS)
    components/ui/             shared UI components
  index.html
  vite.config.js               serves /results/* from rumbleos/results/
```

---

## Setup

### Python pipeline

```bash
cd rumbleos
pip install -r requirements.txt
```

### Frontend

```bash
cd frontend
npm install
```

---

## Running

### Pipeline

```bash
cd rumbleos
python main.py
```

Configure at the top of `main.py`:

```python
SEQUENTIAL_MODE = True    # True = no multiprocessing, full tracebacks (use for dev)
FULL_FILE_MODE  = True    # True = clean entire file; False = per-call windows
N_WORKERS       = 4       # parallel workers (ignored in SEQUENTIAL_MODE)
```

### Frontend

```bash
cd frontend
npm run dev        # http://localhost:5174
npm run build      # production build
npm run preview    # preview production build
```

### Gemini hypotheses (standalone)

Run this if you want to regenerate `ai_hypotheses.txt` without re-running the full pipeline:

```bash
cd rumbleos
python gen_hypotheses.py
```

Requires `GEMINI_API_KEY` in `.env` (project root).

---

## Environment

Create `.env` in the project root:

```
GEMINI_API_KEY=your_key_here
CSV_PATH=data/timestamps.csv
OUTPUT_DIR=results
```

`AUDIO_DIR` is set directly in `main.py` (path to your WAV files).

---

## Outputs

All outputs go to `rumbleos/results/` and are served live to the frontend at `/results/*`.

| File | Description |
|------|-------------|
| `*_clean.wav` | Full-length denoised recording, non-elephant regions silent |
| `*_comparison.png` | Before/after spectrogram per call |
| `batch_results.csv` | Per-call metrics: SNR, F0, validity, cluster, etc. |
| `batch_results_clustered.csv` | Same with UMAP coordinates |
| `tribe_edges.csv` | Cosine-similarity graph edges between calls |
| `cluster_summaries.json` | Cluster centroids and member call IDs |
| `ai_hypotheses.txt` | Gemini behavioral interpretation of each cluster |
| `knowledge_base.json` | Acoustic signatures linked to metadata |

---

## Edge Device (Raspberry Pi)

`edge/listen.py` runs a live capture loop on the Pi — reads from the microphone via
`sounddevice`, applies the 4kHz bandpass, and sends detection events over a socket to
the pipeline. No external IoT hardware required; everything runs locally on the Pi.

On Pi, reduce memory usage:

```python
N_WORKERS = 2
# set max_iter=200 in agents/nmf_masking.py
```

Prereq: `sudo apt install libsndfile1`

---

## Common Errors

| Error | Fix |
|-------|-----|
| `librosa.load` fails | `pip install soundfile` |
| `iircomb` not found | `pip install "scipy>=1.9"` |
| NMF slow | Set `max_iter=200` for testing |
| UMAP install fails | Falls back to PCA automatically |
| Queue deadlock | Set `SEQUENTIAL_MODE = True` |
| Out of memory on Pi | Set `N_WORKERS=2`, `max_iter=200` |
| NMF F0 wrong | Verify `sr=4000`, `n_fft=2048`; raise `max_iter` to 600 |
| Gemini 429 quota | Free tier limit hit — retry after 60s or use a new key |

---

## Smoke Test

```bash
cd rumbleos
python -c "
import numpy as np; from agents.nmf_masking import NMFMaskingAgent
sr=4000; t=np.linspace(0,10,40000)
sig=sum(np.sin(2*np.pi*18*n*t)/n for n in range(1,8))
noisy=sig+np.random.randn(len(t))*0.5
r=NMFMaskingAgent(0,None,None,name='T').process({'segment':noisy,'sr':sr,'noise_type':'airplane','original':noisy,'call_id':'t'})
assert 14<=r['detected_f0']<=22, r['detected_f0']
print('Stage 3 OK — F0=', r['detected_f0'])
"
```

---

## Research Foundation

- Payne et al. (1986) — infrasonic calls of the Asian elephant
- Poole et al. (1988) — social contexts of low-frequency elephant calls
- Poole (2005) — F0 range and ≥5 Hz gap between simultaneous callers
- Lee & Seung (1999) — NMF for parts-based representations
- Fevotte et al. (2009) — NMF with KL divergence
- Scalart & Filho (1996) — Wiener mask from SNR estimation
- McInnes et al. (2018) — UMAP dimensionality reduction