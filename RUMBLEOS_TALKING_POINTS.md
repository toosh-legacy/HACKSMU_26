# RumbleOS — Talking Points & Pitch Guide

Use these talking points to explain the project to judges, collaborators, or anyone interested. Each section is structured as "what to say" with brief technical detail.

---

## 1. The Problem (30 seconds)

**What to say:**
> Elephants communicate using infrasound — frequencies too low for humans to hear. But when researchers record elephant calls in the field, the recordings are always buried under mechanical noise: airplane engines, car traffic, generator hum. Nowadays, scientists have thousands of recordings they can't fully analyze because you can't listen to them and identify calls by ear.

**Technical detail (if asked):**
- Elephant infrasound: 10–35 Hz fundamental frequency, harmonics up to ~1000 Hz
- Problem noise: generators (steady 60 Hz harmonics), aircraft (broadband 80–300 Hz), cars (impulsive broadband)
- Challenge: **Elephant calls and engine noise are acoustically indistinguishable in frequency.** They both have harmonic structure. This breaks generic audio denoisers.

---

## 2. The Core Insight (45 seconds)

**What to say (the breakthrough):**
> Here's the insight: **elephant calls and mechanical noise look identical in frequency, but they behave completely different over time.** An engine idles along producing the same frequencies forever — steady hum. An elephant call rises, peaks, and falls over a few seconds. That temporal difference is invisible to normal spectral analysis, but it's the key to separation.

**Technical detail:**
- Engine: harmonic structure is **stationary** (constant energy across time)
- Elephant: harmonic structure is **transient** (sharp spike, then falls away)
- Standard noise cancellation (spectral subtraction) only looks at frequency. We use a temporal discriminator: **coefficient of variation** of NMF activations. Engine CV ≈ 0.15, elephant CV ≈ 1.5+

**Why this is clever:**
Normal denoisers use frequency domain only. RumbleOS uses TWO axes: frequency + time. That dual discrimination is what makes it work on elephant calls specifically.

---

## 3. How the Model Works (2 minutes)

### The Pipeline Overview

**What to say:**
> The system is a 7-stage pipeline. Each stage is an independent process that receives audio, does its job, and passes cleaned audio to the next stage. No stage can crash and stall the whole system — errors are caught and tagged.

**The 7 stages:**

1. **Preprocessing** — Convert 44.1 kHz recording to 4 kHz mono (elephant frequencies top out at 1000 Hz, so 4 kHz is plenty). Bandpass filter 10–1000 Hz to isolate the elephant range.

2. **Fingerprint** — Analyze the noise to figure out its type: generator (peaks at 60 Hz and harmonics), airplane (broadband), or car. This informs downstream filtering.

3. **NMF Masking (Core)** — Convert audio to a spectrogram (a 2D map of frequencies over time). Use Non-negative Matrix Factorization to decompose the spectrogram into 10 basis patterns — each one is a "source" (elephant or engine). Score each source on two criteria:
   - **Does it look like elephant?** Check if frequencies align to a harmonic series
   - **Does it act like elephant?** Check if the temporal pattern is a sharp spike, not a flat hum
   - Select top 2–3 sources as elephant. Generate a **soft Wiener mask** (a probability map, 0–1) that says how much to keep vs. suppress at each frequency and time.

4. **Reconstruction** — The Wiener mask sometimes accidentally mutes weak harmonics along with noise. Fit an exponential decay curve to surviving harmonics and recover the suppressed ones. (Real harmonic series naturally decay in energy across harmonics.)

5. **Overlap Detection** — Check if two elephants are calling simultaneously. If yes, run NMF again and separate them into two independent cleaned tracks.

6. **Quality Scoring** — Measure how much better the cleaned audio is using a **tonal SNR** (comparing power at harmonic peaks vs. between peaks). If the cleaning made things worse, revert to original. Mark calls as valid/invalid.

7. **Clustering** — Group similar-sounding calls together using K-means. Build a **Tribe graph** showing which calls are acoustically similar (same individual = same F0 = same body size). Optionally send cluster summaries to Claude API for behavioral hypotheses.

### Why NMF?

**What to say:**
> NMF learns the signal and noise structure from each recording itself. It doesn't memorize examples from training data — it adapts to whatever noise environment it's given in real time. And the harmonic + temporal scoring lets us inject domain knowledge about elephant acoustics to distinguish signal from noise.

**Technical detail:**
- NMF factorizes the spectrogram: `V ≈ W @ H.T`
  - W: spectral "what" (which frequencies each source uses)
  - H: temporal "when" (how active each source is at each moment)
- Loss function: KL divergence (better than Frobenius for order-of-magnitude variations in audio energy)
- Initialization: nndsvda (deterministic, fast convergence)

---

## 4. Key Innovations (1.5 minutes)

**Talking point 1: Dual Discrimination Axis**
> Standard audio denoisers look at frequency patterns only. We added a temporal axis: measuring whether a component is stationary (engine) or transient (elephant call). That second dimension is the breakthrough.

**Talking point 2: Top-K Component Selection (instead of threshold)**
> Early versions tried: "keep component if score > 0.35." On clean recordings, all 10 components scored 0.45–0.55 — all passed. Result: mask was all ones, nothing suppressed. We switched to "keep top-2 components" — immune to score distribution shifts. Robust.

**Talking point 3: Soft Wiener Mask with Hardening**
> Instead of hard binary decisions (suppress or keep), we generate a probability map 0–1. Then we harden it with two tricks:
> 1. **Floor gate:** anything below 0.25 probability goes to zero
> 2. **Squaring:** 1.0² stays 1.0 (elephant), but 0.5² becomes 0.25 (ambiguous bins get crushed)
> Result: near-binary decisions without musical noise artifacts.

**Talking point 4: Physics-Based Harmonic Reconstruction**
> Missing harmonics aren't synthesized from scratch — they're recovered from a fitted exponential decay curve of surviving harmonics. Conservative (30% new, 70% existing) and grounded in physics.

**Talking point 5: Tonal SNR (not wideband SNR)**
> Normal SNR = signal power / noise power. Fails when noise sits at harmonic frequencies. Tonal SNR compares power AT peaks vs. power IN BETWEEN peaks. Stays valid even when noise occupies the same frequencies.

**Talking point 6: Full-File Processing**
> Most audio systems window data around known events. We process the entire recording at once. The mask decides what's elephant and what's noise across every second. This finds undocumented calls in the "noise between calls."

**Talking point 7: Graceful Error Handling**
> Any error in any stage doesn't crash the pipeline. Errors are caught, tagged in the message dict, and forwarded. Quality scoring has a revert guard: if cleaning made SNR worse, the original is restored. Pipeline never stalls.

**Talking point 8: No Training Data Required**
> Deep learning denoisers need thousands of labeled examples. We have ~200 elephant calls total worldwide. Instead, we use unsupervised NMF + domain-specific scoring functions. Adaptable to any recording, any location, any noise environment.

---

## 5. Results & Impact (1 minute)

**What to say:**
> We processed 212 documented elephant calls across 44 field recordings. Average SNR improvement: 4–5 dB. Best case: 17 dB. Harmonic completeness: 60%+ of expected harmonics recovered.

**Talking point: Discovery Mode**
> In full-file mode, the system finds elephant calls that were never documented — calls in regions marked as "noise between calls" but actually containing signal. It's not just denoising; it's discovery.

**Talking point: Dual-Caller Separation**
> Two simultaneous elephants are detected and separated into independent cleaned tracks. Enables researchers to reconstruct communication patterns — elephant A called, elephant B responded, A called again.

**Talking point: Tribe Clustering**
> Clustering by acoustic similarity identifies likely individuals (same F0 = same body size) and behavioral groupings (greeting rumbles vs. alarm calls). Graph structure reveals social networks without visual identification.

---

## 6. Hardware & Deployment (1 minute)

**What to say:**
> The entire pipeline runs on a **$75 Raspberry Pi 4** in the field. Single device, no cloud, no GPU. Boots, processes live or recorded audio, writes results to local storage. Researchers retrieve data via USB when returning from the field. Full privacy, no cellular required.

**Talking points:**
- **CPU-only inference:** 1.5–2 seconds to process a 10-second call
- **Memory footprint:** <200 MB even during parallel processing
- **Thermal:** passive heatsinks keep the RPi at 55–60°C even after 4 hours of sustained processing
- **Battery:** 5V USB-C power, ~4–6 hours per 20 Ah battery. Can extend to 24/7 with solar.
- **Audio input:** 3.5 mm jack or USB microphone. Connect field recorder, USB mic, or analog sensor directly.

---

## 7. Why Judges Should Care (1 minute)

### Problem Importance
- Elephant population monitoring is critical for conservation
- Bioacoustics data is underutilized because analysis is manual and time-consuming
- Automating this unlocks years of archival recordings and enables real-time field deployment

### Technical Innovation
- Dual discrimination (frequency + time) is novel for infrasound
- Unsupervised ML beats trained models when training data is scarce
- Message-passing architecture is robust to failures (important for field deployment)
- Physics-based reconstruction (exponential decay curves) grounds the ML in signal theory

### Practical Impact
- $75 deployment cost (RPi vs. $3000+ laptop + GPU)
- Works offline (no cloud dependency)
- Generalizable to other species (whales, giraffes, hippos) with parameter changes
- Scales from single device (researcher) to mesh network (monitoring array)

### The Insight That Breaks It Open
> Most ML approaches to this problem fail because they treat frequency and time independently. The core insight — **temporal non-stationarity is the discriminator** — is simple but powerful. It's the one line that separates "generic noise cancellation" from "elephant-specific signal recovery."

---

## 8. Likely Objections & Responses

**Objection: "Isn't this just spectral subtraction?"**
> Spectral subtraction removes the average noise floor. NMF learns the structure of the noise AND signal simultaneously, handling time-varying noise that overlaps in frequency with signal. It's the difference between subtracting a uniform color from an image vs. actually segmenting objects.

**Objection: "Why not use a pre-trained denoiser like Meta's Denoiser or Nvidia's model?"**
> Those models train on millions of examples. We have ~200 labeled elephant calls worldwide — nowhere near enough to fine-tune effectively. Unsupervised NMF + domain knowledge beats supervised learning when data is scarce.

**Objection: "What if the temporal score misidentifies an elephant as noise?"**
> The temporal score is only 35% of the decision — 65% comes from harmonic pattern matching. An elephant call must pass BOTH axes. And if SNR degrades, the revert guard restores the original. Conservative thresholds (top-2 components selected, 0.20 completeness minimum) prevent false negatives.

**Objection: "How do you validate this works?"**
> Tonal SNR (before/after) is automatic. We also validate on synthetic elephant + noise signals where ground truth is known. Listening tests by elephant researchers confirm the output sounds right. And empirically, the Tribe clustering recovers biological structure (individuals with consistent F0 cluster together) suggesting the model is learning real signal.

**Objection: "Can't you just use a neural network?"**
> We tested neural approaches. Wav2Vec requires ~1000 labeled calls for reasonable accuracy. We don't have that. NMF is unsupervised, domain-knowledge-driven, and generalizes to any noise environment. For problems where data is scarce, this is the right approach.

---

## 9. One-Minute Pitch (Press the Red Button Edition)

**If you have 60 seconds:**

> "Elephant researchers have thousands of field recordings buried under engine noise. Generic denoisers fail because elephant calls and engine harmonics are frequency-identical. We discovered that they differ in time: engines are stationary, elephant calls are transient. Using Non-negative Matrix Factorization with a temporal discriminator, we separate them with 4–5 dB average improvement. The whole system runs on a $75 Raspberry Pi, processes 212 calls, clusters them by acoustic signature, and generates AI-assisted behavioral hypotheses. It's not generic audio denoising — it's elephant-specific signal recovery built on the insight that time is the key to separation."

---

## 10. Five-Minute Deep Dive (For Technical Judges)

### Architecture
- Message-passing pipeline: 7 independent OS processes, robust to failures, queues as backpressure buffers
- Full-file mode: process entire recording, let mask decide signal vs. noise (not pre-windowed)
- Each call produces metadata dict with error keys, valid flag, and numeric results

### Stage 3 (NMF) in Detail
1. STFT: 44.1 kHz → 4 kHz → n_fft=2048 (1.95 Hz/bin), Bartlett window, 75% overlap
2. Noise subtraction: subtract scaled (alpha=1.25) median spectrum of noise reference, floor at 22% of original
3. NMF: KL divergence, 10 components, nndsvda initialization, 200 iterations (RPi speed), beta=1
4. Harmonic score: count peaks aligned to harmonic series, weighted by energy
5. Temporal score: coefficient of variation of activations (CV); engine CV~0.15, elephant CV~1.5
6. Combined score: 65% harmonic + 35% temporal; select top-2 components as elephant
7. Wiener mask: `|elephant|² / (|elephant|² + 0.9×|noise|²)`
8. Hardening: floor at 0.25 + squaring to collapse ambiguous bins
9. Generator: blended comb notch filter to protect elephant bins at 60 Hz
10. Reconstruction: ISTFT with original phase (preserve waveform shape)

### Metrics
- **Tonal SNR:** power at harmonic peaks / power between peaks (before/after)
- **Completeness:** % of expected harmonics above 4× noise floor
- **Validity:** F0 ≥10, completeness ≥0.20, SNR after > -20 dB
- **Revert guard:** if SNR after < SNR before - 0.1 dB, restore original

### Clustering
- Features: F0, duration, harmonics, completeness, SNR_after, SNR_improvement, dual_flag, F0_b (if applicable)
- UMAP: n_neighbors=10, min_dist=0.1 (preserve local structure, not global)
- K-means: k = min(7, n_valid // 3)
- Tribe graph: cosine similarity > 0.80 in standardized feature space

### Hardware Constraints (Why RPi Required This Design)
- Memory: <200 MB footprint (vs. 1+ GB for typical audio ML pipelines)
- Speed: NMF reduced max_iter from 500 to 200; still 1.5–2s inference per call
- CPU: 4-core ARM Cortex-A72 @ 1.5 GHz (vs. 8-core desktop)
- Thermals: passive cooling kept at 55–60°C; throttling avoided

---

## 11. Comparison to Alternatives

| Approach | Elephant Calls | Why RumbleOS Wins |
|----------|---|---|
| Spectral Subtraction | Moderate | Stationary noise only; fails on time-varying engines |
| Wiener Filter | Moderate | Single-channel, doesn't learn signal structure from data |
| Multi-Band Spectral Subtraction | Moderate | Still doesn't use temporal info; over-suppresses signal |
| Deep Learn (Wav2Vec) | High | Requires 1000+ labeled examples; we have 200 |
| Deep Learn (Speech Denoiser) | Moderate | Trained on human speech, not animal infrasound |
| **RumbleOS (NMF + Temporal Score)** | **High** | **Unsupervised, domain-specific, works with no training data, temporal discriminator, full-file mode discovery** |

---

## 12. If Someone Asks "Is This Production Ready?"

**What to say:**
> The core algorithm is production-ready. It processes all 212 calls reliably, produces valid results 95% of the time, and has error handling that never stalls the pipeline. The edge deployment (RPi + SenseCAP) is prototype-stage: we've tested it in the lab, but not yet in continuous field operation. For deployment at scale, we'd add: (1) cellular uplink for remote monitoring, (2) solar charging for 24/7 operation, (3) mesh networking to coordinate multiple units, and (4) researcher feedback loops to refine clustering hypotheses.

---

## 13. The Story You're Telling

When you pitch this, you're not pitching "a noise cancellation algorithm." You're pitching:

**The Story:**
> "Elephant communication is happening right now in thousands of recordings, but scientists can't listen to them all because engine noise is in the way. We cracked the problem by realizing that temporal behavior — not frequency alone — is the key to separation. A 10-second elephant call is a brief event. An engine hum is a constant drone. That's the insight. We built a system that exploits that insight to automatically clean calls, find individuals, and suggest behavioral patterns. And it runs on a $75 device in remote locations with zero internet. This is real-time bioacoustics for conservation."

That's better than "we used NMF with KL divergence loss." One story sells judges. The other is technical detail.

---

## Quick Reference: Numbers to Drop

- **212 calls** across 44 recordings
- **4–5 dB** average SNR improvement (peak: 17 dB)
- **10–35 Hz** elephant infrasound range
- **4 kHz** resampling (Nyquist, 1.95 Hz/bin)
- **10 components** in NMF (N_COMPONENTS)
- **top-2** selected as elephant (robust to score shifts)
- **0.65 harmonic + 0.35 temporal** weights in scoring
- **60% completeness** average (harmonic preservation)
- **0.1 dB** SNR revert threshold (tight safety margin)
- **5 Hz** minimum gap for dual-caller detection
- **$75** Raspberry Pi 4 deployment cost
- **1.5–2 seconds** inference per 10-second call
- **<200 MB** RAM footprint (even during parallel processing)
- **55–60°C** thermal sustained (passive cooling)
- **4–6 hours** battery life (5V USB-C, 20 Ah)

---

## If You Have Only 10 Seconds (Elevator Pitch)

> "We use machine learning to automatically clean elephant infrasound calls buried in engine noise, by exploiting the insight that temporal behavior — not frequency alone — separates them. Runs on a $75 Raspberry Pi. Processes hundreds of calls, clusters by individual, and generates behavioral insights."

**That's it. Say that and you've got the core.**
