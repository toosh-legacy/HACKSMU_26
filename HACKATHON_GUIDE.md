# RumbleOS — Hackathon Deep Dive Guide

This is your personal study doc. Read it front to back once, then use it as a reference
when judges ask specific questions. Every section ends with likely judge questions and
how to answer them.

---

## The Problem (Start Here)

Elephants talk in infrasound — frequencies below 20 Hz, completely inaudible to humans.
Their calls have a fundamental frequency (F0) between 10–35 Hz and harmonics that stack
up to about 1000 Hz. These calls travel kilometers through the ground and air, used for
coordinating herd movement, warning of danger, finding mates, and greeting each other.

Researchers record these calls in the field. The recordings almost always have mechanical
noise layered on top — airplane flyovers, vehicle engines idling nearby, diesel generator
hum. These noise sources happen to occupy the same frequency range as elephant calls.
This isn't a coincidence: low frequencies travel far, and both engines and elephant vocal
cords produce harmonically structured sounds.

The result: scientists have thousands of recordings they can't fully analyze because the
signal is buried.

**The gap RumbleOS fills:** automated noise removal that understands elephant acoustics
specifically, not generic audio denoising. Generic denoisers (like noise gates or
spectral subtraction alone) don't know that 18 Hz and 36 Hz and 54 Hz are related —
they treat every frequency bin independently and end up either over-suppressing signal
or under-suppressing noise.

---

## The Core Insight

The entire system is built on one central insight:

> **Elephant calls and mechanical noise both look harmonic in frequency, but they behave
> completely differently in time.**

A car engine idling at 600 RPM produces harmonics at 10, 20, 30, 40 Hz — nearly
identical to an elephant rumble. If you look at just one frame of STFT, you cannot
distinguish them.

But if you look across time:
- The engine harmonics are **stationary** — constant energy, every frame, for the
  whole recording.
- The elephant call is a **brief localized event** — it rises, peaks, and falls over
  2–6 seconds.

NMF finds this difference automatically. It decomposes the spectrogram into basis
patterns (what frequencies are active) and activation patterns (when they are active).
An engine component has a flat activation pattern. An elephant component has a spike.
The temporal score in Stage 3 exploits exactly this distinction.

---

## Architecture: How Data Flows

### The Message-Passing Pipeline

RumbleOS is not a monolithic script. It's a chain of independent OS processes — each
one a Python `multiprocessing.Process` — that pass data to each other through queues.

```
             mp.Queue          mp.Queue          mp.Queue
[Preprocess] -------> [NMF] -------> [Reconstruct] -------> [Quality] ...
```

Each agent:
1. Waits on its input queue (`in_queue.get()`)
2. Receives a Python dict (the "message")
3. Does its work and adds new keys to the dict
4. Puts the result on its output queue (`out_queue.put(result)`)
5. Never touches shared memory — everything lives inside the dict

This architecture is called a **staged pipeline** or **actor model**. Why do it this way?

- **Isolation**: if NMF crashes on one recording, the error is caught, tagged with
  `"error": str(e)`, and forwarded. The pipeline keeps going. Nothing stalls silently.
- **Parallelism**: with N_WORKERS=4, four recordings are processed simultaneously
  across all stages. The queues act as natural backpressure buffers.
- **Debuggability**: set `SEQUENTIAL_MODE = True` and the whole thing runs inline,
  one call at a time, with full Python tracebacks.

### The Message Dict

Every message is just a Python dict. Keys accumulate as the message passes through stages:

```python
# After PreprocessAgent:
{
    "call_id":           "1989-08_airplane_01_c021",
    "audio_path":        "/path/to/file.wav",
    "start_time":        18.0,
    "end_time":          22.5,
    "noise_type":        "airplane",
    "segment":           np.array([...]),   # 4kHz bandpassed audio
    "original":          np.array([...]),   # copy before any processing
    "noise_ref":         np.array([...]),   # 3s of pure noise before call
    "sr":                4000,
    "source_sr":         48000,
    "source_len":        2160000,
    "n_channels":        1,
    ...
}

# After NMFMaskingAgent adds:
{
    ...,
    "magnitude":         np.array([...]),   # STFT magnitude (freq x time)
    "phase":             np.array([...]),   # STFT phase
    "mask":              np.array([...]),   # Wiener mask values 0-1
    "nmf_scores":        [0.12, 0.45, ...], # per-component scores
    "detected_f0":       19.5,              # Hz
}

# After QualityScorerAgent adds:
{
    ...,
    "snr_before_db":     -3.2,
    "snr_after_db":      3.8,
    "snr_improvement_db": 7.0,
    "f0_hz":             19.5,
    "harmonic_completeness": 0.65,
    "valid":             True,
}
```

### Full-File Mode vs Per-Call Mode

**Per-call mode (old):** read timestamps.csv, cut out a 5-second window around each
documented call, run NMF on that window, splice result back in. Problem: you're only
cleaning known calls. Everything between documented calls stays noisy.

**Full-file mode (current):** ignore the timestamps as a processing gate. Load the
entire WAV file, run one NMF over the whole thing, let the mask decide what's elephant
and what's noise across every second of the recording. The timestamps are only used
afterward to extract per-call metrics for clustering.

This is a fundamentally different philosophy: **the model is the gating mechanism,
not the human annotations.** If there's an undocumented call somewhere in the file,
the NMF mask will preserve it. If there's engine noise between calls, it gets silenced.

---

## Stage 1: PreprocessAgent — Setting Up the Signal

### What it does

Loads the WAV file, prepares two versions of the audio:

1. **Native SR recording** — metadata only (sample rate, length, channel count).
   The buffer is immediately released to avoid carrying 48kHz stereo arrays through
   every queue hop.
2. **4kHz bandpassed mono** — the working signal that all ML stages process.

### Why 4 kHz?

Elephant harmonics of interest top out around 1000 Hz. The Nyquist theorem says you
need a sample rate at least 2× your highest frequency of interest. 2 kHz is the
minimum; 4 kHz gives a comfortable margin.

At 4 kHz with n_fft=2048, each frequency bin is:

```
bin_width = sample_rate / n_fft = 4000 / 2048 = 1.95 Hz
```

This means bins are about 2 Hz wide — fine enough to resolve a 10 Hz F0 cleanly,
and to place each harmonic in its own bin without overlap.

### The bandpass filter

A 4th-order Butterworth bandpass (10–1000 Hz) is applied before NMF. This removes
DC offset and any ultrasonic content that survived the downsampling. Butterworth is
chosen because it has a maximally flat passband — no ripple in the 10–1000 Hz range
the NMF will analyze. The `sosfiltfilt` function applies it zero-phase (forward and
backward) so there's no time-domain shift in the filtered signal.

### Context padding

When processing in per-call mode, a 1.5 s pad is added before and after the call
window. This gives the STFT/NMF enough temporal context to fit basis vectors accurately.
The pad is stripped before writing to the output file. In full-file mode, the whole
recording is the context, so no padding is needed.

### Noise reference

3 seconds of audio immediately before the call start are extracted as `noise_ref`.
This is assumed to contain pure mechanical noise with no elephant content. It's used
in Stage 3 for spectral subtraction. If there isn't enough audio before the call
(file starts too close to the call), a zero array is used as fallback.

**Judge question: "Why 3 seconds for the noise reference?"**
> Three seconds at 4 kHz gives 12,000 samples. At n_fft=2048 and hop=512, that's
> about 23 STFT frames — enough to compute a stable median noise spectrum that isn't
> dominated by any single transient event. Too short and one noise spike skews the
> reference; too long and you risk including part of the elephant call.

---

## Stage 2: FingerprintAgent — Classifying the Noise

### Why classify noise type?

Different noise sources need different removal strategies:
- **Car engines** produce quasi-harmonic noise that moves in frequency as the RPM
  changes. Spectral subtraction works well because it's broadband.
- **Airplanes** produce very stable broadband hum at 80–200 Hz. Same strategy.
- **Generators** produce exact integer harmonics of a fixed RPM frequency (60 Hz for
  60Hz power grid, etc.). These need a comb notch filter to surgically remove each
  harmonic spike without touching everything around it.

### How it classifies

Uses **Welch's method** to estimate the power spectral density (PSD) of the audio.
Welch's method averages multiple overlapping periodograms — much more stable than a
single FFT. Then:

1. Check for generator: look for strong peaks at exact multiples of 45, 60, and 90 Hz.
   A real generator produces at least 6 harmonics all significantly above the local
   noise floor.
2. Check for airplane: broadband energy concentrated in 80–200 Hz with a smooth
   log-PSD curve (low standard deviation of the log-derivative).
3. Default to car.

If `noise_type` is already set in the message (from timestamps.csv), this whole stage
is skipped — the ground truth label is trusted.

**Judge question: "What if the classifier gets it wrong?"**
> The fallback is graceful. Car and airplane use the same spectral subtraction
> strategy with the same alpha value — misclassifying one as the other has minimal
> impact. The critical distinction is generator vs. non-generator, because generators
> need the comb notch filter. A false generator classification adds a notch filter
> where it isn't needed, which could hurt signal. This is why generator detection
> requires 6+ confirmed harmonics — a conservative threshold. In practice, the
> timestamps.csv has the ground truth for all 44 known files, so the classifier is
> only active for live/unlabeled audio.

---

## Stage 3: NMFMaskingAgent — The Core ML Stage

This is the heart of the system. Understand this deeply.

### Step 1: The STFT

Short-Time Fourier Transform converts the 1D audio signal into a 2D spectrogram:

```
signal (samples) --> STFT --> magnitude spectrogram (freq_bins x time_frames)
                          --> phase spectrogram    (freq_bins x time_frames)
```

With n_fft=2048 and hop=512: the spectrogram has 1025 frequency bins (0 to 2000 Hz)
and one frame per 128ms of audio (512 samples / 4000 Hz). The magnitude tells us
how much energy is at each frequency at each moment. The phase tells us the exact
waveform shape — needed later to reconstruct audio via ISTFT.

**Why keep phase?** The STFT splits energy into magnitude and phase. We process only
the magnitude (NMF can't handle complex numbers). When we reconstruct audio, we
multiply the cleaned magnitude by the original phase: `cleaned = mag * mask * e^(j*phase)`.
The original phase is the best estimate of the true signal's phase — using it avoids
introducing artifacts.

### Step 2: Spectral Subtraction

Before NMF, a coarse noise floor is subtracted. The noise reference from Stage 1
(3 s of pure engine noise) is transformed into a median spectrum:

```python
D_noise = librosa.stft(noise_ref)
noise_spectrum = median(|D_noise|, axis=time)   # one value per freq bin
```

This median spectrum is the "typical noise level" at each frequency. We subtract a
scaled version from the signal magnitude:

```python
mag_clean = signal_magnitude - alpha * noise_spectrum
```

`alpha = 1.25` for both car and airplane — slightly over-subtract to push noise below
zero, then floor-clip:

```python
mag_for_nmf = max(mag_clean, signal_magnitude * 0.22)
```

The 0.22 floor prevents "musical noise" — isolated random bins that survive subtraction
and create a fluttery artifact. Setting a floor at 22% of original keeps a residual
that sounds like low-level static rather than chirping.

**Why doesn't this just solve the problem by itself?**
Spectral subtraction removes the average noise floor. But elephant calls are embedded
in noise that varies in time — sometimes the engine gets louder, sometimes quieter.
Subtraction removes the mean but leaves the variance. NMF handles the rest.

### Step 3: NMF Decomposition

Non-negative Matrix Factorization factorizes the spectrogram matrix V into two
non-negative matrices:

```
V ≈ W @ H.T

V: (1025 freq_bins  x  time_frames)  — the input spectrogram
W: (1025 freq_bins  x  10 components) — spectral basis vectors (what)
H: (time_frames     x  10 components) — temporal activations (when)
```

Each component k represents one "sound source": W[:,k] is its spectral fingerprint
(which frequencies it uses) and H[:,k] is its temporal envelope (when it's active).

The factorization uses **Kullback-Leibler divergence** as the loss function. This
measures how well W@H.T explains V in a relative (ratio) sense rather than absolute
(difference) sense. For audio, KL is better than Frobenius (squared difference) because:
- Audio energy spans many orders of magnitude — a 0.01 difference at 100 dB matters
  less than at 20 dB
- KL naturally produces sparser, more parts-based representations
- Harmonics (which are multiplicatively related) are better modeled in log-space

The algorithm iterates multiplicative update rules until convergence (up to 800
iterations, tolerance 1e-3). The `nndsvda` initialization uses a deterministic
SVD-based seed that's much faster to converge than random initialization.

### Step 4: Harmonic Pattern Score

For each NMF component k, we ask: does W[:,k] look like elephant harmonics?

```python
def harmonic_pattern_score(w_col, freqs):
    # Find the peak in the 10-35 Hz range (the F0)
    f0 = freqs[argmax(w_col[10-35Hz mask])]

    # Check for peaks at f0, 2*f0, 3*f0, ... up to 20th harmonic
    for n in range(1, 20):
        hf = f0 * n
        peak = max(w_col[hf - 1.5Hz : hf + 1.5Hz])
        if peak > 3.5 * 25th_percentile(w_col):
            count_hits += 1
            sum_energy += peak

    score = (sum_energy / total_energy) * 0.6 + (count_hits / 5) * 0.4
    return score
```

The ±1.5 Hz tolerance and 3.5× floor threshold are deliberately strict:
- Car RPM harmonics land at exact multiples of ~10 Hz and fall within ±1.5 Hz
- But they also produce harmonics, so they pass harmonic scoring
- This is why temporal scoring is essential as a second discriminator

### Step 5: Temporal Score

For each NMF component k, we ask: is H[:,k] non-stationary?

```python
def temporal_score(h_col):
    h_norm = h_col / max(h_col)       # normalize to 0-1
    cv = std(h_norm) / mean(h_norm)   # coefficient of variation
    return clip(cv, 0, 2) / 2         # scale to 0-1
```

Coefficient of variation (CV) = standard deviation / mean. A flat signal has CV ≈ 0.
A signal with a sharp spike has CV close to 2 or higher (clipped at 2).

Engine noise: flat activation, CV ≈ 0.1–0.2, temporal score ≈ 0.05–0.10
Elephant call: spike activation, CV ≈ 1.5+, temporal score ≈ 0.75+

### Step 6: Combined Scoring and Component Selection

```python
score[k] = 0.65 * harmonic_score[k] + 0.35 * temporal_score[k]
```

The top-2 components by score are classified as "elephant signal." Any component
scoring below 0.15 is rejected even if it's in the top-2 (prevents all-noise
classifications on recordings that have no elephant content at all).

**Why top-K instead of a threshold?**
Early versions used `score > 0.35` as the cutoff. On clean recordings where the
elephant call is strong, all 10 components scored 0.45–0.55 — all passed the threshold.
The result was a mask of all ones: nothing was suppressed. Top-K is robust to this
score distribution shift because it always picks exactly the K best components
regardless of absolute values.

### Step 7: Soft Wiener Mask

The elephant components are summed into an "elephant signal" reconstruction.
The noise components are summed into a "noise signal" reconstruction:

```python
e_sig = W[:, elephant_components] @ H[:, elephant_components].T
n_sig = W[:, noise_components]    @ H[:, noise_components].T

mask = e_sig / (e_sig + 0.90 * n_sig + 1e-8)
```

This is a **soft Wiener mask**: each time-frequency bin gets a value between 0 and 1
representing how confident we are that it's elephant signal. A bin where elephant
energy completely dominates gets mask ≈ 1. A bin that's pure noise gets mask ≈ 0.

The 0.90 coefficient (`PROP_DECREASE`) slightly over-weights the noise denominator,
making the mask more aggressive — bins that are 50/50 elephant/noise get mask ≈ 0.47
instead of 0.50.

### Step 8: Mask Hardening

The raw Wiener mask has a lot of values in the 0.1–0.4 range — ambiguous bins that are
mostly noise but not completely. Two operations harden the mask:

**Floor gate:**
```python
mask = where(mask < 0.25, 0.0, (mask - 0.25) / 0.75)
```
Anything below 0.25 goes to exactly zero. The remaining range [0.25, 1.0] is rescaled
to [0.0, 1.0]. This zeroes out the weakest noise-leaking bins.

**Squaring:**
```python
mask = mask ** 2
```
After rescaling, elephant bins sit near 1.0 and ambiguous bins sit near 0.5.
Squaring: 1.0² = 1.0 (elephant unchanged), 0.5² = 0.25 (ambiguous crushed).
This pushes the mask toward a nearly binary decision without a hard threshold.

### Step 9: Generator Comb Notch

For generator noise, each harmonic spike needs to be surgically removed. An IIR comb
notch filter is designed for the generator's fundamental frequency (e.g., 60 Hz) and
applied to the signal. Then:

```python
notch_mask = 1.0 - (1.0 - notch_ratio) * (1.0 - wiener_mask)
```

Where `notch_ratio = |STFT(notched_audio)| / |STFT(original)|` — the attenuation
the comb filter achieved at each bin.

The blending formula is elegant:
- When `wiener_mask = 1` (confirmed elephant): `notch_mask = 1.0` — no notch attenuation
- When `wiener_mask = 0` (confirmed noise): `notch_mask = notch_ratio` — full notch
- In between: proportional blend

This is important because an elephant rumbling at ~20 Hz has its 3rd harmonic at 60 Hz —
exactly where the 60 Hz generator comb filter would hit. The blending protects it.

### The Final Mask Application

```python
cleaned_magnitude = original_magnitude * mask
cleaned_audio = ISTFT(cleaned_magnitude * exp(j * original_phase))
```

We apply the mask to the **original magnitude** (not the noise-subtracted one).
The NMF ran on the noise-subtracted signal to learn accurate basis patterns, but
the final audio is reconstructed from the original — this avoids spectral subtraction
artifacts appearing in the output.

**Judge question: "How is this different from a neural network denoiser?"**
> Neural denoisers (like DeepFilterNet or Meta's Denoiser) train on millions of
> audio samples and learn a general mapping from noisy to clean. They work well for
> human speech because there's abundant training data. For elephant infrasound, there
> are a few hundred documented calls total — nowhere near enough to train a deep model
> that generalizes. NMF is unsupervised: it learns the structure of each recording
> from the recording itself, with no training data required. The harmonic scoring
> injects domain knowledge about elephant acoustics, replacing what training data
> would provide for a neural approach.

---

## Stage 4: ReconstructionAgent — Fixing Damaged Harmonics

### The Problem

The Wiener mask is built from NMF components. If a high harmonic (say, the 8th at
160 Hz) overlaps heavily with an airplane noise component, the NMF might assign most
of that bin's energy to the noise component. The resulting mask value at 160 Hz would
be low, and the ISTFT output would be missing that harmonic even though it was real.

### The Solution: Exponential Decay Fitting

Real elephant harmonics follow an approximate exponential decay in energy across
harmonic number:

```
E_n ≈ E_1 * exp(-lambda * n)
```

The 2nd harmonic has less energy than the 1st, the 3rd less than the 2nd, etc.
This isn't a perfect rule but it's a strong statistical tendency.

The stage fits this model to the surviving harmonics:

```python
log(E_n) = a*n + b    # linearized in log-energy space
trend = polyfit(n_values, log(E_values), degree=1)
```

Then for each harmonic, it checks: is the measured energy less than 20% of what the
trend predicts? If so, it's "damaged." It reconstructs the damaged harmonic by:
1. Finding the nearest healthy harmonic
2. Scaling it by `expected_energy / healthy_energy`
3. Blending: `0.3 * reconstructed + 0.7 * existing`

The 30/70 blend is conservative — we mostly trust the Wiener mask output and only
nudge damaged harmonics toward plausibility. Stronger reconstruction would risk
synthesizing signal that wasn't there.

**Why require ≥3 surviving harmonics for the fit?**
With 2 points, a line is always a perfect fit (zero residual) — it's interpolation,
not extrapolation with any statistical validity. With 3+ points, the fit is
overdetermined and the slope is a genuine estimate of the decay rate.

---

## Stage 5: OverlapAgent — Separating Two Simultaneous Callers

### Detection

Two elephants can call simultaneously. Their harmonics interleave in the spectrogram.
Detection looks for two distinct F0 peaks in 10–35 Hz, with:
- At least 5 Hz separation (within one caller's series, no two fundamentals land this close)
- Each peak has its own independent harmonic series (≥3 harmonics above noise floor)
- Secondary peak has at least 40% of the primary's energy

### Separation: Competitive Wiener Masking

If dual callers are detected, a second NMF is run on the cleaned STFT magnitude
(already noise-reduced from Stage 3). Each NMF component is scored against both F0s:

```python
scores_a[k] = how many of W[:,k]'s peaks align with f0_a * {1,2,3,...}
scores_b[k] = how many of W[:,k]'s peaks align with f0_b * {1,2,3,...}
```

The weighted sums produce "energy maps" for each elephant:

```python
sig_a = (W * scores_a) @ H.T   # freq x time, elephant A's energy
sig_b = (W * scores_b) @ H.T   # freq x time, elephant B's energy
```

Then competitive Wiener masks:

```python
mask_a = (sig_a / (sig_a + sig_b)) ** 2
mask_b = (sig_b / (sig_a + sig_b)) ** 2
```

At any time-frequency bin, mask_a + mask_b ≤ 1 (approximately — due to squaring).
Bins dominated by elephant A get mask_a → 1, mask_b → 0 and vice versa. The
separation is driven by which elephant "owns" each frequency at each moment.

**Why does the 5 Hz gap matter?**
From Poole 2005: elephant callers within the same recording are typically different
individuals with different body sizes. Body size correlates with vocal fold length,
which correlates with F0 — larger elephant, lower F0. The 5 Hz minimum gap ensures
we're detecting two distinct individuals, not sidelobes or harmonics of the same caller.

**Judge question: "What if both elephants have the same F0?"**
> Then they can't be separated with this technique — two perfectly pitch-matched
> callers produce an identical spectrogram to one caller at the same pitch. In practice,
> elephant fundamentals span 10–35 Hz and individual variation means this exact collision
> is rare. The system correctly does nothing in that case — it only activates when the
> peak detection confirms at least 5 Hz of separation.

---

## Stage 6: QualityScorerAgent — Measuring Success

### Tonal SNR

The standard SNR formula (signal power / noise power) doesn't work well here because
generator noise sits at the exact same frequencies as elephant harmonics. Comparing
"elephant band" (10–150 Hz) power to "noise band" (300–1000 Hz) power would give a
negative number even when the NMF did a perfect job.

Instead, a **tonal SNR** is used: compare the power AT elephant harmonic frequencies
to the power IN BETWEEN harmonics:

```python
for each harmonic n:
    harm_power    += peak PSD at [f0*n - 2.5, f0*n + 2.5] Hz
    between_power += mean PSD at [f0*n + 3, f0*(n+1) - 3] Hz

SNR = 10 * log10(mean(harm_power) / mean(between_power))
```

If the NMF correctly isolated the elephant call, harmonic bins should be much
stronger than inter-harmonic bins. If noise is leaking through, the inter-harmonic
power will be higher and SNR drops.

### The Revert Guard

If SNR after processing is more than 0.1 dB worse than SNR before:

```python
if snr_after < snr_before - 0.1:
    cleaned = original  # restore
```

This catches the edge case where NMF misidentified noise components as elephant signal
and the Wiener mask amplified noise instead of suppressing it. The call is still
flagged as valid (it contains a real elephant call — just undenoised) and forwarded
to clustering.

### Harmonic Completeness

```python
completeness = harmonics_present / harmonics_possible
```

Counts how many expected harmonics (from F0 up to 1000 Hz) have their peak PSD above
4× the noise floor. A score of 1.0 means every harmonic is clearly present. A score
of 0.3 means only 30% survived cleaning.

The noise floor is anchored to `max(cleaned_noise_floor, 0.10 * original_noise_floor)`.
The second term prevents the situation where an aggressive Wiener mask zeros out the
cleaned signal entirely — without the floor anchor, the "noise floor" becomes 0 and
every non-zero bin counts as present, giving a false 100% completeness.

### Validity

```python
valid = (f0 >= 10 and completeness >= 0.20 and snr_after > -20)
```

20% completeness threshold is deliberately loose — the Wiener mask can suppress some
upper harmonics even on good calls. The SNR floor of -20 dB filters out calls where
the signal was overwhelmed beyond recovery. Invalid calls are still forwarded through
the pipeline (never silently dropped) — they just don't contribute to clustering.

---

## Stage 7: ClusteringAgent — Finding Communication Patterns

### Feature Vector

Each valid call gets an 8-dimensional feature vector:

```
[F0, duration, harmonics_present, harmonic_completeness,
 snr_after, snr_improvement, multi_elephant_flag, f0_b]
```

These are normalized with `StandardScaler` (zero mean, unit variance) before any
distance calculations.

### UMAP

UMAP (Uniform Manifold Approximation and Projection) reduces the 8D feature space to
2D for visualization. Unlike PCA which only finds linear structure, UMAP preserves
local neighborhood relationships — calls that are similar in acoustic feature space
end up close together in the 2D plot.

Parameters: `n_neighbors=10, min_dist=0.1, random_state=42`
- `n_neighbors=10`: each point's local neighborhood is defined by its 10 nearest
  neighbors in 8D space. Higher = more global structure preserved.
- `min_dist=0.1`: how tightly clusters can pack in the 2D output. Lower = tighter clusters.

Falls back to PCA automatically if umap-learn isn't installed.

### K-means Clustering

K-means partitions calls into k groups by minimizing within-cluster variance.
k = min(7, n_valid // 3) — at most 7 clusters, at most 1 cluster per 3 calls.

The cluster centers represent "call types" — groups of calls with similar acoustic
properties. If elephant communication has distinct call categories (greeting rumbles
vs. alarm calls vs. contact calls), they should appear as separate clusters.

### Tribe Graph

Every pair of calls with cosine similarity > 0.80 in the standardized 8D feature space
gets an edge in the Tribe graph, weighted by similarity. This is a different question
from clustering:
- Clustering asks: what are the distinct call types?
- Tribe asks: which individual calls are acoustically similar to each other?

The graph is saved as `tribe_edges.csv` and can be visualized as a network where
nodes are calls and edge thickness represents similarity. Dense sub-graphs might
indicate the same individual (similar F0 = similar body size) or similar behavioral
contexts.

### Claude API Hypotheses

If an API key is set, the cluster summaries are sent to Claude with the prompt:
> "I clustered N elephant rumble calls into K groups. For each cluster: what behavioral
> context might this represent? Which clusters likely come from the same individual?
> What are the 3 most important hypotheses to test?"

The model is `claude-sonnet-4-6`. The output is saved to `ai_hypotheses.txt`. This
is a starting point for the researchers, not a definitive answer — the point is to
surface hypotheses that acoustic analysis alone might miss.

---

## Edge Device: SenseCAP Indicator

The `SenseCapAgent` runs in parallel with the main pipeline and streams detection
events to a **Seeed SenseCAP Indicator** — a small ESP32-based display device.

When QualityScorerAgent fires an event to the `sensecap_q` queue:
```python
{
    "detected":   True,
    "confidence": 78.4,    # (snr_after + 40) * 2, capped at 100
    "f0_hz":      19.5,
    "noise_type": "airplane"
}
```

SenseCapAgent picks it up and sends it over USB serial (115200 baud) to the SenseCAP
device, which displays a live indicator of whether an elephant call is currently
being detected and at what confidence.

This is the "edge deployment" component — in a real field setup, the Pi runs the
pipeline live and the SenseCAP display sits in the researcher's tent showing real-time
detection status without requiring a laptop.

---

## The Dashboard

```bash
streamlit run dashboard/app.py
```

A Streamlit web app that reads the `results/` directory and visualizes:
- Before/after spectrograms for every call
- SNR improvement distribution
- UMAP scatter plot colored by cluster
- Tribe similarity graph
- Cluster summary cards

Runs locally at `localhost:8501`. The app re-reads results on each load — run the
pipeline first, then open the dashboard.

---

## Summary: What Makes This Non-Trivial

Here's what to emphasize if a judge asks "isn't this just noise cancellation?":

1. **Domain-specific harmonic scoring** — generic noise cancellation doesn't know
   that 19.5 Hz and 39 Hz and 58.5 Hz are the same elephant. RumbleOS does.

2. **Dual discrimination axis** — frequency domain alone can't separate elephant
   calls from engine harmonics. The temporal non-stationarity score is what makes
   the separation reliable.

3. **No training data required** — NMF learns the structure of each recording from
   itself. This works on any recording from any location with any elephant, because
   it adapts to the specific noise environment it's given.

4. **Full-file processing** — not just windowing around known calls. The system
   finds and preserves signal wherever it exists in the recording.

5. **Dual-caller separation** — detecting and separating two simultaneously calling
   elephants is a non-trivial source separation problem solved with a purpose-built
   competitive Wiener approach.

6. **End-to-end pipeline** — from raw noisy WAV to cleaned audio, cluster assignments,
   similarity graph, and behavioral hypotheses in a single run.

---

## Quick-Reference Numbers

| Parameter | Value | Why |
|-----------|-------|-----|
| Sample rate | 4000 Hz | 1.95 Hz/bin at n_fft=2048; captures all harmonics to 1000 Hz |
| n_fft | 2048 | Frequency resolution vs. time resolution tradeoff |
| hop_length | 512 | 75% overlap; smooth time evolution |
| NMF components | 10 | Empirically optimal; more = slow and overfit, fewer = underfit |
| Top-K elephant | 2 | Conservative; prevents noise leak on quiet recordings |
| Mask floor | 0.25 | Hard-zeros weak bins; raised from 0.08 after noise leak issues |
| Temporal weight | 0.35 | 35% temporal score; enough to reject stationary engine harmonics |
| SNR revert threshold | 0.1 dB | Tight; catch any pipeline degradation immediately |
| Completeness threshold | 0.20 | Loose; Wiener mask can suppress some upper harmonics legitimately |
| Dual-F0 gap | 5 Hz | From Poole 2005; minimum gap between distinct individual callers |
| Tribe similarity | 0.80 cosine | High threshold; only acoustically near-identical calls connect |

---

## Likely Judge Questions and Answers

**Q: Why NMF and not a spectrogram subtraction approach?**
> Spectral subtraction removes the average noise floor. NMF learns the structure of
> the noise and signal simultaneously, allowing separation of noise that varies in
> time and overlaps in frequency with the signal. It's the difference between
> subtracting a static background color from a photo vs. actually segmenting objects.

**Q: How do you know the cleaned audio is actually better?**
> Two metrics: tonal SNR improvement (harmonic peaks should be stronger relative to
> inter-harmonic bins after cleaning) and harmonic completeness (more of the expected
> harmonic series should be detectable). Both are computed on every call and logged.
> Average improvement across the 212 calls is 4–5 dB with peaks up to 17 dB.

**Q: What's the accuracy of the noise classifier?**
> For the 44 known files with ground-truth labels in timestamps.csv, the classifier
> isn't tested because ground truth labels are used directly. For live audio, the
> classifier has been hand-validated against a small set of test recordings. In practice
> the car/airplane distinction is low-stakes (same removal strategy); the generator
> detection is the critical one and requires 6 confirmed harmonics — conservative enough
> that false positives are rare.

**Q: Could this work for other animals?**
> Yes, with parameter changes. The F0_RANGE (10–35 Hz) and harmonic scoring are
> specific to elephants. For, say, blue whale calls (10–40 Hz) or bowhead whale song
> (25–900 Hz), you'd change those bounds. The NMF + temporal score + Wiener mask
> architecture is general-purpose for any species with harmonic vocalizations buried
> in stationary mechanical noise.

**Q: Why not use a pre-trained model like Wav2Vec or a spectrogram CNN?**
> No training data. There are ~200 labeled elephant infrasound calls in total worldwide —
> not enough to train a deep model that generalizes. NMF is unsupervised and requires
> zero labels. The domain knowledge (harmonic structure, temporal behavior) is encoded
> in the scoring functions, not learned from data.

**Q: What happens when the pipeline gets it completely wrong?**
> The SNR revert guard catches pipeline degradation: if the cleaned SNR is worse than
> the original, the original segment is restored. Error handling in BaseAgent catches
> any exception in any stage, tags the message with `"error": ...` and `"valid": False`,
> and forwards it — the pipeline never stalls and every call always produces an output.

**Q: How does the Tribe graph help researchers?**
> Individual elephants have consistent F0 (determined by body size / vocal anatomy).
> Calls from the same individual cluster tightly in the Tribe graph. By identifying
> which graph nodes are likely the same individual, researchers can reconstruct
> behavioral sequences — this elephant called, then that one responded, then this one
> again — without needing visual identification in the field.
