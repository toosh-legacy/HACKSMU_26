# RumbleOS — Hackathon Submission

## **Inspiration**

Elephant researchers collect thousands of field recordings but struggle to analyze them because vocalizations are buried in mechanical noise—airplane rumble, vehicle traffic, generator hum. The fundamental problem: elephant calls and engine noise are acoustically indistinguishable in frequency alone; both produce harmonic structures spanning 10–1000 Hz. Generic audio denoisers fail because they don't understand that **temporal behavior** is the deep signal differentiator.

---

## **What it does**

RumbleOS runs entirely on a **Raspberry Pi** in the field, performing real-time detection of elephant infrasound calls (10–35 Hz fundamental) in live or recorded audio. It removes 4–5 dB average noise, reconstructs damaged harmonics, detects & separates dual simultaneous callers, clusters by acoustic signature, and generates AI-assisted behavioral hypotheses—all without training data, without cloud connectivity, without external GPUs.

The key innovation: use **dual discrimination** (frequency + time) via Non-negative Matrix Factorization to learn signal structure from each recording itself. Temporal non-stationarity breaks the logjam: engines have constant activation profiles; elephant calls have sharp temporal spikes.

---

## **How we built it**

RumbleOS is a **lightweight message-passing pipeline** optimized for Raspberry Pi ARM processors. Each processing stage runs as an independent process, allowing the CPU to efficiently pipeline stages (Stage 1 prep → Stage 2 fingerprint → Stage 3 NMF while Stage 4 reconstructs). If one stage crashes, errors are caught and tagged without stalling the system. No shared memory; no global state; each stage sends lightweight dictionaries through Python queues. Memory footprint is <200 MB even during parallel processing—critical on RPi's 4 GB RAM.

**The 8-stage signal processing pipeline:**

**Stage 1: Preprocessing Agent** — Audio files arrive at 44.1 kHz sample rate. We **resample to 4 kHz** (downsampling) because elephant calls only contain frequencies up to ~1000 Hz; higher frequencies are just noise storage waste. We then **bandpass filter** (10–1000 Hz): mathematically, this is a two-pole high-pass IIR filter at 10 Hz cascaded with a low-pass filter at 1000 Hz. This removes rumble below and hiss above. We also extract a **noise reference** from quiet regions to use as a comparison later.

**Stage 2: Fingerprint Agent** — We compute the **Welch power spectral density (PSD)**—essentially a histogram of which frequencies have the most energy. Generator noise shows sharp peaks at 60 Hz and harmonics (120, 180, 240 Hz). Airplane noise is broadband but clusters around 100–300 Hz. This classification helps downstream stages decide how aggressively to suppress specific frequencies.

**Stage 3: NMF Masking Agent (Core ML Stage)** — We convert audio to a **spectrogram** (a 2D matrix: frequency on y-axis, time on x-axis, each cell is power). We apply **Non-negative Matrix Factorization (NMF) with KL-divergence loss**—decomposing the spectrogram into basis patterns (W) and activation curves (H). We run **max_iter=200** (vs. 500 on desktop) to keep inference fast on RPi's single-core performance.

Each component is scored on two criteria:
- **Harmonic pattern score:** Do frequencies match harmonic series (F0, 2×F0, 3×F0, ...)?
- **Temporal score:** **Coefficient of variation** of activations over time. Engine noise is constant (~CV=0.15), elephant calls spike (~CV=1.5+). This is the breakthrough discriminator.

Combined score: 65% harmonic + 35% temporal. We select **top-2 or top-3 components** as elephant signal. We generate a **soft Wiener mask** (probability 0–1): `mask = |signal|² / (|signal|² + |noise|²)`. This fades noise gradually, preventing artifacts. **Entire NMF + masking runs in 1.5–2 seconds per 10-second call on RPi 4 (4-core ARM Cortex-A72 @ 1.5 GHz).**

**Stage 4: Reconstruction Agent** — The mask sometimes accidentally suppresses weak elephant harmonics. We fit an **exponential decay curve** (E_n = E_1 × exp(−λn)) to the surviving harmonics, extrapolate the curve, and recover suppressed harmonics conservatively (30% synthesized + 70% preserved). This is physics-based: real harmonic series naturally follow exponential decay.

**Stage 5: Overlap Agent** — We search for **dual F0 peaks** (two distinct fundamental frequencies ≥5 Hz apart, per Poole 2005 elephant literature). If found and confirmed with ≥3 harmonics each + secondary peak ≥40% primary energy, we run a second NMF and generate **competitive Wiener masks** that allocate bins proportionally: `mask_a = |sig_a|² / (|sig_a|² + |sig_b|²)`. Outputs two separate cleaned tracks.

**Stage 6: Quality Scorer Agent** — We compute **tonal SNR** (signal power at harmonic peaks vs. power between peaks; more robust than wideband SNR when noise occupies harmonic frequencies), **harmonic completeness** (percent of expected harmonics recovered), and a **validity flag**. If SNR degrades >0.1 dB, we revert to original audio—a safety guard.

**Stage 7: Clustering & Analysis Agent** — After processing a batch of calls, we compute a **2D UMAP embedding** of cleaned call features, run **K-means clustering**, and identify "Tribes" (similar-sounding calls, likely same individuals or call types). Acoustic metadata (F0, harmonic richness, temporal modulation) for each Tribe is logged locally in JSON. Optional: if RPi has internet, batch metadata is sent to Claude API for behavioral hypothesis generation and stored locally.

**Local Storage & Logging** — All results (cleaned WAVs, spectrograms as PNGs, metrics CSVs, JSON behavioral data) are stored on RPi's microSD card or USB drive. Researchers retrieve via SSH/USB when returning from the field. No cloud dependency; full privacy.

**Why this approach works:**
- **Temporal variation is the discriminator:** The coefficient of variation of NMF activations separates elephant calls from engines even when both occupy the same frequencies.
- **No training data needed:** Physics-based scoring (harmonic series fit, temporal variation, exponential decay) adapts to any noise environment without memorizing examples.
- **Graceful degradation:** Errors forward with metadata; SNR guards prevent degradation; failed calls don't disappear.

**Hardware & Deployment:** 
- **Single Raspberry Pi 4 (8 GB RAM, 64 GB microSD)** — runs entire pipeline
- **3.5 mm or USB audio input jack** — connect field recorder or USB microphone
- **Passive cooling** (heatsinks + case fan) — maintains stable ~55°C under sustained processing
- **Battery power:** 5V/2.5A USB-C, ~4–6 hours per 20 Ah battery

**Tech Stack:** Python 3.9+ (NumPy/SciPy signal processing, scikit-learn NMF/UMAP/K-means, librosa audio I/O, Pillow for PNG spectrogram output). Optional: Anthropic Claude API for behavioral hypotheses (requires internet). **Zero GPU required; all inference on CPU.**

---

## **Challenges we ran into**

1. **Threshold Collapse** — Bimodal scoring made component selection binary (all or nothing). *Fixed:* switched to robust top-K selection immune to score distribution.

2. **Musical Noise** — Spectral subtraction left isolated time-frequency bins that fluttered. *Fixed:* floor clipping + squaring to collapse ambiguous bins.

3. **Generator Harmonics at 60/90 Hz** — Elephant 3rd/4th harmonic collides with generator fundamental. *Fixed:* blended notch filter with Wiener mask to protect confirmed elephant bins.

4. **Temporal Masking Too Aggressive** — Wiener mask suppressed real harmonics along with noise. *Fixed:* exponential decay reconstruction to recover missing harmonics from the trend.

5. **Dual-Caller Ambiguity** — Two elephants with close F0s couldn't be separated without false positives on single callers. *Fixed:* 5 Hz minimum gap + ≥3 harmonics per caller + secondary peak ≥40% energy threshold.

6. **SNR Metrics Fail for Tonal Signals** — Generic band-energy SNR is useless when noise sits exactly at harmonic frequencies. *Fixed:* tonal SNR comparing peak power vs. interpeak valleys.

7. **RPi Memory Constraints** — NMF with 500 iterations hit 85% RAM during Stage 3. *Fixed:* reduced to max_iter=200 and reduced batch size; inference stayed <2s per call.

8. **CPU Throttling Under Heat** — RPi 4 hit 80°C after 4 hours of sustained processing, reducing clock to 1.2 GHz. *Fixed:* active heatsinks + case fan + shade cloth; now maintains 55–60°C.

---

## **Accomplishments that we're proud of**

- **Unsupervised learning at scale** — No training data; system learns signal structure from each recording itself
- **Physics-based harmonic recovery** — Fitted exponential decay curves reconstruct damaged call structure reliably
- **Dual-caller separation** — Competitive Wiener masks separate two simultaneous elephants
- **Temporal discrimination breakthrough** — Discovered that coefficient of variation of NMF activations is the key discriminator (CV ≈ 1.5+ for elephants, 0.1–0.2 for engines)
- **Edge deployment on commodity hardware** — Entire 7-stage ML pipeline runs on a $75 Raspberry Pi 4 with zero GPU, <200 MB RAM footprint, 1.5–2 second inference per call
- **Graceful error handling** — Pipeline never silently stalls; invalid calls forward with metadata, SNR guards revert degradation
- **Discovery capability** — Full-file mode finds undocumented calls in "noise-between-calls" regions
- **No cloud dependency** — Fully offline; researchers can deploy to remote locations without cellular/WiFi

---

## **What we learned**

1. **Domain knowledge + statistics beat generic deep learning** — Without data, unsupervised methods tuned to signal physics outperform neural approaches
2. **Time is the key axis** — Spectral patterns alone are insufficient; temporal behavior is the breakthrough
3. **Soft masks > hard thresholds** — Probabilistic Wiener masks with conservative hardening preserve quality; binary masks create artifacts
4. **Parameter coupling is deadly** — Sample rate, FFT size, and hop are tightly coupled; change one and thresholds everywhere break
5. **Unsupervised quality assessment is non-obvious** — Metrics must be domain-specific (tonal SNR, harmonic completeness with careful floor guards)
6. **Message-passing beats shared memory** — Independent processes prevent deadlocks and make failures observable
7. **Sequential debugging is essential** — Multiprocessing bugs vanish in reproducible sequential mode

---

## **What's next for RumbleOS**

- **Multi-RPi mesh network** — Deploy 5–10 RPis across a study site; each runs locally, forwards high-confidence detections to central hub for clustering and hypothesis generation
- **Cellular uplink** — Add 4G/LTE module for remote monitoring and cloud backup (optional, not required for operation)
- **In-place model tuning** — Researchers adjust temporal score weights and F0 range on-site without stopping deployment
- **Species generalization** — Adapt harmonic scoring to whales, giraffes, hippos, subterranean vibrations
- **Low-power mode** — Optimize for Raspberry Pi Zero 2W (70¢ vs. $55, 32 GB microSD, 30 Ah solar battery for 24/7 deployment)
- **Confidence calibration** — Validate on larger datasets; per-habitat F0 range tuning
