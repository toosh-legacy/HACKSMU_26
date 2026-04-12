import numpy as np
from agents.runtime import configure_runtime

configure_runtime()

import librosa
from sklearn.decomposition import NMF
from scipy.signal import iircomb, lfilter
from agents.base import BaseAgent

N_FFT              = 2048
HOP_LENGTH         = 512
N_COMPONENTS       = 10
PROP_DECREASE      = 0.75       # validated: removes 75% of noise energy
TOP_K_ELEPHANT     = 3          # top-K NMF components classified as elephant
SPECTRAL_SUB_ALPHA = 1.2        # spectral subtraction factor (car noise only)
SPECTRAL_SUB_FLOOR = 0.25       # floor as fraction of original magnitude
TEMPORAL_WEIGHT    = 0.35       # blend weight for temporal non-stationarity score


class NMFMaskingAgent(BaseAgent):
    """
    Stage 3: Core AI/ML stage.

    Process:
    1. Spectral subtraction using noise_ref to remove stationary noise floor
    2. STFT magnitude spectrogram of the residual
    3. NMF decomposition into N_COMPONENTS spectral patterns (W) and activations (H)
    4. Score each component with harmonic_pattern_score (frequency) +
       temporal_score (time) — car RPM harmonics look harmonic but are stationary;
       elephant calls are brief localized events with non-uniform temporal activation
    5. Top-K components are elephant; rest are noise
    6. Soft Wiener mask on original magnitude
    7. For generators: additionally apply iircomb notch filter

    Input keys required:  segment, noise_ref, sr, noise_type, original
    Output keys added:    magnitude, phase, mask, nmf_scores, detected_f0
    """

    @staticmethod
    def harmonic_pattern_score(w_col: np.ndarray, freqs: np.ndarray,
                                f0_range: tuple = (10, 35)) -> float:
        """
        Score a NMF basis vector by how well it matches elephant harmonics.
        Returns float 0.0 (random noise) to 1.0 (perfect harmonic series).

        Stricter than original: tighter ±1.5 Hz tolerance and 3.5× floor
        threshold reduce false positives from car engine harmonics.
        """
        f0_mask = (freqs >= f0_range[0]) & (freqs <= f0_range[1])
        if not f0_mask.any() or w_col[f0_mask].max() < 1e-10:
            return 0.0

        f0 = freqs[f0_mask][np.argmax(w_col[f0_mask])]
        if f0 < 5:
            return 0.0

        hits, h_energy = 0, 0.0
        total = w_col.sum() + 1e-10
        floor = np.percentile(w_col, 25)

        for n in range(1, 20):
            hf = f0 * n
            if hf > freqs.max():
                break
            # Tighter tolerance: 1.5 Hz vs original 2 Hz
            hm = (freqs >= hf - 1.5) & (freqs <= hf + 1.5)
            if hm.any():
                p = w_col[hm].max()
                # Stricter floor: 3.5× vs original 2.5×
                if p > floor * 3.5:
                    h_energy += p
                    hits += 1

        score = h_energy / total * 0.6 + min(hits / 5.0, 1.0) * 0.4
        return float(np.clip(score, 0.0, 1.0))

    @staticmethod
    def temporal_score(h_col: np.ndarray) -> float:
        """
        Score a NMF activation by temporal non-stationarity.

        Elephant calls are brief localized events — their NMF activations peak
        in the middle of the segment and drop in the context padding on either
        side. Car and airplane noise is quasi-stationary across the whole window.

        High coefficient of variation (std/mean) → non-stationary → more likely elephant.
        Returns 0.0 (flat/stationary) to 1.0 (strongly non-stationary).
        """
        if h_col.max() < 1e-10:
            return 0.0
        h_norm = h_col / (h_col.max() + 1e-10)
        cv = float(np.std(h_norm) / (np.mean(h_norm) + 1e-10))
        # Clip at 2.0 before normalising so extreme spikes don't dominate
        return float(np.clip(cv, 0.0, 2.0) / 2.0)

    def process(self, msg: dict) -> dict:
        if 'error' in msg:
            return msg

        audio      = msg['segment']
        sr         = msg['sr']
        noise_type = msg['noise_type']
        noise_ref  = msg.get('noise_ref', np.array([]))

        # Full STFT on original segment — phase and magnitude kept for final mask
        D         = librosa.stft(audio, n_fft=N_FFT, hop_length=HOP_LENGTH)
        magnitude = np.abs(D)
        phase     = np.angle(D)
        freqs     = librosa.fft_frequencies(sr=sr, n_fft=N_FFT)

        # ── Spectral subtraction using noise reference (car noise only) ────────
        # noise_ref is 3s of pure mechanical noise before the call.
        # For car noise, subtracting its median spectrum reduces stationary
        # engine harmonics in the 10–35 Hz range before NMF, preventing the
        # decomposition from latching onto RPM harmonics as "elephant".
        # Not applied to airplane/generator: airplane noise_ref ≈ segment
        # magnitude (broadband stationary), over-subtraction would flatten
        # the spectrogram and kill structure needed by NMF. Generator is
        # handled by the comb notch filter later.
        is_car = (noise_type == "car")
        if is_car and len(noise_ref) >= N_FFT:
            D_nr       = librosa.stft(noise_ref, n_fft=N_FFT, hop_length=HOP_LENGTH)
            noise_spec = np.median(np.abs(D_nr), axis=1, keepdims=True)
            mag_sub    = magnitude - SPECTRAL_SUB_ALPHA * noise_spec
            mag_for_nmf = np.maximum(mag_sub, magnitude * SPECTRAL_SUB_FLOOR)
        else:
            mag_for_nmf = magnitude

        # ── NMF decomposition on noise-subtracted magnitude ─────────────────
        V     = mag_for_nmf + 1e-8
        model = NMF(
            n_components=N_COMPONENTS,
            init='nndsvda',
            solver='mu',
            beta_loss='kullback-leibler',
            max_iter=400,
            random_state=42
        )
        H = model.fit_transform(V.T)   # (time_frames, N_COMPONENTS)
        W = model.components_.T        # (freq_bins,   N_COMPONENTS)

        # ── Combined component scoring ───────────────────────────────────────
        # harmonic_pattern_score: does W[:,k] look like elephant harmonics?
        # temporal_score:         is H[:,k] non-stationary (localized event)?
        # Car RPM harmonics score well on harmonic but flat on temporal.
        # Elephant calls score on both.
        harmonic_scores = np.array([
            NMFMaskingAgent.harmonic_pattern_score(W[:, k], freqs)
            for k in range(N_COMPONENTS)
        ])
        temporal_scores = np.array([
            NMFMaskingAgent.temporal_score(H[:, k])
            for k in range(N_COMPONENTS)
        ])
        scores = ((1.0 - TEMPORAL_WEIGHT) * harmonic_scores
                  + TEMPORAL_WEIGHT        * temporal_scores)

        # Top-K: pick K highest-scoring components as elephant
        top_k_idx   = np.argsort(scores)[-TOP_K_ELEPHANT:]
        is_elephant = np.zeros(N_COMPONENTS, dtype=bool)
        is_elephant[top_k_idx] = True

        # ── Soft Wiener mask on ORIGINAL magnitude ───────────────────────────
        # W/H were fit on mag_for_nmf so they represent the noise-subtracted
        # signal space. We apply the resulting mask to the original magnitude
        # to avoid distortion artifacts from the subtraction step.
        if is_elephant.any():
            e_sig = W[:, is_elephant] @ H[:, is_elephant].T
        else:
            e_sig = np.zeros_like(magnitude)

        if (~is_elephant).any():
            n_sig = W[:, ~is_elephant] @ H[:, ~is_elephant].T
        else:
            n_sig = np.ones_like(magnitude) * 1e-8

        mask = e_sig / (e_sig + PROP_DECREASE * n_sig + 1e-8)
        mask = np.clip(mask, 0.0, 1.0)

        # ── Generator: comb notch filter ─────────────────────────────────────
        if noise_type.startswith("generator"):
            f0_gen = (60.0 if "60" in noise_type else
                      90.0 if "90" in noise_type else 45.0)
            n_harm    = max(1, round(sr / f0_gen))
            w0_eff    = sr / n_harm
            b, a      = iircomb(w0=w0_eff, Q=35, ftype='notch', fs=sr)
            notched   = lfilter(b, a, audio)
            D_notch   = librosa.stft(notched, n_fft=N_FFT, hop_length=HOP_LENGTH)
            mag_notch = np.abs(D_notch)
            notch_ratio = mag_notch / (magnitude + 1e-8)
            mask = np.maximum(mask, np.clip(notch_ratio, 0, 1))
            mask = np.clip(mask, 0, 1)

        # ── Detected F0 ───────────────────────────────────────────────────────
        best_comp = int(np.argmax(scores))
        f0_band   = (freqs >= 10) & (freqs <= 35)
        if f0_band.any() and scores[best_comp] > 0.1:
            detected_f0 = float(freqs[f0_band][np.argmax(W[f0_band, best_comp])])
        else:
            detected_f0 = 0.0

        return {
            **msg,
            "magnitude":   magnitude,
            "phase":       phase,
            "mask":        mask,
            "nmf_scores":  scores.tolist(),
            "detected_f0": detected_f0,
        }
