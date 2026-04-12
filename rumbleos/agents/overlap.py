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
        peaks, _  = find_peaks(f0_energy,
                               height=f0_energy.max() * 0.25, distance=3)

        multi, f0_b = False, 0.0

        if len(peaks) >= 2:
            sorted_peaks = peaks[np.argsort(f0_energy[peaks])[::-1]]
            f0_b_cand    = float(freqs[f0_mask][sorted_peaks[1]])

            # Verify second F0 has its own harmonic series
            sec_harmonics = 0
            for n in range(2, 10):
                hf = f0_b_cand * n
                if hf > freqs.max(): break
                hm = (freqs >= hf - 3) & (freqs <= hf + 3)
                if hm.any() and mag[hm, :].mean() > 1e-6:
                    sec_harmonics += 1

            if sec_harmonics >= 2 and abs(f0_a - f0_b_cand) > 3.0:
                multi = True
                f0_b  = f0_b_cand

        if multi and f0_b > 0:
            # Dual NMF: separate both callers
            cleaned_audio = msg['cleaned']
            D_clean = librosa.stft(cleaned_audio, n_fft=N_FFT, hop_length=HOP_LENGTH)
            mag2    = np.abs(D_clean)
            V       = mag2 + 1e-8

            model = NMF(n_components=8, init='nndsvda', solver='mu',
                        beta_loss='kullback-leibler', max_iter=500, random_state=42)
            H2 = model.fit_transform(V.T)
            W2 = model.components_.T

            def score_for_f0(w_col, target_f0):
                return sum(
                    1 for n in range(1, 15)
                    if target_f0 * n <= freqs.max() and
                       w_col[(freqs >= target_f0*n-3) & (freqs <= target_f0*n+3)].max()
                       > np.percentile(w_col, 25) * 2.0
                )

            scores_a = np.array([score_for_f0(W2[:,k], f0_a) for k in range(8)])
            scores_b = np.array([score_for_f0(W2[:,k], f0_b) for k in range(8)])
            comp_a   = scores_a >= scores_b

            def reconstruct_from_components(comp_mask):
                if not comp_mask.any():
                    return np.zeros(len(cleaned_audio))
                signal = W2[:, comp_mask] @ H2[:, comp_mask].T
                c_sig  = signal * np.exp(1j * np.angle(D_clean))
                return librosa.istft(c_sig, hop_length=HOP_LENGTH, win_length=N_FFT)

            cleaned_a = reconstruct_from_components(comp_a)
            cleaned_b = reconstruct_from_components(~comp_a)
            msg = {**msg, "cleaned": cleaned_a, "cleaned_b": cleaned_b}

        return {**msg, "multi_elephant": multi, "f0_b": f0_b}
