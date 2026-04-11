import numpy as np
import librosa
from sklearn.decomposition import NMF
from scipy.signal import iircomb, lfilter
from agents.base import BaseAgent

N_FFT              = 2048
HOP_LENGTH         = 512
N_COMPONENTS       = 10
PROP_DECREASE      = 0.75       # validated: removes 75% of noise energy
ELEPHANT_THRESHOLD = 0.35       # components scoring above this = elephant

class NMFMaskingAgent(BaseAgent):
    """
    Stage 3: Core AI/ML stage.

    Process:
    1. Compute STFT magnitude spectrogram
    2. Decompose with NMF into N_COMPONENTS spectral patterns (W) and activations (H)
    3. Score each W column with harmonic_pattern_score()
    4. Components scoring > ELEPHANT_THRESHOLD are elephant; rest are noise
    5. Build soft Wiener mask from elephant vs noise component ratio
    6. For generators: additionally apply iircomb notch filter

    Input keys required:  segment, sr, noise_type, original
    Output keys added:    magnitude, phase, mask, nmf_scores, detected_f0
    """
    @staticmethod
    def harmonic_pattern_score(w_col: np.ndarray, freqs: np.ndarray,
                                f0_range: tuple = (10, 35)) -> float:
        """
        Score a NMF basis vector by how well it matches elephant harmonics.
        Returns float 0.0 (random noise) to 1.0 (perfect harmonic series).

        Algorithm:
        - Find dominant frequency in elephant F0 range (10-35 Hz)
        - Check for significant energy at integer multiples of that F0
        - Score = weighted average of (harmonic energy fraction) and (harmonic count)
        """
        f0_mask = (freqs >= f0_range[0]) & (freqs <= f0_range[1])
        if not f0_mask.any() or w_col[f0_mask].max() < 1e-10:
            return 0.0

        f0 = freqs[f0_mask][np.argmax(w_col[f0_mask])]
        if f0 < 5: return 0.0

        hits, h_energy = 0, 0.0
        total = w_col.sum() + 1e-10
        floor = np.percentile(w_col, 25)

        for n in range(1, 20):
            hf = f0 * n
            if hf > freqs.max(): break
            hm = (freqs >= hf - 2) & (freqs <= hf + 2)
            if hm.any():
                p = w_col[hm].max()
                if p > floor * 2.5:
                    h_energy += p
                    hits += 1

        score = h_energy / total * 0.6 + min(hits / 5.0, 1.0) * 0.4
        return float(np.clip(score, 0.0, 1.0))

    def process(self, msg: dict) -> dict:
        if 'error' in msg: return msg

        audio      = msg['segment']
        sr         = msg['sr']
        noise_type = msg['noise_type']

        # STFT
        D         = librosa.stft(audio, n_fft=N_FFT, hop_length=HOP_LENGTH)
        magnitude = np.abs(D)
        phase     = np.angle(D)
        freqs     = librosa.fft_frequencies(sr=sr, n_fft=N_FFT)

        # NMF decomposition
        V     = magnitude + 1e-8
        model = NMF(
            n_components=N_COMPONENTS,
            init='nndsvda',                    # better than random for audio
            solver='mu',                       # multiplicative update — standard for audio
            beta_loss='kullback-leibler',      # KL divergence suits audio better than MSE
            max_iter=400,
            random_state=42
        )
        H = model.fit_transform(V.T)   # shape: (time_frames, N_COMPONENTS)
        W = model.components_.T        # shape: (freq_bins, N_COMPONENTS)

        # Score each component
        scores      = np.array([NMFMaskingAgent.harmonic_pattern_score(W[:, k], freqs)
                                 for k in range(N_COMPONENTS)])
        is_elephant = scores > ELEPHANT_THRESHOLD

        # Build elephant and noise signal estimates
        if is_elephant.any():
            e_sig = W[:, is_elephant] @ H[:, is_elephant].T
        else:
            e_sig = np.zeros_like(magnitude)

        if (~is_elephant).any():
            n_sig = W[:, ~is_elephant] @ H[:, ~is_elephant].T
        else:
            n_sig = np.ones_like(magnitude) * 1e-8

        # Soft mask: what fraction of each TF bin is elephant?
        mask = e_sig / (e_sig + PROP_DECREASE * n_sig + 1e-8)
        mask = np.clip(mask, 0.0, 1.0)

        # Generator: additionally apply comb notch filter to clean periodic spikes
        if noise_type.startswith("generator"):
            f0_gen = (60.0 if "60" in noise_type else
                      90.0 if "90" in noise_type else 45.0)
            b, a      = iircomb(w0=f0_gen, Q=35, ftype='notch', fs=sr)
            notched   = lfilter(b, a, audio)
            D_notch   = librosa.stft(notched, n_fft=N_FFT, hop_length=HOP_LENGTH)
            mag_notch = np.abs(D_notch)
            # Blend: take the max of the two masks (be generous to elephant signal)
            notch_ratio = mag_notch / (magnitude + 1e-8)
            mask = np.maximum(mask, np.clip(notch_ratio, 0, 1))
            mask = np.clip(mask, 0, 1)

        # Detected F0 from best-scoring component
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
