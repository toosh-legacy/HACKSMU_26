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
    def compute_snr(audio, sr, freqs, psd, f0: float = 0.0):
        """
        Tonal SNR in dB: power AT elephant harmonic frequencies vs power
        IN BETWEEN them. If an f0 is known we use harmonic-vs-inter-harmonic
        which is robust to noise that happens to share the signal band
        (e.g. generator RPM and its subharmonics) — a plain band-energy
        SNR goes negative in that case when the NMF correctly removes
        the in-band noise.

        If no f0 is available we fall back to the original broadband
        elephant-band (10-150 Hz) vs out-of-band (300-1000 Hz) ratio.
        """
        if f0 >= 5.0:
            harm_pow, between_pow, n_hits, n_gaps = 0.0, 0.0, 0, 0
            for k in range(1, 16):
                hf = f0 * k
                if hf > 950:
                    break
                hm = (freqs >= hf - 2.5) & (freqs <= hf + 2.5)
                gm = (freqs >= hf + 3.0) & (freqs <= hf + (f0 - 3.0))
                if hm.any():
                    harm_pow += float(psd[hm].max())
                    n_hits   += 1
                if gm.any():
                    between_pow += float(psd[gm].mean())
                    n_gaps      += 1
            if n_hits and n_gaps:
                sig = harm_pow / n_hits
                nse = between_pow / n_gaps
                return float(10 * np.log10((sig + 1e-12) / (nse + 1e-12)))

        # Fallback: broadband ratio
        e_band = (freqs >= 10)  & (freqs <= 150)
        n_band = (freqs >= 300) & (freqs <= 1000)
        sig = psd[e_band].mean() if e_band.any() else 1e-10
        nse = psd[n_band].mean() if n_band.any() else 1e-10
        return float(10 * np.log10((sig + 1e-12) / (nse + 1e-12)))

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

        # Determine f0 first so SNR can use harmonic-based scoring
        f0 = msg.get('detected_f0', 0.0)
        f0_band = (freqs >= 10) & (freqs <= 35)
        if f0 < 5 and f0_band.any() and psd_c[f0_band].max() > 1e-10:
            f0 = float(freqs[f0_band][np.argmax(psd_c[f0_band])])

        snr_before = self.compute_snr(orig, sr, freqs, psd_o, f0=f0)
        snr_after  = self.compute_snr(cln,  sr, freqs, psd_c, f0=f0)

        # SNR degradation guard: if the pipeline made the audio worse by more
        # than 0.1 dB, revert the output to the original segment.  This handles
        # cases where NMF incorrectly selected noise components as "elephant"
        # and the Wiener mask amplified noise instead of suppressing it.
        reverted = False
        if snr_after < snr_before - 0.1:
            cln       = orig.copy()
            snr_after = snr_before  # signal is now untouched
            reverted  = True

        # Harmonic completeness — a harmonic "counts" if its peak in the
        # cleaned signal exceeds the noise floor.
        #
        # Noise floor reference: take the LARGER of the cleaned out-of-band
        # mean and 10% of the original out-of-band mean.  An aggressive Wiener
        # mask can zero the cleaned PSD entirely (noise_floor → 0), making
        # "psd > noise_floor * 6" trivially True or False for both signal and
        # inter-harmonic bins, which destabilises the completeness count.
        # Using the original as a secondary floor anchors the threshold to a
        # meaningful physical energy level.
        freqs_hc, psd_hc = welch(cln,  fs=sr, nperseg=2048)
        _,        psd_orig_ref = welch(orig, fs=sr, nperseg=2048)
        h_present, h_possible = 0, 0
        out_band = (freqs_hc >= 300) & (freqs_hc <= 1000)
        noise_floor_cln  = (float(np.mean(psd_hc[out_band]))
                            if out_band.any() else float(np.percentile(psd_hc, 25)))
        noise_floor_orig = (float(np.mean(psd_orig_ref[out_band]))
                            if out_band.any() else float(np.percentile(psd_orig_ref, 25)))
        noise_floor = max(noise_floor_cln, noise_floor_orig * 0.10, 1e-15)
        if f0 > 5:
            for n in range(1, 20):
                hf = f0 * n
                if hf > 1000: break
                h_possible += 1
                hm = (freqs_hc >= hf - 3) & (freqs_hc <= hf + 3)
                if hm.any() and psd_hc[hm].max() > noise_floor * 4:
                    h_present += 1

        completeness = h_present / max(h_possible, 1)
        # Reverted calls still contain a real elephant call (just undenoised),
        # so they are valid for clustering/analysis — drop the `not reverted`
        # gate.  Lowered completeness threshold from 0.35 → 0.20: the Wiener
        # mask can suppress high-frequency harmonics even on good calls,
        # causing false invalids when SNR improvement is clearly positive.
        valid = (f0 >= 10 and completeness >= 0.20 and snr_after > -20)

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
            "cleaned":               cln,         # may be reverted to original
            "snr_before_db":         round(snr_before, 2),
            "snr_after_db":          round(snr_after, 2),
            "snr_improvement_db":    round(snr_after - snr_before, 2),
            "f0_hz":                 round(f0, 1),
            "harmonic_completeness": round(completeness, 3),
            "harmonics_present":     h_present,
            "harmonics_possible":    h_possible,
            "valid":                 valid,
            "reverted":              reverted,    # True = pipeline degraded, used original
        }
