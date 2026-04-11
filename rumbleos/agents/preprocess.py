import numpy as np
import librosa
from scipy.signal import butter, sosfiltfilt
from agents.base import BaseAgent

TARGET_SR     = 4000
BANDPASS_LOW  = 10
BANDPASS_HIGH = 1000
CONTEXT_SEC   = 1.5
NOISE_REF_SEC = 3.0

class PreprocessAgent(BaseAgent):
    """
    Stage 1: Load WAV, downsample to 4000 Hz, bandpass 10-1000 Hz,
    extract call segment with context, extract noise reference.

    Input keys required:  call_id, audio_path, start_time, end_time
    Output keys added:    segment, noise_ref, sr, original
    """
    def process(self, msg: dict) -> dict:
        # Load and downsample — 4000 Hz gives 1.95 Hz/bin at n_fft=2048
        y, _ = librosa.load(msg['audio_path'], sr=TARGET_SR)

        # Bandpass 10-1000 Hz (removes everything outside elephant range)
        sos = butter(N=4, Wn=[BANDPASS_LOW, BANDPASS_HIGH],
                     btype='band', fs=TARGET_SR, output='sos')
        y   = sosfiltfilt(sos, y)
        sr  = TARGET_SR

        # Extract call segment with context padding
        s = max(0,      int((msg['start_time'] - CONTEXT_SEC) * sr))
        e = min(len(y), int((msg['end_time']   + CONTEXT_SEC) * sr))
        segment = y[s:e]

        # Noise reference: 3 seconds before call (pure mechanical noise)
        ns = max(0, int((msg['start_time'] - NOISE_REF_SEC) * sr))
        ne = int(msg['start_time'] * sr)
        noise_ref = y[ns:ne] if ne > ns and (ne - ns) > sr//4 else np.zeros(sr)

        return {
            **msg,
            "segment":   segment,
            "noise_ref": noise_ref,
            "sr":        sr,
            "original":  segment.copy(),
        }
