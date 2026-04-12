"""
RumbleOS Main Launcher
Wires all 9 agents together and runs the full pipeline.

Usage:
    python main.py

Configure paths at the bottom of this file.

SEQUENTIAL_MODE = True skips multiprocessing — use this to debug.
"""

import multiprocessing as mp
from pathlib import Path
import pandas as pd
import numpy as np
import time
import librosa
from collections import Counter
from scipy.signal import butter, sosfiltfilt
from scipy.io import wavfile

from agents.runtime        import configure_runtime
from agents.serialization  import tabular_result
from agents.base           import SENTINEL
from agents.preprocess     import PreprocessAgent
from agents.fingerprint    import FingerprintAgent
from agents.nmf_masking    import NMFMaskingAgent
from agents.reconstruction import ReconstructionAgent
from agents.overlap        import OverlapAgent
from agents.quality_scorer import QualityScorerAgent
from agents.sensecap       import SenseCapAgent
from agents.clustering     import ClusteringAgent

configure_runtime()

SEQUENTIAL_MODE = True    # set True to debug without multiprocessing
FULL_FILE_MODE  = True    # process entire WAV files (not just annotated windows)
N_WORKERS       = 4       # match your CPU core count


def save_result(result: dict, output_dir: str):
    """Save before/after spectrogram for one call (diagnostic only).

    WAV output is handled by save_merged_files() which writes one
    *_clean.wav per source recording with every call spliced in.
    """
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')  # non-interactive backend for server/RPi

    out      = Path(output_dir)
    call_id  = result['call_id']
    sr       = result['sr']
    cleaned  = result['cleaned']
    original = result.get('original', cleaned)

    # Before/after spectrogram comparison
    try:
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        for ax, audio, title in [
            (axes[0], original, f"BEFORE — {result.get('noise_type','')}"),
            (axes[1], cleaned,
             f"AFTER — F0={result.get('f0_hz',0)}Hz "
             f"SNR+{result.get('snr_improvement_db',0):.1f}dB "
             f"[{result.get('harmonics_present',0)}/{result.get('harmonics_possible',0)} harmonics]"),
        ]:
            # scale='dB' calls log10 internally; silence bins produce 0 → -inf.
            # Suppress the divide-by-zero RuntimeWarning — vmin=-80 clips it anyway.
            with np.errstate(divide='ignore', invalid='ignore'):
                ax.specgram(audio, NFFT=2048, Fs=sr, noverlap=1536,
                            cmap='inferno', scale='dB', vmin=-80)
            ax.set_ylim(0, 400)
            ax.set_xlabel("Time (s)")
            ax.set_ylabel("Frequency (Hz)")
            ax.set_title(title, fontweight='bold', fontsize=10)
            f0 = result.get('f0_hz', 0)
            if f0 > 5:
                for n in range(1, 15):
                    if f0 * n > 400: break
                    ax.axhline(y=f0*n, color='cyan', alpha=0.2, linewidth=0.6)
        fig.suptitle(f"Call: {call_id}", fontsize=10)
        fig.tight_layout()
        plt.savefig(str(out / f"{call_id}_comparison.png"),
                    dpi=150, bbox_inches='tight')
        plt.close(fig)
    except Exception as e:
        print(f"[save] spectrogram failed for {call_id}: {e}")


def save_merged_files(results: list, output_dir: str):
    """Write one *_clean.wav per source recording at NATIVE sample rate.

    For every source file we reload the pristine original-SR waveform
    from disk (avoids carrying a huge array through every queue hop).
    For each detected call we take the 4 kHz cleaned core (no padding),
    upsample to source rate, and overwrite only the [start_time, end_time]
    window.  Non-call regions are preserved from the original int16 samples
    without floating-point round-trip.

    Stereo / multichannel: the cleaned signal is mono; it is broadcast to
    all source channels so non-call stereo imaging is untouched.

    Overlapping annotations: calls are written in ascending snr_after_db
    order so the highest-confidence cleaned segment wins the overlap.
    Detected overlaps are logged as warnings.
    """
    import librosa
    from scipy.io import wavfile
    from collections import defaultdict

    out     = Path(output_dir)
    by_file = defaultdict(list)
    for r in results:
        if 'cleaned' in r and r.get('source_sr') is not None:
            by_file[r['audio_path']].append(r)

    for audio_path, calls in by_file.items():
        source_sr = calls[0]['source_sr']
        proc_sr   = calls[0]['sr']
        n_channels = calls[0].get('n_channels', 1)

        # Load native int16 samples via scipy to avoid float quantization
        # on non-call regions.  Falls back to librosa for non-PCM formats.
        try:
            file_sr, native_int = wavfile.read(audio_path)
            source_sr = file_sr
            # Normalise to float32 in [-1, 1] for arithmetic, but we'll
            # write back from integer so untouched regions are bit-perfect.
            if native_int.dtype == np.int16:
                native_f = native_int.astype(np.float32) / 32768.0
                int_dtype = np.int16
                int_scale = 32767
            elif native_int.dtype == np.int32:
                native_f = native_int.astype(np.float32) / 2147483648.0
                int_dtype = np.int32
                int_scale = 2147483647
            else:
                native_f  = native_int.astype(np.float32)
                int_dtype = np.int16
                int_scale = 32767
        except Exception:
            try:
                native_f, file_sr = librosa.load(audio_path, sr=None, mono=False)
                source_sr = file_sr
                if native_f.ndim == 1:
                    native_f = native_f[np.newaxis, :]
                int_dtype = np.int16
                int_scale = 32767
            except Exception as exc:
                print(f"[save] could not reload {audio_path}: {exc}")
                continue

        # Ensure 2-D (channels, samples)
        if native_f.ndim == 1:
            native_f = native_f[np.newaxis, :]

        # Start with SILENCE — non-call regions will remain zero.
        # Only the cleaned elephant call windows are written in.
        native_int_out = np.zeros_like((native_f * int_scale).astype(int_dtype))

        merged_b_int = None

        # Detect timestamp overlaps — warn, then write ascending-SNR order
        # so the highest-quality clean segment wins the overlapping region.
        sorted_calls = sorted(calls, key=lambda x: x.get('snr_after_db', 0))
        written_regions = []  # list of (start, end) native-sample intervals
        for r in sorted_calls:
            src_s = r.get('source_core_start')
            src_e = r.get('source_core_end')
            if src_s is not None and src_e is not None:
                for ws, we in written_regions:
                    if src_s < we and src_e > ws:
                        print(f"[save] WARNING overlap detected in {Path(audio_path).name}: "
                              f"[{ws},{we}) vs [{src_s},{src_e}) — higher-SNR call wins")
                written_regions.append((src_s, src_e))

        for r in sorted_calls:
            src_s = r.get('source_core_start')
            src_e = r.get('source_core_end')
            core_s_4k = r.get('core_start_sample')
            core_e_4k = r.get('core_end_sample')
            seg_s_4k  = r.get('seg_start_sample')
            if None in (src_s, src_e, core_s_4k, core_e_4k, seg_s_4k):
                continue
            if src_e <= src_s or core_e_4k <= core_s_4k:
                continue

            cleaned = r['cleaned']  # 4 kHz, length == padded segment
            lo = core_s_4k - seg_s_4k
            hi = core_e_4k - seg_s_4k
            core_cleaned = cleaned[lo:hi]
            if len(core_cleaned) == 0:
                continue

            # Upsample cleaned core back to native sample rate
            if source_sr != proc_sr:
                core_up = librosa.resample(core_cleaned.astype(np.float32),
                                           orig_sr=proc_sr, target_sr=source_sr,
                                           res_type='soxr_hq')
            else:
                core_up = core_cleaned.astype(np.float32)

            # Length-match to the source window
            target_len = src_e - src_s
            if len(core_up) >= target_len:
                core_up = core_up[:target_len]
            else:
                core_up = np.pad(core_up, (0, target_len - len(core_up)))

            # Broadcast mono cleaned signal to all source channels
            core_int = np.clip(core_up * int_scale, -int_scale, int_scale).astype(int_dtype)
            for ch in range(native_int_out.shape[0]):
                native_int_out[ch, src_s:src_e] = core_int

            # Second elephant track (multi-elephant overlap resolution)
            if r.get('multi_elephant') and r.get('cleaned_b') is not None:
                if merged_b_int is None:
                    merged_b_int = np.zeros_like((native_f * int_scale).astype(int_dtype))
                core_b = r['cleaned_b'][lo:hi]
                if source_sr != proc_sr:
                    core_b_up = librosa.resample(core_b.astype(np.float32),
                                                 orig_sr=proc_sr, target_sr=source_sr,
                                                 res_type='soxr_hq')
                else:
                    core_b_up = core_b.astype(np.float32)
                if len(core_b_up) >= target_len:
                    core_b_up = core_b_up[:target_len]
                else:
                    core_b_up = np.pad(core_b_up, (0, target_len - len(core_b_up)))
                core_b_int = np.clip(core_b_up * int_scale, -int_scale, int_scale).astype(int_dtype)
                for ch in range(merged_b_int.shape[0]):
                    merged_b_int[ch, src_s:src_e] = core_b_int

        stem = Path(audio_path).stem

        # Write: squeeze to (samples,) for mono, (samples, channels) for multi
        def to_write_shape(arr2d):
            if arr2d.shape[0] == 1:
                return arr2d[0]           # mono → 1-D
            return arr2d.T                # stereo → (samples, channels)

        wavfile.write(str(out / f"{stem}_clean.wav"), source_sr,
                      to_write_shape(native_int_out))
        n = len(calls)
        n_samp = native_int_out.shape[1]
        print(f"[save] {stem}_clean.wav  ({n} call{'s' if n != 1 else ''}, "
              f"{n_samp/source_sr:.1f}s @ {source_sr} Hz, "
              f"{native_int_out.shape[0]}ch)")

        if merged_b_int is not None:
            wavfile.write(str(out / f"{stem}_clean_b.wav"), source_sr,
                          to_write_shape(merged_b_int))
            print(f"[save] {stem}_clean_b.wav (multi-elephant track)")


def run_full_file_cleaning(csv_path, audio_dir, output_dir):
    """Clean entire WAV files across every second of audio.

    Why this exists:
        The per-call pipeline (run_sequential) only processes annotated windows
        from timestamps.csv — everything else stays noisy.  This function
        treats timestamps.csv as reference data only: it extracts the noise type
        per file and a noise reference sample, then runs NMF on 20-second
        sliding windows across the FULL recording.  The Wiener mask naturally
        passes elephant harmonics and silences mechanical noise everywhere —
        detected or not.

    Output:
        One *_clean.wav per source file at native sample rate.
        Non-elephant regions → near silence (mask ≈ 0).
        Elephant regions     → cleaned harmonic signal.

    After full-file cleaning, a per-call scoring pass still runs on the
    annotated windows so the clustering agent has quality metrics to work with.
    """
    TARGET_SR     = 4000
    BANDPASS_LOW  = 10
    BANDPASS_HIGH = 1000

    df  = pd.read_csv(csv_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Build per-file metadata from timestamps
    file_meta = {}
    for _, row in df.iterrows():
        fn = row['filename']
        if fn not in file_meta:
            file_meta[fn] = {'noise_types': [], 'first_call': float('inf')}
        file_meta[fn]['noise_types'].append(row.get('noise_type', 'unknown'))
        file_meta[fn]['first_call'] = min(file_meta[fn]['first_call'],
                                          float(row['start_time']))

    nmf_agent = NMFMaskingAgent(0, None, None, name="NMF")

    for filename, meta in file_meta.items():
        audio_path = Path(audio_dir) / filename
        if not audio_path.exists():
            print(f"[full] SKIP {filename} — not found")
            continue

        noise_type = Counter(meta['noise_types']).most_common(1)[0][0]
        first_call = meta['first_call']
        print(f"[full] {filename}  noise={noise_type}  first_call={first_call:.1f}s")

        # ── Load at native sample rate ────────────────────────────────
        try:
            file_sr, native_int = wavfile.read(str(audio_path))
            if native_int.dtype == np.int16:
                native_f = native_int.astype(np.float32) / 32768.0
                int_dtype, int_scale = np.int16, 32767
            elif native_int.dtype == np.int32:
                native_f = native_int.astype(np.float32) / 2147483648.0
                int_dtype, int_scale = np.int32, 2147483647
            else:
                native_f = native_int.astype(np.float32)
                int_dtype, int_scale = np.int16, 32767
        except Exception:
            native_f, file_sr = librosa.load(str(audio_path), sr=None, mono=False)
            int_dtype, int_scale = np.int16, 32767

        if native_f.ndim == 1:
            native_f = native_f[np.newaxis, :]
        n_channels = native_f.shape[0]
        native_len = native_f.shape[1]

        # ── Downsample to 4 kHz + bandpass for the ML pipeline ───────
        mono = native_f.mean(axis=0).astype(np.float32)
        y    = librosa.resample(mono, orig_sr=file_sr, target_sr=TARGET_SR,
                                res_type='soxr_hq')
        sos  = butter(4, [BANDPASS_LOW, BANDPASS_HIGH],
                      btype='band', fs=TARGET_SR, output='sos')
        y    = sosfiltfilt(sos, y).astype(np.float32)
        proc_len = len(y)

        # ── Noise reference: up to 3 s before first annotated call ───
        ne = int(first_call * TARGET_SR)
        ns = max(0, ne - 3 * TARGET_SR)
        noise_ref = (y[ns:ne]
                     if ne > ns and (ne - ns) > TARGET_SR // 4
                     else np.zeros(TARGET_SR * 3, dtype=np.float32))

        # ── Run full file through NMF in one shot ────────────────────
        # No windowing, no overlap-add.  One STFT on the entire signal,
        # NMF decomposes every frame at once, Wiener mask decides
        # frame-by-frame what passes through.  No human-defined cuts.
        try:
            result      = nmf_agent.process({
                'segment':    y,
                'noise_ref':  noise_ref,
                'sr':         TARGET_SR,
                'noise_type': noise_type,
                'original':   y.copy(),
                'call_id':    Path(filename).stem,
            })
            cleaned_mag = result['magnitude'] * result['mask']
            out_4k      = librosa.istft(
                cleaned_mag * np.exp(1j * result['phase']),
                hop_length=512, win_length=2048).astype(np.float32)
        except Exception as exc:
            print(f"  NMF failed: {exc} — writing silence")
            out_4k = np.zeros(proc_len, dtype=np.float32)

        # ── Upsample back to native SR ────────────────────────────────
        out_native = (librosa.resample(out_4k, orig_sr=TARGET_SR,
                                       target_sr=file_sr, res_type='soxr_hq')
                      if file_sr != TARGET_SR else out_4k)

        if len(out_native) >= native_len:
            out_native = out_native[:native_len]
        else:
            out_native = np.pad(out_native, (0, native_len - len(out_native)))

        # ── Write ─────────────────────────────────────────────────────
        out_int   = np.clip(out_native * int_scale,
                            -int_scale, int_scale).astype(int_dtype)
        out_multi = np.tile(out_int[np.newaxis, :], (n_channels, 1))

        def _shape(arr2d):
            return arr2d[0] if arr2d.shape[0] == 1 else arr2d.T

        stem = Path(filename).stem
        wavfile.write(str(out / f"{stem}_clean.wav"), file_sr, _shape(out_multi))
        print(f"[full]   done {stem}_clean.wav  "
              f"({native_len/file_sr:.1f}s @ {file_sr}Hz, {n_channels}ch)")

    # ── Per-call scoring pass for clustering ─────────────────────────────
    # Timestamps are used here purely to measure cleaning quality at known
    # call locations and feed the clustering agent with F0/SNR features.
    print("\n[full] Running per-call scoring for clustering metrics...")
    pre_agent   = PreprocessAgent(0, None, None, name="Pre")
    fing_agent  = FingerprintAgent(0, None, None, name="Fing")
    recon_agent = ReconstructionAgent(0, None, None, name="Recon")
    over_agent  = OverlapAgent(0, None, None, name="Over")
    score_agent = QualityScorerAgent(0, None, None, name="Score")
    score_results = []

    for i, row in df.iterrows():
        call_id = f"{Path(row['filename']).stem}_c{i:03d}"
        job = {
            "call_id":    call_id,
            "audio_path": str(Path(audio_dir) / row['filename']),
            "start_time": float(row['start_time']),
            "end_time":   float(row['end_time']),
            "noise_type": row.get('noise_type'),
        }
        try:
            msg = pre_agent.process(job)
            msg = fing_agent.process(msg)
            msg = nmf_agent.process(msg)
            msg = recon_agent.process(msg)
            msg = over_agent.process(msg)
            msg = score_agent.process(msg)
            score_results.append(msg)
            print(f"  OK {call_id} | F0={msg.get('f0_hz')}Hz | "
                  f"SNR+{msg.get('snr_improvement_db')}dB | valid={msg.get('valid')}")
        except Exception as exc:
            print(f"  FAIL {call_id}: {exc}")

    pd.DataFrame([tabular_result(r) for r in score_results]).to_csv(
        out / "batch_results.csv", index=False)

    try:
        q_clust = mp.Queue(maxsize=1)
        cluster = ClusteringAgent(q_clust, output_dir)
        cluster.start()
        q_clust.put(score_results)
        cluster.join(timeout=120)
    except Exception as exc:
        print(f"[Main] clustering skipped: {exc}")

    return score_results


def run_sequential(csv_path, audio_dir, output_dir):
    """Sequential mode — no multiprocessing. Good for debugging."""
    pre   = PreprocessAgent(0, None, None, name="Pre")
    fing  = FingerprintAgent(0, None, None, name="Fing")
    nmf   = NMFMaskingAgent(0, None, None, name="NMF")
    recon = ReconstructionAgent(0, None, None, name="Recon")
    over  = OverlapAgent(0, None, None, name="Over")
    score = QualityScorerAgent(0, None, None, name="Score")

    df  = pd.read_csv(csv_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    results = []

    for i, row in df.iterrows():
        call_id = f"{Path(row['filename']).stem}_c{i:03d}"
        job = {
            "call_id":    call_id,
            "audio_path": str(Path(audio_dir) / row['filename']),
            "start_time": float(row['start_time']),
            "end_time":   float(row['end_time']),
            "noise_type": row['noise_type'] if 'noise_type' in row else None,
        }
        try:
            msg = pre.process(job)
            msg = fing.process(msg)
            msg = nmf.process(msg)
            msg = recon.process(msg)
            msg = over.process(msg)
            msg = score.process(msg)
            results.append(msg)
            if 'cleaned' in msg:
                save_result(msg, output_dir)
            print(f"OK {call_id} | {msg.get('noise_type')} | "
                  f"F0={msg.get('f0_hz')}Hz | "
                  f"SNR+{msg.get('snr_improvement_db')}dB | "
                  f"valid={msg.get('valid')}")
        except Exception as e:
            print(f"FAIL {call_id}: {e}")

    pd.DataFrame([tabular_result(r) for r in results]).to_csv(
        out / "batch_results.csv", index=False)

    # Write one *_clean.wav per source recording with all calls spliced in
    save_merged_files(results, output_dir)

    try:
        q_clust = mp.Queue(maxsize=1)
        cluster = ClusteringAgent(q_clust, output_dir)
        cluster.start()
        q_clust.put(results)
        cluster.join(timeout=60)
    except Exception as e:
        print(f"[Main] clustering skipped in sequential mode: {e}")
    return results


def launch_parallel(csv_path, audio_dir, output_dir,
                    claude_api_key=None, sensecap_port='/dev/ttyUSB0'):
    """Parallel mode — 9 agents, 4× speedup."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    N = N_WORKERS

    # Create queues
    q_pre   = mp.Queue(maxsize=80)
    q_fing  = mp.Queue(maxsize=80)
    q_nmf   = mp.Queue(maxsize=80)
    q_recon = mp.Queue(maxsize=80)
    q_over  = mp.Queue(maxsize=80)
    q_score = mp.Queue(maxsize=80)
    q_sense = mp.Queue(maxsize=300)
    q_res   = mp.Queue(maxsize=300)
    q_clust = mp.Queue(maxsize=1)

    # Spawn agents
    agents = []
    for i in range(N):
        agents += [
            PreprocessAgent(i,    q_pre,   q_fing,  name="Pre"),
            FingerprintAgent(i,   q_fing,  q_nmf,   name="Fing"),
            NMFMaskingAgent(i,    q_nmf,   q_recon, name="NMF"),
            ReconstructionAgent(i,q_recon, q_over,  name="Recon"),
            QualityScorerAgent(i, q_score, q_res,
                               extra_queues={"sensecap_q": q_sense},
                               name="Score"),
        ]
    for i in range(2):
        agents.append(OverlapAgent(i, q_over, q_score, name="Over"))
    agents.append(SenseCapAgent(q_sense, port=sensecap_port))
    agents.append(ClusteringAgent(q_clust, output_dir, claude_api_key))

    for a in agents: a.start()
    print(f"[Main] {len(agents)} agents started")

    # Dispatch all jobs
    df    = pd.read_csv(csv_path)
    total = len(df)
    for i, row in df.iterrows():
        q_pre.put({
            "call_id":    f"{Path(row['filename']).stem}_c{i:03d}",
            "audio_path": str(Path(audio_dir) / row['filename']),
            "start_time": float(row['start_time']),
            "end_time":   float(row['end_time']),
            "noise_type": row['noise_type'] if 'noise_type' in row else None,
        })
    print(f"[Main] {total} jobs dispatched")

    # Collect results
    all_results = []
    t0 = time.time()
    while len(all_results) < total:
        try:
            r = q_res.get(timeout=300)
        except Exception:
            print("[Main] timeout waiting for results — check for agent errors")
            break
        all_results.append(r)
        if 'cleaned' in r:
            save_result(r, output_dir)
        done = len(all_results)
        if done % 25 == 0 or done == total:
            elapsed = time.time() - t0
            rate    = done / (elapsed + 1e-5)
            eta     = (total - done) / (rate + 1e-5)
            valid_n = sum(1 for x in all_results if x.get('valid'))
            print(f"[Main] {done}/{total} | {rate:.1f}/s | ETA {eta:.0f}s | valid={valid_n}")

    # Trigger clustering
    q_clust.put(all_results)

    # Shutdown workers
    for _ in range(N): q_pre.put(SENTINEL)
    for _ in range(N): q_fing.put(SENTINEL)
    for _ in range(N): q_nmf.put(SENTINEL)
    for _ in range(N): q_recon.put(SENTINEL)
    for _ in range(2): q_over.put(SENTINEL)
    for _ in range(N): q_score.put(SENTINEL)
    q_sense.put(SENTINEL)
    for a in agents: a.join(timeout=30)

    # Final summary
    pd.DataFrame([tabular_result(r) for r in all_results]).to_csv(
        f"{output_dir}/batch_results.csv", index=False)

    # Write one *_clean.wav per source recording with all calls spliced in
    save_merged_files(all_results, output_dir)

    valid_n     = sum(1 for r in all_results if r.get('valid'))
    elapsed     = time.time() - t0
    noise_types = set(r.get('noise_type', '?') for r in all_results)
    multi_n     = sum(1 for r in all_results if r.get('multi_elephant'))

    print(f"\n{'='*60}")
    print(f"RumbleOS COMPLETE")
    print(f"  Total calls:       {total}")
    print(f"  Valid (cleaned):   {valid_n}")
    print(f"  Multi-elephant:    {multi_n}")
    print(f"  Noise categories:  {noise_types}")
    print(f"  Time:              {elapsed:.1f}s ({total/elapsed:.1f} calls/s)")
    print(f"  Results in:        {output_dir}/")
    print(f"{'='*60}")
    return all_results


if __name__ == "__main__":
    # ── CONFIGURE THESE ──────────────────────────────────────────────
    CSV_PATH       = r"C:\Users\tusha\Documents\hackathons\smu\HACKSMU_26\rumbleos\data\timestamps.csv"
    AUDIO_DIR      = r"C:\Users\tusha\Documents\hackathons\smu\HACKSMU_26\recordings\2026)-20260411T194946Z-3-001\Audio Files (04-10-2026)"
    OUTPUT_DIR     = r"C:\Users\tusha\Documents\hackathons\smu\HACKSMU_26\rumbleos\results"
    CLAUDE_API_KEY = None            # set your key for AI hypotheses
    SENSECAP_PORT  = "/dev/ttyUSB0"  # change if port differs
    # ─────────────────────────────────────────────────────────────────

    if FULL_FILE_MODE:
        print("Running in FULL-FILE mode (clean entire recordings)")
        results = run_full_file_cleaning(CSV_PATH, AUDIO_DIR, OUTPUT_DIR)
    elif SEQUENTIAL_MODE:
        print("Running in SEQUENTIAL mode (annotated windows only — debug)")
        results = run_sequential(CSV_PATH, AUDIO_DIR, OUTPUT_DIR)
    else:
        print("Running in PARALLEL mode (4× agents)")
        results = launch_parallel(
            CSV_PATH, AUDIO_DIR, OUTPUT_DIR,
            claude_api_key=CLAUDE_API_KEY,
            sensecap_port=SENSECAP_PORT,
        )

    print(f"\nDone. Run dashboard with: streamlit run dashboard/app.py")
