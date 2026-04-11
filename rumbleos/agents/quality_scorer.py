import numpy as np
from scipy.signal import welch
from agents.base import BaseAgent

class QualityScorerAgent(BaseAgent):
    """
    Stage 6: Quality scoring.

    Computes SNR improvement, harmonic completeness, and call validity.
    Also fires live detection events to SenseCAP via extra_queues['sensecap_q'].

    Input keys required:  original, cleaned, sr, detected_f0, noise_type
    Output keys added:    snr_before_db, snr_after_db, snr_improvement_db,
                          f0_hz, harmonic_completeness, harmonics_present,
                          harmonics_possible, valid
    """
    @staticmethod
    def compute_snr(audio, sr, freqs, psd):
        e_band = (freqs >= 10)  & (freqs <= 500)
        n_band = (freqs >= 500) & (freqs <= 1500)
        sig = psd[e_band].mean() if e_band.any() else 1e-10
        nse = psd[n_band].mean() if n_band.any() else 1e-10
        return float(10 * np.log10(sig / (nse + 1e-10)))

    def process(self, msg: dict) -> dict:
        if 'error' in msg:
            return {**msg, "valid": False, "snr_improvement_db": 0,
                    "harmonic_completeness": 0, "f0_hz": 0}

        original = msg['original']
        cleaned  = msg['cleaned']
        sr       = msg['sr']
        min_len  = min(len(original), len(cleaned))
        orig, cln = original[:min_len], cleaned[:min_len]

        freqs, psd_o = welch(orig, fs=sr, nperseg=2048)
        freqs, psd_c = welch(cln,  fs=sr, nperseg=2048)

        snr_before = self.compute_snr(orig, sr, freqs, psd_o)
        snr_after  = self.compute_snr(cln,  sr, freqs, psd_c)

        # F0 detection on cleaned signal
        f0 = msg.get('detected_f0', 0.0)
        f0_band = (freqs >= 10) & (freqs <= 35)
        if f0 < 5 and f0_band.any() and psd_c[f0_band].max() > 1e-10:
            f0 = float(freqs[f0_band][np.argmax(psd_c[f0_band])])

        # Harmonic completeness
        h_present, h_possible = 0, 0
        noise_floor = np.percentile(psd_c, 15)
        if f0 > 5:
            for n in range(1, 20):
                hf = f0 * n
                if hf > 1000: break
                h_possible += 1
                hm = (freqs >= hf - 3) & (freqs <= hf + 3)
                if hm.any() and psd_c[hm].max() > noise_floor * 3:
                    h_present += 1

        completeness = h_present / max(h_possible, 1)
        valid = (f0 >= 10 and completeness >= 0.4 and snr_after > -20)

        # Fire live event to SenseCAP
        if 'sensecap_q' in self.extra_queues:
            try:
                self.extra_queues['sensecap_q'].put_nowait({
                    "detected":   valid,
                    "confidence": round(min(100.0, (snr_after + 40) * 2), 1),
                    "f0_hz":      round(f0, 1),
                    "noise_type": msg.get('noise_type', 'unknown'),
                })
            except Exception:
                pass  # Never block the pipeline for display

        return {
            **msg,
            "snr_before_db":         round(snr_before, 2),
            "snr_after_db":          round(snr_after, 2),
            "snr_improvement_db":    round(snr_after - snr_before, 2),
            "f0_hz":                 round(f0, 1),
            "harmonic_completeness": round(completeness, 3),
            "harmonics_present":     h_present,
            "harmonics_possible":    h_possible,
            "valid":                 valid,
        }
