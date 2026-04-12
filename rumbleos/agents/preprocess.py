import numpy as np
from agents.runtime import configure_runtime

configure_runtime()

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

    Dual-rate design: the pipeline processes a 4 kHz bandpassed copy
    (NMF and STFT need narrow-band to find elephant harmonics) but the
    final splice is written back into the ORIGINAL sample-rate audio so
    non-call regions sound exactly like the source recording.

    Input keys required:  call_id, audio_path, start_time, end_time
    Output keys added:    segment, noise_ref, sr, original,
                          seg_start_sample, seg_end_sample,
                          core_start_sample, core_end_sample,
                          source_sr, source_len, n_channels,
                          source_core_start, source_core_end

    Note: the native-SR waveform is NOT attached to the message (avoids
    queue bloat). save_merged_files() reloads each source file once from
    disk at write time, preserving channel count via n_channels.
    """
    def process(self, msg: dict) -> dict:
        # Load once at native sample rate to capture source_sr/length/channels,
        # then downsample for the pipeline and drop the native buffer.
        # mono=False so stereo/multichannel files are not silently downmixed
        # before we can record the channel count — saves_merged_files needs
        # this to splice into the correct number of channels.
        source_audio, source_sr = librosa.load(msg['audio_path'], sr=None, mono=False)
        # Normalize to 2-D (channels, samples) for uniform handling
        if source_audio.ndim == 1:
            source_audio = source_audio[np.newaxis, :]   # (1, N)
        n_channels = source_audio.shape[0]
        source_len = source_audio.shape[1]

        # Mono mix for the ML pipeline (NMF works on single channel)
        source_mono = source_audio.mean(axis=0).astype(np.float32)

        # ── Downsample to 4 kHz and bandpass for the ML pipeline ────────────
        # 4000 Hz gives 1.95 Hz/bin at n_fft=2048, ideal for resolving
        # 10-35 Hz elephant fundamentals.
        y = librosa.resample(source_mono, orig_sr=source_sr,
                             target_sr=TARGET_SR, res_type='soxr_hq')
        del source_audio, source_mono  # release native-SR buffers before queue hops
        sos = butter(N=4, Wn=[BANDPASS_LOW, BANDPASS_HIGH],
                     btype='band', fs=TARGET_SR, output='sos')
        y  = sosfiltfilt(sos, y).astype(np.float32)
        sr = TARGET_SR

        # Segment with context padding (for NMF framing)
        s = max(0,      int((msg['start_time'] - CONTEXT_SEC) * sr))
        e = min(len(y), int((msg['end_time']   + CONTEXT_SEC) * sr))
        segment = y[s:e]

        # Core call window (no padding) — the ONLY region that gets spliced
        # back into the output. The padding on either side exists purely to
        # give NMF / STFT temporal context and must not bleed Wiener
        # attenuation into the surrounding recording.
        core_s = int(msg['start_time'] * sr)
        core_e = int(msg['end_time']   * sr)
        core_s = max(s, min(e, core_s))
        core_e = max(s, min(e, core_e))

        # Same core window expressed in source (native) sample positions
        src_core_s = int(msg['start_time'] * source_sr)
        src_core_e = int(msg['end_time']   * source_sr)
        src_core_s = max(0, min(source_len, src_core_s))
        src_core_e = max(0, min(source_len, src_core_e))

        # Noise reference: 3 seconds before call (pure mechanical noise)
        ns = max(0, int((msg['start_time'] - NOISE_REF_SEC) * sr))
        ne = int(msg['start_time'] * sr)
        noise_ref = y[ns:ne] if ne > ns and (ne - ns) > sr // 4 else np.zeros(sr, dtype=np.float32)

        return {
            **msg,
            "segment":           segment,
            "noise_ref":         noise_ref,
            "sr":                sr,
            "original":          segment.copy(),
            # full_audio intentionally omitted — avoids carrying a large array
            # through every queue hop. seg_start_sample / core_start_sample
            # are offsets into the 4 kHz bandpassed stream, but that stream
            # is not needed after NMF/reconstruction (only cleaned is).
            "seg_start_sample":  s,                  # padded segment start in 4 kHz stream
            "seg_end_sample":    e,
            "core_start_sample": core_s,             # un-padded call start in 4 kHz stream
            "core_end_sample":   core_e,
            "source_sr":         source_sr,
            "source_len":        source_len,
            "n_channels":        n_channels,          # 1 for mono, 2 for stereo, etc.
            "source_core_start": src_core_s,          # call bounds in native-SR source file
            "source_core_end":   src_core_e,
        }
