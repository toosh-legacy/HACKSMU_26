import numpy as np
from scipy.signal import welch
from agents.base import BaseAgent

class FingerprintAgent(BaseAgent):
    """
    Stage 2: Classify the noise type from the audio's spectral features.

    Noise signatures:
    - Generator: exact harmonic spikes at RPM multiples (60, 90, 45 Hz base)
    - Airplane: broadband energy, smooth PSD curve, dominant 80-200 Hz
    - Car: variable quasi-harmonics, non-stationary

    Input keys required:  segment, sr
    Output keys added:    noise_type (str)
    """
    def process(self, msg: dict) -> dict:
        if 'error' in msg: return msg

        audio = msg['segment']
        sr    = msg['sr']
        freqs, psd = welch(audio, fs=sr, nperseg=2048)

        def check_harmonics(f0: float, tol: float = 3.0):
            count, score = 0, 0.0
            for n in range(1, 12):
                t = f0 * n
                if t > 500: break
                band  = (freqs >= t - tol) & (freqs <= t + tol)
                floor = np.percentile(psd, 20) + 1e-10
                if band.any() and psd[band].max() > floor * 6:
                    count += 1
                    score += psd[band].max() / floor
            return count, score

        h60, s60 = check_harmonics(60.0)
        h90, s90 = check_harmonics(90.0)
        h45, s45 = check_harmonics(45.0)

        low_e  = psd[(freqs >= 80)  & (freqs <= 200)].mean()
        high_e = psd[(freqs >= 200) & (freqs <= 1000)].mean()
        ratio  = low_e / (high_e + 1e-10)
        smooth = np.std(np.diff(np.log10(psd + 1e-10)))

        if h60 >= 4 and s60 >= s90:        noise_type = "generator_60hz"
        elif h90 >= 4:                      noise_type = "generator_90hz"
        elif h45 >= 3:                      noise_type = "generator_45hz"
        elif ratio > 2.5 and smooth < 0.4: noise_type = "airplane"
        else:                               noise_type = "car"

        return {**msg, "noise_type": noise_type}
