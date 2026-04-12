# RumbleOS

A multi-agent signal processing system that removes mechanical noise from elephant
infrasound recordings and discovers behavioral communication patterns. Built for
HackSMU 2026.

---

## What It Does

Elephants communicate through infrasound — low-frequency rumbles (10–35 Hz fundamental,
harmonics extending to ~1000 Hz) inaudible to humans. Field recordings of these calls
are almost always contaminated by airplane flyovers, vehicle engines, or generator hum
at overlapping frequencies, making them difficult to analyze scientifically.

RumbleOS takes raw, noisy WAV files and:

1. Automatically classifies the noise type (airplane, car, generator)
2. Runs a full-file NMF-based Wiener mask to suppress noise across the entire recording
3. Reconstructs harmonics that were damaged by the noise
4. Detects whether two elephants were calling simultaneously and separates them
5. Scores each call for SNR improvement and harmonic completeness
6. Clusters all calls by acoustic signature and asks Claude to generate behavioral hypotheses

The output is a clean WAV per recording (non-elephant regions silenced), per-call
spectrograms, a tribe similarity graph, cluster summaries, and optional AI-generated
behavioral notes.

---

## Architecture

### Design Philosophy

The system is a **message-passing pipeline of independent OS processes**. Each stage
is a `BaseAgent` subclass that extends `multiprocessing.Process`. Stages communicate
by passing plain Python `dict` objects through `mp.Queue` pipes. No shared memory.
No global state. If one stage crashes it forwards an `error` key and the pipeline
keeps moving — nothing silently stalls.

```
WAV files
    |
    v
[PreprocessAgent]      Stage 1 — load, downsample 4kHz, bandpass, extract segment
    |
    v
[FingerprintAgent]     Stage 2 — classify noise: airplane / car / generator_Nhz
    |
    v
[NMFMaskingAgent]      Stage 3 — STFT -> NMF -> harmonic scoring -> Wiener mask  <-- core ML
    |
    v
[ReconstructionAgent]  Stage 4 — fit exponential decay, reconstruct damaged harmonics
    |
    v
[OverlapAgent]         Stage 5 — detect dual callers, competitive Wiener separation
    |
    v
[QualityScorerAgent]   Stage 6 — SNR before/after, harmonic completeness, validity flag
    |
    v
[ClusteringAgent]      Stage 7 — UMAP + K-means, Tribe graph, Claude API hypotheses

[SenseCapAgent]        Parallel — streams live detection events to SenseCAP Indicator
```

### Two Execution Modes

| Mode | Flag | Use |
|------|------|-----|
| `FULL_FILE_MODE = True` | default | Single-shot NMF over the entire WAV file — the model decides what to keep |
| `FULL_FILE_MODE = False` | legacy | Per-call windowed processing gated by timestamps.csv |

Full-file mode is the correct production mode. The timestamps.csv is used only as a
reference for per-call scoring and clustering metrics — it is **not** a processing gate.
The NMF runs once over the whole signal, and the mask values determine what survives.
This means no artificial cuts and no human-defined windows — if the model finds elephant
signal somewhere, it keeps it; everything else is silenced.

### Key Parameters

```python
TARGET_SR      = 4000    # 4 kHz gives 1.95 Hz/bin at n_fft=2048
N_FFT          = 2048    # STFT window
HOP_LENGTH     = 512     # STFT hop
N_COMPONENTS   = 10      # NMF basis vectors
TOP_K_ELEPHANT = 2       # top-K components classified as elephant
MASK_FLOOR     = 0.25    # hard-zero bins below this in the Wiener mask
BANDPASS       = 10-1000 Hz
F0_RANGE       = 10-35 Hz   # elephant fundamental range
```

Do not change `TARGET_SR`, `N_FFT`, or `HOP_LENGTH` without re-tuning harmonic
scoring thresholds — these three constants are tightly coupled.

---

## Pipeline Stages In Detail

### Stage 1 — PreprocessAgent

Loads the WAV at native sample rate, records channel count and duration, then:

- Downsamples to 4 kHz mono (soxr_hq resampler) for the NMF pipeline
- Applies a 4th-order Butterworth bandpass (10–1000 Hz)
- Extracts a call segment with 1.5 s context padding on each side
- Extracts 3 s of pre-call audio as a noise reference for spectral subtraction

The native-SR buffer is released immediately after metadata is recorded. Output WAVs
are reconstructed by reloading from disk at write time, avoiding queue bloat.

**Why 4 kHz?** The highest elephant harmonic of interest is ~1000 Hz. Nyquist requires
2 kHz minimum; 4 kHz gives a clean margin. At n_fft=2048 this yields ~1.95 Hz/bin —
enough frequency resolution to resolve the 10–35 Hz F0 band unambiguously.

### Stage 2 — FingerprintAgent

Classifies noise type from the spectral power distribution using Welch's method:

- **Generator**: sharp harmonic spikes at exact multiples of 45, 60, or 90 Hz (engine RPM)
- **Airplane**: broadband energy concentrated in 80–200 Hz, smooth log-PSD curve
- **Car**: quasi-harmonic, non-stationary, variable RPM

If `noise_type` is already set in the message (from timestamps.csv ground truth), this
stage is a no-op. The heuristic only fires on unlabeled live audio.

### Stage 3 — NMFMaskingAgent (Core ML)

This is the primary noise removal stage. It runs the following sequence:

**Step 1: Spectral subtraction**
For car and airplane noise, a noise spectrum is estimated from the 3 s pre-call
noise reference. The median spectrum of that reference is subtracted from the signal
magnitude, with a floor at 22% of original magnitude to prevent musical noise artifacts:

```
mag_clean = max(mag - alpha * noise_spectrum, mag * 0.22)
```

Generators skip spectral subtraction and use a comb notch filter instead (see below).

**Step 2: NMF decomposition**
Non-negative Matrix Factorization with Kullback-Leibler divergence loss decomposes
the noise-subtracted magnitude spectrogram into 10 basis vectors W (spectral patterns)
and 10 activation matrices H (time patterns):

```
V ≈ W @ H.T      (freq_bins x time_frames)
```

KL divergence is used instead of Frobenius norm because KL encourages sparse,
parts-based representations — critical for separating narrowband harmonics from
broadband noise.

**Step 3: Component scoring**
Each NMF component k gets a combined score:

```
score[k] = 0.65 * harmonic_score(W[:,k]) + 0.35 * temporal_score(H[:,k])
```

- `harmonic_score`: measures how well W[:,k] fits an integer harmonic series rooted
  in 10–35 Hz. Requires peaks at f0*n within ±1.5 Hz, above 3.5x the 25th-percentile
  floor. Elephant calls score high; car engine harmonics also score high on this alone.

- `temporal_score`: measures non-stationarity of H[:,k] via coefficient of variation
  (std/mean). Elephant calls are brief localized events — their activations spike and
  fall. Engine noise is quasi-stationary. This is the key discriminator that separates
  elephant harmonics from car/generator harmonics that pass the frequency test.

**Step 4: Wiener mask**
The top-2 highest-scoring components are classified as elephant signal. A soft Wiener
mask is computed from the ratio of elephant signal energy to total energy:

```
mask = e_signal / (e_signal + 0.90 * noise_signal + 1e-8)
```

Then hardened with a floor gate and squaring:

```python
mask = where(mask < 0.25, 0.0, (mask - 0.25) / 0.75)
mask = mask ** 2
```

Squaring preserves high-confidence bins (0.9^2 = 0.81) while collapsing ambiguous
bins (0.3^2 = 0.09). This silences residual noise without hard blocking artifacts.

**Step 5: Generator comb filter**
For generator noise, an IIR comb notch filter targets the generator's fundamental
frequency. Critically, the notch is blended with the Wiener mask so elephant harmonics
that happen to fall on mains frequencies are protected:

```python
notch_mask = 1.0 - (1.0 - notch_ratio) * (1.0 - mask)
```

When `mask=1` (confirmed elephant bin), the notch has zero effect. When `mask=0`
(confirmed noise bin), full notch attenuation is applied.

### Stage 4 — ReconstructionAgent

Some harmonics are so heavily masked by noise that the Wiener mask suppresses them
along with the noise. This stage recovers them by:

1. Fitting a log-linear (exponential decay) curve to all surviving clean harmonics:
   `log(E_n) = a*n + b`

2. Any harmonic whose measured energy is below 20% of the expected value from this
   curve is considered "damaged." It is reconstructed by scaling the nearest healthy
   harmonic by the expected energy ratio.

3. The reconstruction is blended conservatively (30% new, 70% existing) to avoid
   over-synthesizing content that wasn't there.

Requires at least 3 surviving harmonics for a reliable curve fit.

### Stage 5 — OverlapAgent

Detects whether two elephants are calling simultaneously by looking for two distinct
F0 peaks in the 10–35 Hz band, at least 5 Hz apart, each with its own harmonic series
(>=3 harmonics above the local floor), with the secondary peak at least 40% of the
primary's energy.

If dual callers are detected, it runs a second NMF on the cleaned STFT magnitude,
scores each component against both F0s, then applies competitive Wiener separation:

```python
sig_a = (W * scores_a) @ H.T    # energy map for elephant A
sig_b = (W * scores_b) @ H.T    # energy map for elephant B

mask_a = (sig_a / (sig_a + sig_b + 1e-8)) ** 2
mask_b = (sig_b / (sig_a + sig_b + 1e-8)) ** 2
```

Each time-frequency bin is allocated proportionally to whichever elephant owns more
energy there. Two separate audio tracks are output: `cleaned` (elephant A) and
`cleaned_b` (elephant B).

The 5 Hz minimum gap between F0s comes from Poole (2005) — within a single caller's
harmonic series, no two harmonics ever land that close to each other at the fundamental.

### Stage 6 — QualityScorerAgent

Computes:

- **Tonal SNR** before and after cleaning — harmonic-vs-inter-harmonic power ratio
  at the detected F0. More robust than band-energy SNR for generator recordings where
  in-band noise at RPM frequencies would make a broadband ratio go negative even when
  the NMF correctly removed it.

- **SNR revert guard** — if the pipeline degraded SNR by more than 0.1 dB, the original
  unprocessed segment is restored. This protects calls where NMF misclassified noise
  as signal.

- **Harmonic completeness** — fraction of expected harmonics (up to 1000 Hz) present
  above 4x the noise floor. Uses the original PSD as a secondary noise floor reference
  so an aggressive Wiener mask doesn't collapse the threshold to zero and produce
  false invalids.

- **Validity flag** — `valid=True` when F0 >= 10 Hz, completeness >= 20%, SNR > -20 dB.

Also fires a live detection event to SenseCAP with confidence score, F0, and noise type.

### Stage 7 — ClusteringAgent

After all calls are scored, ClusteringAgent receives the full result set and:

1. Extracts 8 acoustic features per call: F0, duration, harmonics present, completeness,
   SNR before/after, multi-elephant flag, secondary F0.

2. Reduces to 2D with **UMAP** (falls back to PCA if unavailable).

3. Clusters with **K-means** (k = min(7, n_calls // 3)).

4. Builds a **Tribe similarity graph** — every pair of calls with cosine similarity
   > 0.80 in feature space gets an edge. The graph encodes which calls likely came
   from the same individual or behavioral context.

5. Optionally calls the **Claude API** (claude-sonnet-4-6) with cluster summaries to
   generate behavioral hypotheses about what each cluster represents biologically.

Outputs: `tribe_edges.csv`, `cluster_summaries.json`, `batch_results_clustered.csv`,
`ai_hypotheses.txt`.

---

## How to Use

### Install

```bash
pip install -r rumbleos/requirements.txt
```

### Configure paths

Open `rumbleos/main.py` and update the three path constants at the bottom:

```python
CSV_PATH   = r"C:\path\to\HACKSMU_26\rumbleos\data\timestamps.csv"
AUDIO_DIR  = r"C:\path\to\recordings"
OUTPUT_DIR = r"C:\path\to\HACKSMU_26\rumbleos\results"
```

### Add recordings

Put your WAV files flat inside `AUDIO_DIR` (no subfolders).

Edit `rumbleos/data/timestamps.csv` to cross-reference known calls:

```
filename,start_time,end_time,noise_type
my_recording.wav,15.2,22.7,car
```

`noise_type` values: `car`, `airplane`, `generator_60hz`, `generator_90hz`,
`generator_45hz`, `background`. Leave it blank to use the auto-classifier.

### Run

```bash
cd rumbleos
python main.py
```

Configure behavior at the top of `main.py`:

```python
SEQUENTIAL_MODE = True     # True = no multiprocessing, full tracebacks
FULL_FILE_MODE  = True     # True = clean entire file; False = per-call windows
N_WORKERS       = 4        # parallel workers (ignored in SEQUENTIAL_MODE)
```

Set `SEQUENTIAL_MODE = True` when developing. Multiprocessing swallows tracebacks.
Switch to `False` only for production runs over large batches.

### Outputs

All outputs go to `rumbleos/results/`:

| File | What it is |
|------|------------|
| `*_clean.wav` | Full-length denoised recording at native SR, non-elephant regions silent |
| `*_spectrogram.png` | Before/after spectrogram for each call |
| `batch_results.csv` | Per-call scalar metrics (SNR, F0, validity, cluster, etc.) |
| `batch_results_clustered.csv` | Same with UMAP coordinates added |
| `tribe_edges.csv` | Cosine-similarity graph edges between calls |
| `cluster_summaries.json` | Cluster centroids and member call IDs |
| `ai_hypotheses.txt` | Claude's behavioral interpretation (requires API key) |

### Dashboard

```bash
cd rumbleos
streamlit run dashboard/app.py
```

### Claude API hypotheses

Set `CLAUDE_API_KEY` in `main.py` to enable AI-generated behavioral notes per cluster,
saved to `results/ai_hypotheses.txt`.

---

## Best Way to Work on This

### Changing NMF / masking behavior

Everything that matters lives in `agents/nmf_masking.py`. The constants at the top
are the primary tuning knobs:

- `TOP_K_ELEPHANT` — how many NMF components count as elephant. Raise to recover
  more signal; lower to reduce noise leak.
- `MASK_FLOOR` — hard gate threshold. Lower = more signal passes but more noise too.
- `TEMPORAL_WEIGHT` — blend between harmonic score and temporal score. Raise it to
  be more aggressive about filtering stationary harmonics (engine noise that happens
  to be harmonic).
- `SPECTRAL_SUB_ALPHA_*` — how aggressively to subtract the noise reference spectrum.

Run the smoke test after any change:

```bash
python -c "
import numpy as np; from agents.nmf_masking import NMFMaskingAgent
sr=4000; t=np.linspace(0,10,40000)
sig=sum(np.sin(2*np.pi*18*n*t)/n for n in range(1,8))
noisy=sig+np.random.randn(len(t))*0.5
r=NMFMaskingAgent(0,None,None,name='T').process({'segment':noisy,'sr':sr,'noise_type':'airplane','original':noisy,'call_id':'t'})
assert 14<=r['detected_f0']<=22, r['detected_f0']
print('OK — F0=', r['detected_f0'])
"
```

### Adding a new pipeline stage

1. Create `agents/my_agent.py`, subclass `BaseAgent`, implement `process(self, msg)`.
2. `process` receives a dict, returns a dict — add your new keys, pass through the rest.
3. Wire it into `main.py`: add a queue between the upstream and downstream agents,
   instantiate your agent, call `.start()`, and send `SENTINEL` at shutdown.
4. Never mutate `msg` in place — always return `{**msg, "new_key": value}`.

### Debugging a specific stage

Set `SEQUENTIAL_MODE = True` in `main.py` and add print statements. With multiprocessing
enabled, exceptions in worker processes print to the console but stack traces are
truncated. Sequential mode runs all agents inline — full Python tracebacks.

You can also call any agent directly from a Python script or REPL:

```python
from agents.nmf_masking import NMFMaskingAgent
agent = NMFMaskingAgent(0, None, None, name="debug")
result = agent.process({"segment": audio, "sr": 4000,
                        "noise_type": "airplane", "original": audio, "call_id": "test"})
print(result['detected_f0'], result['mask'].mean())
```

### Modifying the clustering

The feature vector is in `ClusteringAgent.extract_features()`. Add any scalar field
from the result dict. If you add a new metric in `quality_scorer.py`, append it there.
K is auto-tuned to `min(7, n_valid // 3)` — override in `clustering.py` if you need
a fixed number of clusters.

### Edge device (Raspberry Pi)

The `edge/listen.py` script runs a live capture loop on the Pi. It reads from the
microphone with `sounddevice`, applies the same 4 kHz bandpass, and sends detection
events over a socket. The `SenseCapAgent` relays these to the SenseCAP Indicator
over USB serial at `/dev/ttyUSB0` (115200 baud). Try `/dev/ttyACM0` if the default
does not connect.

Set `N_WORKERS = 2` and `max_iter = 200` on the Pi to stay within memory constraints.

---

## Research Foundation

**Elephant infrasound and communication**
- Payne, K.B., Langbauer, W.R., Thomas, E.M. (1986). Infrasonic calls of the Asian
  elephant. *Behavioral Ecology and Sociobiology*, 18, 297–301.
- Poole, J.H., Payne, K., Langbauer, W.R., Moss, C.J. (1988). The social contexts
  of some very low frequency calls of African elephants. *Behavioral Ecology and
  Sociobiology*, 22, 385–392.
- Poole, J.H. (2005). *Elephant Voices*. ElephantVoices Project, Amboseli. Reference
  for F0 range, harmonic structure, and the >=5 Hz minimum gap between simultaneous
  callers used in OverlapAgent.

**NMF for audio source separation**
- Lee, D.D., Seung, H.S. (1999). Learning the parts of objects by non-negative matrix
  factorization. *Nature*, 401, 788–791.
- Fevotte, C., Bertin, N., Durrieu, J.L. (2009). Nonnegative matrix factorization
  with the Itakura-Saito divergence. *Neural Computation*, 21(3), 793–830. (basis for
  KL divergence NMF used here)
- Virtanen, T. (2007). Monaural sound source separation by nonnegative matrix
  factorization with temporal continuity and sparseness criteria. *IEEE TASLP*, 15(3).

**Wiener filtering**
- Scalart, P., Filho, J. (1996). Speech enhancement based on a priori signal to noise
  estimation. *ICASSP*, 351–354. (soft Wiener mask formulation)
- Ephraim, Y., Malah, D. (1984). Speech enhancement using a minimum mean-square error
  short-time spectral amplitude estimator. *IEEE TASP*, 32(6), 1109–1121.

**Spectral subtraction**
- Boll, S. (1979). Suppression of acoustic noise in speech using spectral subtraction.
  *IEEE Transactions on ASSP*, 27(2), 113–120.

**UMAP dimensionality reduction**
- McInnes, L., Healy, J., Melville, J. (2018). UMAP: Uniform Manifold Approximation
  and Projection for Dimension Reduction. *arXiv:1802.03426*.

---

## Requirements

```
numpy>=1.24       scipy>=1.11       librosa>=0.10
scikit-learn>=1.3 matplotlib>=3.7   sounddevice>=0.4.6
pyserial>=3.5     paho-mqtt>=1.6    streamlit>=1.28
pandas>=2.0       plotly>=5.0       networkx>=3.0
anthropic>=0.25   umap-learn>=0.5   noisereduce>=3.0
```

Python 3.10+. Tested on Ubuntu 22.04 and Windows 11.
On Raspberry Pi, run `sudo apt install libsndfile1` before `pip install soundfile`.

---

## Common Errors

| Error | Fix |
|-------|-----|
| `librosa.load` fails | `pip install soundfile` |
| `iircomb` not found | `pip install "scipy>=1.9"` |
| NMF slow | Set `max_iter=200` for testing |
| SenseCAP not connecting | Try `/dev/ttyACM0` instead of `/dev/ttyUSB0` |
| UMAP install fails | Falls back to PCA automatically |
| Queue deadlock | Set `SEQUENTIAL_MODE = True` |
| Out of memory on Pi | Set `N_WORKERS=2`, `max_iter=200` |
| NMF F0 wrong | Verify `sr=4000`, `n_fft=2048`; increase `max_iter` to 600 |
