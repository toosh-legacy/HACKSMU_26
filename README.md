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

A multi-agent signal processing system that strips mechanical noise from elephant
infrasound recordings and uncovers behavioral communication patterns. Built at HackSMU 2026.

**Devpost:** https://devpost.com/software/le-go-snm4q6

---

## What It Does

Elephants communicate through infrasound - low-frequency rumbles (10–35 Hz fundamental,
harmonics to ~1000 Hz) inaudible to humans. Field recordings are almost always contaminated
by airplane flyovers, vehicle engines, or generator hum at overlapping frequencies.

Tribal takes raw, noise WAV files and:

1. Classifies the noise type (airplane, vehicle, generator variant)
2. Spectral subtraction of the stationary noise floor before NMF
3. NMF-based Wiener masking to suppress noise, retaining only elephant harmonics
4. Reconstructs harmonics damaged by the noise via exponential decay curve fitting
5. Detects two simultaneous callers and separates them into independent tracks
6. Scores each call for tonal SNR improvement and harmonic completeness
7. Clusters all calls by acoustic signature and generates AI behavioral hypotheses via Gemini

Results are displayed in a Vite + React frontend with a knowledge graph, spectrogram
explorer, and cluster analysis view.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              INPUT LAYER                                    │
│                                                                             │
│  ┌──────────────────┐    ┌──────────────────┐    ┌────────────────────┐   │
│  │   WAV files      │    │  HTTP Upload      │    │  Raspberry Pi      │   │
│  │  44 recordings   │    │  server.py :5050  │    │  edge/listen.py    │   │
│  │  timestamps.csv  │    │  base64 + CSV     │    │  sounddevice 4kHz  │   │
│  └────────┬─────────┘    └────────┬──────────┘    └─────────┬──────────┘   │
│           └─────────────────────┬─┘                         │  MQTT/queue  │
└─────────────────────────────────┼───────────────────────────┼──────────────┘
                                  │ WAV + metadata             │
                                  ▼                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        PIPELINE  (9 agents · 4 workers)                    │
│                                                                             │
│   mp.Queue ──► mp.Queue ──► mp.Queue ──► mp.Queue ──► mp.Queue ──► mp.Queue│
│      │             │             │            │            │            │   │
│  ┌───▼───┐    ┌────▼────┐   ┌───▼───┐   ┌───▼───┐   ┌───▼───┐   ┌───▼───┐│
│  │  Pre  │    │ Finger  │   │  NMF  │   │ Recon │   │ Over  │   │ Score ││
│  │ Stage1│──► │ Stage 2 │──►│Stage 3│──►│Stage 4│──►│Stage 5│──►│Stage 6││
│  └───────┘    └─────────┘   └───────┘   └───────┘   └───────┘   └───┬───┘│
│  librosa       Welch PSD     STFT+NMF    exp-decay   dual-NMF     Welch│   │
│  butter BP     comb detect   Wiener mask harmonic    comp-Wiener  SNR  │   │
│                                          reconstruct  separation   tonal│   │
│                                                                     ┌───▼───┐│
│                                                                     │Sense ││
│                                                                     │ CAP  ││
│                                                                     │serial││
│                                                                     └───────┘│
└──────────────────────────────────────────┬──────────────────────────────────┘
                                           │ all results (list of dicts)
                                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ANALYSIS LAYER                                    │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │  ClusteringAgent  (Stage 7 - fires once, after all calls collected)  │ │
│  │                                                                       │ │
│  │  feature vec  →  StandardScaler  →  UMAP (2D)  →  K-means (k≤7)    │ │
│  │  + metadata                           or PCA                          │ │
│  │                                                                       │ │
│  │  cosine_similarity > 0.80  →  Tribe graph edges                      │ │
│  │  70% acoustic + 30% metadata affinity  →  knowledge_base.json        │ │
│  │  Gemini 1.5 Flash  →  behavioral hypotheses per cluster              │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  Outputs: *_clean.wav  ·  *_comparison.png  ·  batch_results.csv          │
│           tribe_edges.csv  ·  cluster_summaries.json  ·  ai_hypotheses.txt │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Pipeline - Stage by Stage

### Stage 1 · PreprocessAgent

```
WAV (native SR, any bit depth)
  │
  ├─ librosa.load(sr=None, mono=False)   ← preserves channel count + native SR
  │    source_sr, n_channels, source_len recorded for final splice
  │
  ├─ mean over channels → mono float32
  │
  ├─ librosa.resample(orig_sr=source_sr, target_sr=4000, res_type='soxr_hq')
  │
  ├─ scipy.signal.butter(N=4, Wn=[10,1000], btype='band', fs=4000, output='sos')
  │    sosfiltfilt (zero-phase, no group delay)
  │
  ├─ segment = y[start-1.5s : end+1.5s]     ← 1.5 s context padding for STFT framing
  ├─ noise_ref = y[start-3s : start]         ← 3 s of pure mechanical noise pre-call
  │
  └─ core window (start:end) tracked in both 4 kHz and native-SR sample indices
     → spliced back into original file at write time (non-call regions bit-perfect)
```

**Why 4 kHz?** At `n_fft=2048`, `sr=4000` gives **1.953 Hz/bin** - enough resolution to
resolve the 10–35 Hz elephant fundamental without aliasing at the 1000 Hz harmonic ceiling.
Halving the sample rate also cuts NMF compute by 8× (STFT frames scale linearly with SR).

---

### Stage 2 · FingerprintAgent

Classifies the mechanical noise source from the noise reference segment using
**Welch PSD** (`nperseg=2048`). No ML - pure spectral fingerprinting.

```
noise_ref  →  scipy.signal.welch(fs=4000, nperseg=2048)
                  │
                  ├─ Generator detection: comb harmonic scan
                  │    for n in 1..12:
                  │        check psd[f0*n ± 2Hz] > local_floor × 12
                  │    local_floor = median(PSD[50–500 Hz])  ← avoids global bias
                  │
                  │    h60 ≥ 6 and s60 ≥ s90  →  generator_60hz
                  │    h90 ≥ 5                →  generator_90hz
                  │    h45 ≥ 4                →  generator_45hz
                  │
                  ├─ Airplane detection: broadband energy ratio + smoothness
                  │    low_e  = mean(PSD[80–200 Hz])
                  │    high_e = mean(PSD[200–1000 Hz])
                  │    ratio  = low_e / high_e
                  │    smooth = std(diff(log10(PSD)))     ← log-smoothness of curve
                  │
                  │    ratio > 2.5 and smooth < 0.4  →  airplane
                  │
                  └─ else  →  car / vehicle
```

**Design note:** The local floor (median of 50–500 Hz band) replaced a global 20th-percentile
floor. Global p20 was too low when the bandpass concentrated energy below 200 Hz, causing
residual mains hum to trigger false `generator` classifications.

---

### Stage 3 · NMFMaskingAgent  ← core ML

This is the noise separation engine. Three sub-steps: spectral subtraction, NMF decomposition, and Wiener masking.

```
                    ┌─────────────────────────────────────┐
                    │         SPECTRAL SUBTRACTION         │
                    │                                     │
  segment ──STFT──► │  V_orig = |STFT(segment)|           │
  noise_ref──STFT──► │  N_ref  = median(|STFT(noise_ref)|) │
                    │                                     │
                    │  V_sub = max(V_orig - α·N_ref,      │
                    │              V_orig · 0.22)         │
                    │                                     │
                    │  α = 1.25 for car + airplane        │
                    │  α = None for generators (comb      │
                    │       notch filter handles those)   │
                    └──────────────┬──────────────────────┘
                                   │ V_sub (noise-reduced magnitude)
                                   ▼
                    ┌─────────────────────────────────────┐
                    │           NMF DECOMPOSITION          │
                    │                                     │
                    │  V_sub ≈ W · H                      │
                    │                                     │
                    │  W: (1025 freq_bins × 10 components)│
                    │  H: (time_frames   × 10 components) │
                    │                                     │
                    │  init:      nndsvda                 │
                    │  solver:    multiplicative update   │
                    │  beta_loss: kullback-leibler        │
                    │  max_iter:  800  tol: 1e-3          │
                    └──────────────┬──────────────────────┘
                                   │ W, H
                                   ▼
                    ┌─────────────────────────────────────┐
                    │        COMPONENT SCORING             │
                    │                                     │
                    │  harmonic_score(W[:,k]):            │
                    │    find F0 ∈ [10,35] Hz in W[:,k]  │
                    │    for n in 1..20:                  │
                    │        check W[F0·n ± 1.5Hz] >      │
                    │               percentile(W,25)·3.5  │
                    │    score = (Σ harmonic energy/total)│
                    │             ×0.6 + (hits/5)×0.4    │
                    │                                     │
                    │  temporal_score(H[:,k]):            │
                    │    cv = std(H_norm) / mean(H_norm)  │
                    │    score = clip(cv, 0, 2) / 2.0     │
                    │    (elephant=localized, noise=flat) │
                    │                                     │
                    │  combined = 0.65·harmonic           │
                    │           + 0.35·temporal           │
                    │                                     │
                    │  select TOP_K=2 components          │
                    │  (drop any below floor 0.15)        │
                    └──────────────┬──────────────────────┘
                                   │ is_elephant[k]
                                   ▼
                    ┌─────────────────────────────────────┐
                    │          WIENER MASKING              │
                    │                                     │
                    │  e_sig = W[:,elephant] @ H[:,elephant]ᵀ │
                    │  n_sig = W[:,noise]    @ H[:,noise]ᵀ    │
                    │                                     │
                    │  mask = e_sig / (e_sig + 0.9·n_sig) │
                    │  mask applied to V_orig (not V_sub) │
                    │                                     │
                    │  hard gate:  mask < 0.25 → 0        │
                    │  rescale:    (mask-0.25) / 0.75     │
                    │  sharpen:    mask = mask²           │
                    │    (0.9²=0.81, 0.3²=0.09, 0.1²=0.01)│
                    │                                     │
                    │  generators: additionally apply     │
                    │  iircomb notch (Q=35) at RPM freq   │
                    │  only in noise bins (mask≈0)        │
                    └─────────────────────────────────────┘
```

**Why KL divergence?** Beta-loss=2 (Frobenius) blurred the 18 Hz fundamental into the noise
floor. KL (beta=1) enforces sparse, parts-based decomposition - it prefers representations
where each component "owns" a narrow spectral region, which matches harmonic structure far
better than a least-squares solution.

**Why Top-K instead of a threshold?** With Frobenius loss, `harmonic_pattern_score` clustered
tightly in 0.45–0.55, causing the 0.35 threshold to select all 10 components, collapsing the
mask to all-ones (0 dB improvement). Top-K is invariant to score distribution shift.

**Generator comb notch design:**
```
notch_mask = 1 - (1 - notch_ratio) × (1 - mask)
  mask=1 (elephant bin):  notch_mask = 1     → zero attenuation
  mask=0 (noise bin):     notch_mask = notch_ratio → full notch
```
The previous formulation `mask × notch_ratio` gutted the 3rd harmonic of 20 Hz elephants
whenever it landed on 60/120/180 Hz. The new formulation gates notch application on mask value.

---

### Stage 4 · ReconstructionAgent

Noise masking can destroy harmonics that happen to fall inside a loud noise band. This stage
fits a decay model to the surviving harmonic series and reconstructs missing bands.

```
  cleaned_mag = magnitude × mask    ← Wiener output from Stage 3

  For each harmonic n = 1..24:
      h_energy[n] = mean(cleaned_mag[F0·n ± 3 Hz, :])

  Require ≥ 3 surviving harmonics, then fit log-linear decay:
      log(E_n) = a·n + b        (polyfit degree 1 on log scale)
      ⟺  E_n ≈ exp(b) · exp(a·n)   (exponential decay in linear scale)

  For each harmonic where actual < expected × 0.20 (damaged):
      find nearest healthy neighbor harmonic (energy > expected × 0.5)
      scale its STFT bins to expected energy:
          recon = cleaned_mag[neighbor_bins] × (expected / E_neighbor)
      blend:  cleaned_mag[target] = 0.3·recon + 0.7·cleaned_mag[target]
              (conservative - trust Wiener mask, only nudge toward expected)

  ISTFT(cleaned_mag × exp(i·phase))  →  cleaned audio
  length-matched to input segment (ISTFT rounding ±few samples corrected)
```

---

### Stage 5 · OverlapAgent

Detects simultaneous callers and separates them via competitive Wiener masking.

```
  STFT magnitude from Stage 3
      │
      ▼ mean over time frames → F0 energy profile [10–35 Hz]
      │
      ▼ scipy.signal.find_peaks(height=max×0.50, distance=5 bins)
      │
      ├─ < 2 peaks  →  single caller path (pass through)
      │
      └─ ≥ 2 peaks:
            secondary peak must satisfy:
              energy_ratio  ≥ 0.40  (not a sidelobe)
              sec_harmonics ≥ 3     (own harmonic series above 3×median floor)
              |F0_a - F0_b| ≥ 5 Hz  (Poole 2005 - below this = harmonics of same caller)

            if all three pass → multi_elephant = True

  Dual-elephant separation (competitive Wiener):
      cleaned_mag = magnitude × mask      ← operate in frequency domain
      NMF(cleaned_mag, n_components=8, KL loss, max_iter=800)
      W: (freq_bins × 8)   H: (time_frames × 8)

      score_a[k] = count harmonics of F0_a in W[:,k] above local floor×2
      score_b[k] = count harmonics of F0_b in W[:,k] above local floor×2

      sig_a = (W × score_a) @ Hᵀ     ← weighted spectral energy per elephant
      sig_b = (W × score_b) @ Hᵀ

      mask_a = (sig_a / (sig_a + sig_b))²   ← squared = bin hardening
      mask_b = (sig_b / (sig_a + sig_b))²

      cleaned_a = ISTFT(cleaned_mag × mask_a × exp(i·phase))
      cleaned_b = ISTFT(cleaned_mag × mask_b × exp(i·phase))
```

**Insight:** within a single call, harmonics never cross. When two callers overlap, their
harmonics do cross - each NMF component scores higher for one F0 than the other, giving the
competitive mask a natural per-component "ownership" to exploit.

---

### Stage 6 · QualityScorerAgent

```
  For both original and cleaned segments:
      scipy.signal.welch(fs=4000, nperseg=2048)  →  freqs, PSD

  Tonal SNR (harmonic-vs-inter-harmonic, preferred):
      for k = 1..15:
          harm_pow    += PSD[F0·k ± 2.5 Hz].max()
          between_pow += PSD[F0·k+3 : F0·k+(F0-3) Hz].mean()
      SNR_dB = 10·log10(mean_harm_pow / mean_between_pow)

  Fallback SNR (broadband, when F0 unknown):
      SNR_dB = 10·log10(mean(PSD[10–150Hz]) / mean(PSD[300–1000Hz]))

  Safety revert: if SNR_after < SNR_before − 0.1 dB
      → output = original segment (pipeline made it worse, silently revert)

  Harmonic completeness:
      noise_floor = max(mean(PSD_cleaned[300–1000Hz]),
                        mean(PSD_orig[300–1000Hz]) × 0.10)
      for n = 1..20 (while F0·n ≤ 1000 Hz):
          h_present++ if PSD_cleaned[F0·n ± 3Hz].max() > noise_floor × 4

      completeness = h_present / h_possible

  valid = (F0 ≥ 10 Hz) and (completeness ≥ 0.20) and (SNR_after > −20 dB)

  SenseCAP event: { detected, confidence=(SNR_after+40)×2, f0_hz, noise_type }
```

**Why tonal SNR?** A plain band-energy SNR goes negative when generator RPM harmonics and
elephant harmonics share the same spectral band - the NMF correctly removes the in-band noise
but the broadband ratio sees less energy and reports degradation. Harmonic-vs-inter-harmonic
measures only the bins that matter.

---

### Stage 7 · ClusteringAgent

```
  Feature vector per valid call (8 dimensions):
    [f0_hz, duration_s, harmonics_present, harmonic_completeness,
     snr_after_db, snr_improvement_db, multi_elephant_flag, f0_b]

  Optional context columns from timestamps.csv (15 fields):
    elephant_id · age_class · age · sex · location · location_id
    camera_id · recorder_id · recording_device
    relationship · relationship_group · family_group · clan
    breeding_context · breeding_target · call_type
    → one-hot encoded and horizontally stacked with acoustic features

  Pipeline:
    StandardScaler → UMAP(n_components=2, n_neighbors=10, min_dist=0.1)
                                     or PCA(n_components=2) fallback
    K-means(k = min(7, n_valid//3), n_init=10, random_state=42)

  Tribe similarity graph:
    acoustic_sim[i,j] = cosine_similarity(acoustic_feature_i, acoustic_feature_j)
    meta_sim[i,j]     = weighted field overlap:
                          elephant_id×4 · family_group×3 · clan×3
                          sex×2 · age_class×2 · location×2 · breeding_context×2
                          call_type×1 · camera_id×1 ...
    combined = 0.70·acoustic_sim + 0.30·meta_sim
    edge kept if combined ≥ 0.72 OR meta_sim ≥ 0.80

  Gemini 1.5 Flash prompt: cluster profiles with mean F0, duration,
    harmonics, SNR → behavioral hypothesis per cluster + individual ID
    inference (similar F0 = similar body size → same individual)
```

---

## Technology Stack

| Layer | Library / Tool | Version | Role |
|---|---|---|---|
| Audio I/O | `librosa` | ≥ 0.10 | WAV load, resample (soxr_hq), STFT, ISTFT |
| DSP | `scipy` | ≥ 1.11 | butter bandpass, sosfiltfilt, Welch PSD, iircomb notch, find_peaks |
| Source separation | `scikit-learn` NMF | ≥ 1.3 | KL-divergence NMF, KMeans, StandardScaler, cosine_similarity |
| Dimensionality reduction | `umap-learn` | ≥ 0.5 | UMAP 2D projection (PCA fallback) |
| AI hypotheses | `google-generativeai` | ≥ 0.7 | Gemini 1.5 Flash behavioral analysis |
| Spectrogram output | `matplotlib` | ≥ 3.7 | Before/after comparison PNGs |
| Noise reduction | `noisereduce` | ≥ 3.0 | Spectral gating (auxiliary) |
| Serial / IoT | `pyserial` | ≥ 3.5 | SenseCAP Indicator USB serial (115200 baud) |
| Edge streaming | `paho-mqtt` | ≥ 1.6 | MQTT publish from Raspberry Pi edge listener |
| Live capture | `sounddevice` | ≥ 0.4.6 | Microphone capture on Raspberry Pi |
| Graph analysis | `networkx` | ≥ 3.0 | Tribe similarity graph |
| Concurrency | Python `multiprocessing` | stdlib | Process-per-agent, mp.Queue message passing |
| Upload server | Python `http.server` | stdlib | WAV upload, base64 decode, CSV entry, pipeline spawn |
| Env config | `python-dotenv` | ≥ 1.0 | GEMINI_API_KEY, CSV_PATH, OUTPUT_DIR |

---

## Signal Parameters

```python
# DO NOT change without re-tuning harmonic scoring -
# TARGET_SR, N_FFT, HOP_LENGTH are tightly coupled.

TARGET_SR          = 4000    # Hz → 1.953 Hz/bin at n_fft=2048
N_FFT              = 2048
HOP_LENGTH         = 512     # 87.5% overlap
N_COMPONENTS       = 10      # NMF basis vectors
TOP_K_ELEPHANT     = 2       # top-K components classified as elephant
ELEPHANT_SCORE_MIN = 0.15    # absolute score floor (prevents all-ones mask on silent files)
PROP_DECREASE      = 0.90    # noise weight in Wiener denominator
MASK_FLOOR         = 0.25    # hard gate before rescaling
TEMPORAL_WEIGHT    = 0.35    # fraction of combined score from temporal non-stationarity
SPECTRAL_SUB_ALPHA = 1.25    # noise reference subtraction strength (car + airplane)
SPECTRAL_SUB_FLOOR = 0.22    # minimum fraction of original magnitude after subtraction
BANDPASS_LOW       = 10      # Hz
BANDPASS_HIGH      = 1000    # Hz
F0_MIN / F0_MAX    = 10/35   # elephant fundamental range (Hz)
CONTEXT_SEC        = 1.5     # padding on each side of call for STFT framing
NOISE_REF_SEC      = 3.0     # seconds of pre-call noise for spectral subtraction
```

---

## Repository Layout

```
rumbleos/
  agents/
    preprocess.py        Stage 1 - load, resample, bandpass, segment
    fingerprint.py       Stage 2 - Welch PSD comb/ratio classifier
    nmf_masking.py       Stage 3 - spectral subtraction + NMF + Wiener mask
    reconstruction.py   Stage 4 - exponential decay harmonic reconstruction
    overlap.py           Stage 5 - dual F0 detection + competitive Wiener separation
    quality_scorer.py    Stage 6 - tonal SNR, harmonic completeness, validity
    clustering.py        Stage 7 - UMAP + K-means + Tribe graph + Gemini
    sensecap.py          SenseCAP Indicator serial event streamer
    base.py              BaseAgent (multiprocessing.Process + queue wiring)
    runtime.py           OpenBLAS thread-count config for RPi
    serialization.py     dict → CSV-safe scalar extraction
  edge/
    listen.py            Raspberry Pi live capture (sounddevice + MQTT)
  data/
    timestamps.csv       call index: filename, start_time, end_time, noise_type
  results/               output WAVs, spectrograms, CSVs, JSON, hypotheses
  main.py                pipeline launcher (sequential / parallel / full-file)
  server.py              HTTP upload server (port 5050)
  gen_hypotheses.py      standalone Gemini hypothesis regenerator
  requirements.txt

frontend/
  src/
    main.js              routing, data loading, section rendering
    network-graph/       Sigma.js + ForceAtlas2 knowledge graph (React/TS)
    components/ui/       shared UI components
  index.html
  vite.config.js         serves /results/* from rumbleos/results/
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

### Environment

Create `.env` in the project root:

```
GEMINI_API_KEY=your_key_here
AUDIO_DIR=data/recordings
CSV_PATH=data/timestamps.csv
OUTPUT_DIR=results
```

---

## Running

### Pipeline modes

```python
# main.py - configure at the top:
SEQUENTIAL_MODE = True    # single process, full tracebacks (debug)
FULL_FILE_MODE  = True    # clean entire recording vs. per-call windows only
N_WORKERS       = 4       # parallel agents (ignored in SEQUENTIAL_MODE)
```

```bash
cd rumbleos
python main.py
```

### Upload server

```bash
python server.py    # http://localhost:5050
# POST /api/upload  body: { filename: "rec.wav", data: "<base64>" }
# POST /api/run     re-run pipeline on existing files
# GET  /api/status  { status, logs[], progress }
```

### Frontend

```bash
cd frontend
npm run dev        # http://localhost:5174
```

---

## Deploying

### Backend on Render

Use the included `render.yaml`, or create a Python Web Service with:

```bash
Build Command: pip install -r rumbleos/requirements.txt
Start Command: cd rumbleos && python server.py
Health Check Path: /api/status
```

Set these environment variables on Render:

```bash
AUDIO_DIR=data/recordings
CSV_PATH=data/timestamps.csv
OUTPUT_DIR=results
GEMINI_API_KEY=your_key_here   # optional
```

### Frontend on Vercel

Deploy the `frontend/` directory as a Vite app, then replace `YOUR_RENDER_URL`
in `frontend/vercel.json` with your Render service URL so `/api/*` and
`/results/*` proxy to the backend.

### Gemini hypotheses (standalone)

```bash
cd rumbleos
python gen_hypotheses.py
```

---

## Outputs

| File | Description |
|------|-------------|
| `*_clean.wav` | Full-length denoised recording; non-elephant regions silent |
| `*_comparison.png` | Before/after spectrogram per call with F0 harmonic overlays |
| `batch_results.csv` | Per-call scalars: SNR before/after, F0, completeness, valid, cluster |
| `batch_results_clustered.csv` | Same + UMAP x/y coordinates |
| `tribe_edges.csv` | Call-pair similarity graph edges (combined score ≥ 0.72) |
| `cluster_summaries.json` | Per-cluster: count, mean F0, duration, harmonics, SNR, member IDs |
| `knowledge_base.json` | Full structured call database with context, UMAP coords, links |
| `ai_hypotheses.txt` | Gemini behavioral interpretation of each cluster |

---

## Edge Device (Raspberry Pi)

`edge/listen.py` captures 10-second chunks at 4 kHz via `sounddevice`, applies the
bandpass, and pushes to a local queue or publishes over MQTT for remote processing.

On Pi, reduce memory pressure:

```python
N_WORKERS = 2
# in agents/nmf_masking.py: max_iter=200
```

```bash
sudo apt install libsndfile1
```

---

## Smoke Test

```bash
cd rumbleos
python -c "
import numpy as np; from agents.nmf_masking import NMFMaskingAgent
sr=4000; t=np.linspace(0,10,40000)
sig=sum(np.sin(2*np.pi*18*n*t)/n for n in range(1,8))
noisy=sig+np.random.randn(len(t))*0.5
r=NMFMaskingAgent(0,None,None,name='T').process(
    {'segment':noisy,'sr':sr,'noise_type':'airplane',
     'original':noisy,'call_id':'t','noise_ref':np.zeros(sr*3)})
assert 14<=r['detected_f0']<=22, r['detected_f0']
print('Stage 3 OK - F0=', r['detected_f0'])
"
```

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
| Gemini 429 quota | Free tier limit - retry after 60 s or rotate key |
| All-ones mask (0 dB) | Raise `ELEPHANT_SCORE_MIN`; check `TOP_K_ELEPHANT` |

---

## Research Foundation

- Payne et al. (1986) - infrasonic calls of the Asian elephant
- Poole et al. (1988) - social contexts of low-frequency elephant calls  
- Poole (2005) - F0 range and ≥ 5 Hz gap between simultaneous callers
- Lee & Seung (1999) - NMF for parts-based representations
- Févotte et al. (2009) - NMF with KL divergence (beta=1 multiplicative updates)
- Scalart & Filho (1996) - Wiener filter from a priori SNR estimation
- McInnes et al. (2018) - UMAP: Uniform Manifold Approximation and Projection
