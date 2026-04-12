import numpy as np
from agents.runtime import configure_runtime

configure_runtime()

import librosa
from agents.base import BaseAgent

N_FFT      = 2048
HOP_LENGTH = 512

class ReconstructionAgent(BaseAgent):
    """
    Stage 4: Harmonic reconstruction.

    For harmonics completely destroyed by noise, fit an exponential decay
    curve to surviving clean harmonics and reconstruct damaged bands.

    Input keys required:  magnitude, phase, mask, detected_f0, sr
    Output keys added:    cleaned (audio array)
    """
    def process(self, msg: dict) -> dict:
        if 'error' in msg: return msg

        mag   = msg['magnitude']
        phase = msg['phase']
        mask  = msg['mask']
        f0    = msg['detected_f0']
        sr    = msg['sr']
        freqs = librosa.fft_frequencies(sr=sr, n_fft=N_FFT)

        cleaned_mag = mag * mask

        if f0 > 5:
            h_energies, h_bins = {}, {}
            for n in range(1, 25):
                hf = f0 * n
                if hf > freqs.max(): break
                hb = np.where((freqs >= hf - 3) & (freqs <= hf + 3))[0]
                if len(hb):
                    h_bins[n]     = hb
                    h_energies[n] = float(cleaned_mag[hb, :].mean())

            if len(h_energies) >= 2:
                ns     = np.array(sorted(h_energies.keys()), dtype=float)
                Es     = np.array([h_energies[int(n)] for n in ns])
                log_Es = np.log(Es + 1e-10)
                trend  = np.polyfit(ns, log_Es, 1)  # exponential decay fit

                for n, hb in h_bins.items():
                    expected = np.exp(np.polyval(trend, n))
                    actual   = h_energies[n]

                    if actual < expected * 0.3:  # band is damaged (< 30% of expected)
                        neighbors = [k for k, e in h_energies.items()
                                     if k != n and e > expected * 0.5]
                        if neighbors:
                            nb    = min(neighbors, key=lambda k: abs(k - n))
                            nbb   = h_bins[nb]
                            scale = expected / (h_energies[nb] + 1e-10)
                            recon = cleaned_mag[nbb[:len(hb)], :] * scale
                            # Blend: 70% reconstructed, 30% original
                            cleaned_mag[hb[:len(recon)], :] = (
                                0.7 * recon +
                                0.3 * cleaned_mag[hb[:len(recon)], :]
                            )

        # Reconstruct audio via ISTFT
        cleaned_complex = cleaned_mag * np.exp(1j * phase)
        cleaned_audio   = librosa.istft(cleaned_complex,
                                        hop_length=HOP_LENGTH, win_length=N_FFT)
        return {**msg, "cleaned": cleaned_audio}
