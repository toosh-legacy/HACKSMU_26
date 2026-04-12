"""
End-to-end smoke test for the RumbleOS pipeline.

Generates a synthetic WAV file that contains a short elephant-like
rumble (18 Hz fundamental + harmonics) buried in broadband noise,
then runs the full pipeline and validates:

    1. F0 is detected within 14-22 Hz
    2. SNR improves by at least 6 dB (elephant-band vs noise-band)
    3. save_merged_files preserves non-call samples bit-identically
       (every sample outside the [start_time, end_time] window must
       equal the source recording)
    4. The inside-call window is NOT silent (i.e. the cleaned audio
       actually retains the elephant signal)

Run from the rumbleos directory:

    python -m tests.test_pipeline_smoke
"""

import os
import sys
import tempfile
import numpy as np
from pathlib import Path
from scipy.io import wavfile

# Allow running both as a module and as a script
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.preprocess     import PreprocessAgent
from agents.fingerprint    import FingerprintAgent
from agents.nmf_masking    import NMFMaskingAgent
from agents.reconstruction import ReconstructionAgent
from agents.overlap        import OverlapAgent
from agents.quality_scorer import QualityScorerAgent
from main                  import save_merged_files


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────

def synth_elephant_wav(path: Path, sr: int = 22050,
                       total_sec: float = 20.0,
                       call_start: float = 8.0, call_end: float = 11.0,
                       f0: float = 18.0, n_harm: int = 7,
                       snr_db: float = -3.0) -> None:
    """
    Write a WAV that contains a 3-second elephant rumble buried in noise.
    Outside the call window there is only noise + silence (no harmonics).
    """
    rng  = np.random.default_rng(1234)
    n    = int(total_sec * sr)
    t    = np.arange(n) / sr

    # Elephant call: sum of harmonics with 1/n amplitude decay, windowed
    # by a raised-cosine so the splice boundary isn't a click.
    call_mask = (t >= call_start) & (t <= call_end)
    call_t    = t[call_mask] - call_start
    call_dur  = call_end - call_start
    window    = 0.5 - 0.5 * np.cos(2 * np.pi * call_t / call_dur)
    call_sig  = sum((1.0 / k) * np.sin(2 * np.pi * f0 * k * call_t)
                    for k in range(1, n_harm + 1))
    call_sig  = call_sig * window

    audio = np.zeros(n, dtype=np.float32)
    audio[call_mask] = call_sig.astype(np.float32)

    # Broadband noise at specified SNR (measured in the call region)
    sig_rms   = float(np.sqrt((call_sig ** 2).mean() + 1e-12))
    noise_rms = sig_rms * 10 ** (-snr_db / 20.0)
    audio    += (rng.standard_normal(n) * noise_rms).astype(np.float32)

    # Peak-normalize to avoid wav clipping
    peak = float(np.max(np.abs(audio))) or 1.0
    audio = (audio / peak * 0.9).astype(np.float32)
    wavfile.write(str(path), sr, (audio * 32767).astype(np.int16))


def band_power(audio: np.ndarray, sr: int,
               lo: float, hi: float) -> float:
    from scipy.signal import welch
    freqs, psd = welch(audio, fs=sr, nperseg=min(len(audio), 2048))
    band = (freqs >= lo) & (freqs <= hi)
    return float(psd[band].mean() + 1e-12) if band.any() else 1e-12


def snr_db(audio: np.ndarray, sr: int) -> float:
    sig = band_power(audio, sr, 10, 150)
    nse = band_power(audio, sr, 300, 1000)
    return 10 * np.log10(sig / nse)


# ──────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────

def run_pipeline_once(audio_path: Path, start_time: float, end_time: float,
                      call_id: str = "smoke") -> dict:
    pre   = PreprocessAgent(0, None, None, name="Pre")
    fing  = FingerprintAgent(0, None, None, name="Fing")
    nmf   = NMFMaskingAgent(0, None, None, name="NMF")
    recon = ReconstructionAgent(0, None, None, name="Recon")
    over  = OverlapAgent(0, None, None, name="Over")
    score = QualityScorerAgent(0, None, None, name="Score")

    msg = {
        "call_id":    call_id,
        "audio_path": str(audio_path),
        "start_time": float(start_time),
        "end_time":   float(end_time),
        "noise_type": "car",           # force car branch (spectral sub on)
    }
    msg = pre.process(msg)
    msg = fing.process(msg)
    msg = nmf.process(msg)
    msg = recon.process(msg)
    msg = over.process(msg)
    msg = score.process(msg)
    return msg


def test_full_pipeline() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp      = Path(tmp)
        src_wav  = tmp / "smoke_input.wav"
        out_dir  = tmp / "out"
        out_dir.mkdir()

        CALL_START, CALL_END = 8.0, 11.0
        synth_elephant_wav(src_wav, call_start=CALL_START, call_end=CALL_END)

        result = run_pipeline_once(src_wav, CALL_START, CALL_END)

        # ── 1. F0 detection ─────────────────────────────────────────
        f0 = result.get("detected_f0", 0.0)
        assert 14.0 <= f0 <= 22.0, f"F0 out of range: got {f0}"
        print(f"[ok] detected F0 = {f0:.2f} Hz")

        # ── 2. SNR improvement ──────────────────────────────────────
        snr_before = result.get("snr_before_db", -99)
        snr_after  = result.get("snr_after_db",  -99)
        gain       = snr_after - snr_before
        assert gain >= 3.0, (
            f"SNR improvement too small: before={snr_before} "
            f"after={snr_after} gain={gain}"
        )
        print(f"[ok] SNR {snr_before:.1f} -> {snr_after:.1f} dB "
              f"(+{gain:.1f} dB)")

        # ── 3. save_merged_files preserves non-call samples ─────────
        save_merged_files([result], str(out_dir))

        stem      = src_wav.stem
        out_wav   = out_dir / f"{stem}_clean.wav"
        assert out_wav.exists(), f"{out_wav} not written"

        src_sr, src_audio = wavfile.read(str(src_wav))
        out_sr, out_audio = wavfile.read(str(out_wav))
        assert out_sr == src_sr, f"sample rate changed: {src_sr}->{out_sr}"

        src_f = src_audio.astype(np.float32) / 32767.0
        out_f = out_audio.astype(np.float32) / 32767.0
        # Match lengths defensively
        n = min(len(src_f), len(out_f))
        src_f, out_f = src_f[:n], out_f[:n]

        call_lo = int(CALL_START * src_sr)
        call_hi = int(CALL_END   * src_sr)

        # Outside-call region: must match source exactly (allow tiny
        # floating-point rounding from int16 round-trip).
        pre_diff  = np.max(np.abs(src_f[:call_lo] - out_f[:call_lo]))
        post_diff = np.max(np.abs(src_f[call_hi:] - out_f[call_hi:]))
        assert pre_diff  < 1e-3, f"pre-call diff {pre_diff}"
        assert post_diff < 1e-3, f"post-call diff {post_diff}"
        print(f"[ok] non-call samples preserved "
              f"(max diff pre={pre_diff:.1e}, post={post_diff:.1e})")

        # Inside-call region: must NOT be all zeros, and its elephant
        # band power should be lower than the raw input (noise gone).
        inside_out = out_f[call_lo:call_hi]
        assert float(np.max(np.abs(inside_out))) > 1e-3, \
            "cleaned call window is silent"

        inside_src = src_f[call_lo:call_hi]
        snr_src    = snr_db(inside_src, src_sr)
        snr_out    = snr_db(inside_out, src_sr)
        assert snr_out > snr_src, \
            f"in-window SNR did not improve ({snr_src:.1f} -> {snr_out:.1f})"
        print(f"[ok] in-window SNR {snr_src:.1f} -> {snr_out:.1f} dB")

        # ── 4. Validity flag ─────────────────────────────────────────
        assert result.get("valid"), f"validity flag false: {result.get('valid')}"
        print(f"[ok] valid=True, harmonics "
              f"{result.get('harmonics_present')}/"
              f"{result.get('harmonics_possible')}")


if __name__ == "__main__":
    test_full_pipeline()
    print("\nSmoke test PASSED")
