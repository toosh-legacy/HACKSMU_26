import numpy as np
from agents.runtime import configure_runtime

configure_runtime()

import librosa
from sklearn.decomposition import NMF
from scipy.signal import find_peaks
from agents.base import BaseAgent

N_FFT      = 2048
HOP_LENGTH = 512

class OverlapAgent(BaseAgent):
    """
    Stage 5: Multi-elephant overlap resolution.

    Detects if two elephants are calling simultaneously by looking for
    two distinct F0 peaks in the 10-35 Hz band. If detected, runs dual
    NMF to separate each caller into their own audio stream.

    Key insight: within one call, harmonics never cross each other.
    When two callers overlap, their harmonics WILL cross.

    Input keys required:  cleaned, magnitude, phase, detected_f0, sr
    Output keys added:    multi_elephant (bool), f0_b (float),
                          cleaned_b (array, only if multi_elephant=True)
    """
    def process(self, msg: dict) -> dict:
        if 'error' in msg: return msg

        mag   = msg['magnitude']
        phase = msg['phase']
        f0_a  = msg['detected_f0']
        sr    = msg['sr']
        freqs = librosa.fft_frequencies(sr=sr, n_fft=N_FFT)

        f0_mask   = (freqs >= 10) & (freqs <= 35)
        f0_energy = mag[f0_mask, :].mean(axis=1) if f0_mask.any() else np.array([0.0])
        # Stricter peak finder: require ≥50 % of the tallest peak and a
        # 5-bin minimum separation so we don't latch onto sidelobes.
        peaks, _  = find_peaks(f0_energy,
                               height=f0_energy.max() * 0.50, distance=5)

        multi, f0_b = False, 0.0

        if len(peaks) >= 2:
            sorted_peaks  = peaks[np.argsort(f0_energy[peaks])[::-1]]
            f0_b_cand     = float(freqs[f0_mask][sorted_peaks[1]])
            primary_peak  = float(f0_energy[sorted_peaks[0]])
            secondary_peak = float(f0_energy[sorted_peaks[1]])

            # Second F0 must have a reasonable share of the primary's energy;
            # otherwise we're picking up sidelobes / leakage.
            energy_ratio = secondary_peak / (primary_peak + 1e-12)

            # Verify second F0 has its OWN harmonic series with real energy
            # (≥3 harmonics above a meaningful floor — was 2 above 1e-6 which
            # effectively matched any non-zero bin).
            mag_floor     = float(np.median(mag)) * 3.0 + 1e-10
            sec_harmonics = 0
            for n in range(2, 10):
                hf = f0_b_cand * n
                if hf > freqs.max(): break
                hm = (freqs >= hf - 2) & (freqs <= hf + 2)
                if hm.any() and mag[hm, :].mean() > mag_floor:
                    sec_harmonics += 1

            if (sec_harmonics >= 3
                    and energy_ratio >= 0.40
                    and abs(f0_a - f0_b_cand) >= 5.0):
                multi = True
                f0_b  = f0_b_cand

        if multi and f0_b > 0:
            # ── Dual-elephant source separation via competitive Wiener masking ──
            #
            # Previous approach: re-STFT the time-domain cleaned audio, binary-split
            # NMF components → both output tracks were just complements of the same
            # blended signal (not two distinct callers).
            #
            # New approach:
            # 1. Decompose the CLEANED STFT magnitude (from the pipeline's Wiener
            #    mask output) — avoids a lossy STFT/ISTFT round-trip and works
            #    directly in the frequency domain where separation is cleanest.
            # 2. Score each NMF component as a continuous weight for elephant A vs B.
            # 3. Build per-elephant "energy maps" as WEIGHTED sums of all components.
            # 4. Apply a competitive Wiener mask: each time-frequency bin is allocated
            #    to elephant A or B proportional to how much energy each "owns".
            # 5. Square the resulting masks (same sharpening as the main pipeline)
            #    to drive ambiguous bins toward silence.

            cleaned_audio = msg['cleaned']
            target_len    = len(cleaned_audio)

            # Cleaned STFT magnitude — already noise-reduced by the Wiener mask
            # (magnitude × mask from nmf_masking). Re-using it avoids introducing
            # new noise from decomposing raw original magnitude.
            cleaned_mag = msg['magnitude'] * msg['mask']   # (freq_bins, time_frames)
            phase       = msg['phase']                      # (freq_bins, time_frames)

            V     = cleaned_mag + 1e-8
            model = NMF(n_components=8, init='nndsvda', solver='mu',
                        beta_loss='kullback-leibler', max_iter=800, tol=1e-3,
                        random_state=42)
            H2 = model.fit_transform(V.T)   # (time_frames, 8)
            W2 = model.components_.T         # (freq_bins,   8)

            def score_for_f0(w_col, target_f0):
                """Continuous score: count harmonics above local floor, normalised."""
                hits = sum(
                    1 for n in range(1, 15)
                    if target_f0 * n <= freqs.max() and
                       w_col[(freqs >= target_f0*n - 3) & (freqs <= target_f0*n + 3)].max()
                       > np.percentile(w_col, 25) * 2.0
                )
                return float(hits)

            scores_a = np.array([score_for_f0(W2[:, k], f0_a) for k in range(8)],
                                 dtype=float)
            scores_b = np.array([score_for_f0(W2[:, k], f0_b) for k in range(8)],
                                 dtype=float)

            # Weighted spectral reconstructions — every component contributes to
            # BOTH elephants, weighted by how well it matches each elephant's harmonics.
            # (freq_bins × 8) × diag(scores) × (8 × time_frames) → freq × time
            sig_a = (W2 * scores_a) @ H2.T   # elephant-A energy per time-freq bin
            sig_b = (W2 * scores_b) @ H2.T   # elephant-B energy per time-freq bin

            # Competitive Wiener mask: each bin goes proportionally to its owner.
            # Squared for the same bin-hardening used in the main pipeline.
            denom  = sig_a + sig_b + 1e-8
            mask_a = (sig_a / denom) ** 2
            mask_b = (sig_b / denom) ** 2

            def recon(msk):
                c   = np.maximum(cleaned_mag * msk, 0.0) * np.exp(1j * phase)
                out = librosa.istft(c, hop_length=HOP_LENGTH, win_length=N_FFT)
                out = out.astype(np.float32)
                if len(out) < target_len:
                    out = np.pad(out, (0, target_len - len(out)))
                return out[:target_len]

            cleaned_a = recon(mask_a)
            cleaned_b = recon(mask_b)
            msg = {**msg, "cleaned": cleaned_a, "cleaned_b": cleaned_b}

        return {**msg, "multi_elephant": multi, "f0_b": f0_b}
