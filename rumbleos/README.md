```
  ████████╗██████╗ ██╗██████╗  █████╗ ██╗
  ╚══██╔══╝██╔══██╗██║██╔══██╗██╔══██╗██║
     ██║   ██████╔╝██║██████╔╝███████║██║
     ██║   ██╔══██╗██║██╔══██╗██╔══██║██║
     ██║   ██║  ██║██║██████╔╝██║  ██║███████╗
     ╚═╝   ╚═╝  ╚═╝╚═╝╚═════╝ ╚═╝  ╚═╝╚══════╝

  🐘  hear what humans can't  •  HackSMU 2026
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  10 Hz ▁▂▃▄▅▆▇█▇▆▅▄▃▂▁ 35 Hz  →  clean signal
```

> Multi-agent elephant infrasound cleaner and behavioral pattern discovery system.

Elephants communicate at 10–35 Hz, well below human hearing. Field recordings are buried under airplane, vehicle, and generator noise. Tribal runs a 7-stage ML pipeline to strip that noise, reconstruct damaged harmonics, separate simultaneous callers, and discover communication patterns using UMAP clustering and AI hypothesis generation.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         INPUT LAYER                                     │
│                                                                         │
│   WAV files (44 recordings)          Raspberry Pi edge listener         │
│   timestamps.csv annotation   ──or── live 4 kHz microphone capture     │
│          │                                    │                         │
│          └──────────────┬─────────────────────┘                        │
│                         ▼                                               │
│              HTTP Upload Server (port 5050)                             │
│           stdlib Python · base64 WAV upload · CSV auto-entry           │
└─────────────────────────────┬───────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       PIPELINE (9 agents, 4 workers)                    │
│                                                                         │
│  mp.Queue  mp.Queue  mp.Queue  mp.Queue  mp.Queue  mp.Queue            │
│     │          │         │         │         │         │               │
│  ┌──▼──┐   ┌──▼──┐   ┌──▼──┐   ┌──▼──┐   ┌──▼──┐   ┌──▼──┐         │
│  │ Pre │──▶│Fing │──▶│ NMF │──▶│Recon│──▶│Over │──▶│Score│          │
│  └─────┘   └─────┘   └─────┘   └─────┘   └─────┘   └─────┘          │
│  Stage 1   Stage 2   Stage 3   Stage 4   Stage 5    Stage 6           │
│                                                          │              │
│                                                    ┌─────▼──────┐      │
│                                                    │  SenseCAP  │      │
│                                                    │  (serial)  │      │
│                                                    └────────────┘      │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ all results
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       ANALYSIS LAYER                                    │
│                                                                         │
│   ClusteringAgent (Stage 7)                                             │
│   UMAP → K-means → Tribe graph → Gemini API behavioral hypotheses      │
│                                                                         │
│   Outputs:  batch_results.csv  tribe_edges.csv  cluster_summaries.json │
│             knowledge_base.json  ai_hypotheses.txt  *_clean.wav        │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Pipeline Stages

### Stage 1 — PreprocessAgent
**File:** [agents/preprocess.py](agents/preprocess.py)

Loads each WAV at native sample rate, downsamples to **4 kHz** (Nyquist for 2 kHz ceiling), applies a **10–1000 Hz Butterworth bandpass** (4th order, zero-phase `sosfiltfilt`), then extracts the annotated call window plus a noise reference segment (up to 3 s before the first call onset).

```
WAV (native SR, any bit depth)
  → librosa resample (soxr_hq)  →  4000 Hz mono float32
  → scipy butter bandpass       →  10–1000 Hz signal
  → segment + noise_ref extracted
```

Key parameters: `TARGET_SR = 4000`, `BANDPASS_LOW = 10`, `BANDPASS_HIGH = 1000`

---

### Stage 2 — FingerprintAgent
**File:** [agents/fingerprint.py](agents/fingerprint.py)

Classifies the mechanical noise type from the noise reference segment using spectral fingerprinting. Detects comb structure for generator harmonics and spectral centroid/roll-off for aircraft vs. vehicle.

| Label | Characteristic |
|---|---|
| `generator_60hz` | 60 Hz comb + sidebands |
| `generator_90hz` | 90 Hz comb |
| `generator_45hz` | 45 Hz comb |
| `airplane` | Broadband, high spectral centroid |
| `car` / `vehicle` | Low centroid, irregular |

Falls back to `_auto_` detection via probe segment when CSV labels say `unknown`.

---

### Stage 3 — NMFMaskingAgent (Core ML)
**File:** [agents/nmf_masking.py](agents/nmf_masking.py)

The heart of the noise separation. Applies **Non-negative Matrix Factorization** with KL-divergence loss on the STFT magnitude spectrogram.

```
STFT (n_fft=2048, hop=512, sr=4000)  →  magnitude V (freq × time)
  NMF:  V ≈ W · H   (10 components, KL loss, max_iter=400)
  ↓
  Each component W[:,k] scored by harmonic_pattern_score()
    — checks energy at F0 × {1,2,3,...,14} within ±2 bins
  ↓
  Top-K=3 components selected as elephant (robust to score distribution)
  ↓
  Wiener soft mask:  mask = elephant_mag / (elephant_mag + noise_mag + ε)
  ↓
  Masked magnitude ready for reconstruction
```

**Critical design decision:** `TOP_K_ELEPHANT = 3` replaced a 0.35 threshold after harmonic scores clustered tightly in 0.45–0.55, causing all 10 components to pass and producing an all-ones mask (0 dB improvement). Top-K is distribution-invariant.

---

### Stage 4 — ReconstructionAgent
**File:** [agents/reconstruction.py](agents/reconstruction.py)

Harmonics above ~500 Hz are often damaged by noise masking. This agent fits an **exponential decay model** to the recovered harmonic series (amplitude ∝ e^{−αn}) and reconstructs missing or weak harmonics by extrapolation. Applies phase reconstruction via ISTFT.

```
Detected harmonics {F0, 2F0, 3F0, ...}
  → fit A·exp(-α·n) to amplitudes
  → reconstruct weak/missing harmonics
  → ISTFT  →  cleaned time-domain signal
```

---

### Stage 5 — OverlapAgent
**File:** [agents/overlap.py](agents/overlap.py)

Detects **dual fundamental frequencies** in the STFT to identify simultaneous callers. When two F0 peaks separated by ≥ 5 Hz are found, runs a second independent NMF pass to separate the two streams.

```
STFT magnitude  →  peak detection in 10–35 Hz band
  if |F0_a - F0_b| ≥ 5 Hz:
    dual NMF → stream_a (cleaned), stream_b (cleaned_b)
    sets multi_elephant = True
  else:
    single-caller path
```

The 5 Hz gap threshold follows Poole (2005) — narrower separations match harmonics of a single caller, not a second individual.

---

### Stage 6 — QualityScorerAgent
**File:** [agents/quality_scorer.py](agents/quality_scorer.py)

Measures cleaning quality and flags calls for downstream use.

| Metric | Method |
|---|---|
| `snr_before_db` | RMS of original segment |
| `snr_after_db` | RMS of cleaned segment |
| `snr_improvement_db` | Δ in dB |
| `harmonics_present` | Count of harmonic bins with energy > threshold |
| `harmonic_completeness` | present / possible harmonics |
| `f0_hz` | Detected fundamental frequency |
| `valid` | True if SNR improvement > 0 and harmonic completeness > 0.3 |

Also emits a JSON event to `SenseCapAgent` over `mp.Queue` for real-time display.

---

### Stage 7 — ClusteringAgent
**File:** [agents/clustering.py](agents/clustering.py)

Runs once all results are collected. Builds acoustic feature vectors and discovers communication patterns.

```
Feature vector per call:
  [f0_hz, duration_s, harmonics_present, harmonic_completeness,
   snr_after_db, snr_improvement_db, multi_elephant_flag, f0_b]

  + context columns from CSV (elephant_id, age_class, sex,
    family_group, clan, breeding_context, …)

  → StandardScaler → UMAP (n=2, n_neighbors=10, min_dist=0.1)
                         or PCA fallback if umap-learn not installed
  → K-means (k = min(7, n_valid//3))
  → Tribe similarity graph (cosine_similarity > 0.80)
  → Gemini 1.5 Flash: behavioral hypotheses per cluster
```

**Tribe affinity** combines 70% acoustic cosine similarity + 30% metadata affinity (weighted by field: `elephant_id × 4`, `family_group × 3`, `sex × 2`, …).

---

### SenseCapAgent (parallel)
**File:** [agents/sensecap.py](agents/sensecap.py)

Streams JSON detection events to a **SenseCAP Indicator** (ESP32-S3 + RP2040) over USB serial at 115200 baud. Displays live F0, SNR, and call counts on the device screen. Runs in its own process alongside the main pipeline.

---

### Edge Listener
**File:** [edge/listen.py](edge/listen.py)

Runs on a **Raspberry Pi** with a microphone for live field capture. Records 10-second chunks at 4 kHz, then either pushes to a local queue for on-device processing or publishes via **MQTT** to a remote pipeline host.

---

## Full-File Mode vs. Annotated-Window Mode

| Mode | When | What |
|---|---|---|
| `FULL_FILE_MODE = True` | Production | NMF on entire recording; Wiener mask passes elephant harmonics everywhere, silences noise everywhere — detected or not |
| `SEQUENTIAL_MODE = True` | Debug | Only annotated windows from `timestamps.csv`; no multiprocessing |
| Default (parallel) | Benchmark | 4 worker processes, 9 agents, 4× throughput |

---

## Technology Stack

| Layer | Technology |
|---|---|
| Audio DSP | `librosa >= 0.10`, `scipy >= 1.11` (butter, sosfiltfilt, wavfile) |
| Source separation | scikit-learn NMF (KL loss), custom Wiener masking |
| Dimensionality reduction | `umap-learn >= 0.5` (PCA fallback via scikit-learn) |
| Clustering | scikit-learn KMeans, cosine similarity graph |
| Concurrency | Python `multiprocessing` — process-per-agent, `mp.Queue` message passing |
| AI hypotheses | Google Gemini 1.5 Flash (`google-generativeai >= 0.7`) |
| Noise reduction | `noisereduce >= 3.0` (spectral gating, auxiliary) |
| Serial / IoT | `pyserial >= 3.5` (SenseCAP), `paho-mqtt >= 1.6` (MQTT edge stream) |
| Visualization | `matplotlib >= 3.7` (spectrogram comparison PNGs) |
| Graph analysis | `networkx >= 3.0` (Tribe similarity graph) |
| Upload server | Python stdlib `http.server` (no framework dependencies) |
| Live capture | `sounddevice >= 0.4.6` (Raspberry Pi edge) |

---

## Outputs

```
results/
  *_clean.wav                  — full recording with elephant calls isolated
  *_c###_comparison.png        — before/after spectrogram per call
  batch_results.csv            — scalar metrics for every call
  batch_results_clustered.csv  — same + cluster assignment
  tribe_edges.csv              — call-pair similarity graph edges
  cluster_summaries.json       — per-cluster acoustic profile
  knowledge_base.json          — full structured call database (schema v1)
  ai_hypotheses.txt            — Gemini behavioral hypotheses
```

---

## Quick Start

```bash
cd rumbleos

# Install dependencies
pip install -r requirements.txt

# Place WAV files in:
#   ../recordings/.../Audio Files/

# Run full pipeline (edits timestamps.csv automatically for uploads)
python main.py

# Upload a new WAV via HTTP
python server.py   # starts on port 5050
# then POST /api/upload with { filename, data: base64 }

# Edge live capture (Raspberry Pi)
python edge/listen.py
```

**Debug mode** — edit [main.py](main.py):
```python
SEQUENTIAL_MODE = True   # single process, easy to step through
FULL_FILE_MODE  = False  # only annotated windows
```

---

## Signal Parameters (do not change without re-validation)

```python
TARGET_SR          = 4000    # Hz — gives 1.95 Hz/bin at n_fft=2048
N_FFT              = 2048
HOP_LENGTH         = 512
N_COMPONENTS       = 10      # NMF components
TOP_K_ELEPHANT     = 3       # top-K components classified as elephant
PROP_DECREASE      = 0.75    # Wiener mask strength
BANDPASS_LOW       = 10      # Hz
BANDPASS_HIGH      = 1000    # Hz
F0_MIN / F0_MAX    = 10/35   # elephant fundamental range (Hz)
```

---

## Dataset

- **44 WAV files**, 212 documented elephant calls
- Noise categories: airplane, vehicle, generator (45/60/90 Hz variants)
- Call fundamentals: 10–24 Hz, harmonics up to 1000 Hz
- Annotation format: `timestamps.csv` — `filename, start_time, end_time, noise_type`
- Optional context columns: `elephant_id`, `age_class`, `sex`, `family_group`, `clan`, `breeding_context`, `call_type`, …
