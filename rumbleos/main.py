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

from agents.base           import SENTINEL
from agents.preprocess     import PreprocessAgent
from agents.fingerprint    import FingerprintAgent
from agents.nmf_masking    import NMFMaskingAgent
from agents.reconstruction import ReconstructionAgent
from agents.overlap        import OverlapAgent
from agents.quality_scorer import QualityScorerAgent
from agents.sensecap       import SenseCapAgent
from agents.clustering     import ClusteringAgent

SEQUENTIAL_MODE = True    # set True to debug without multiprocessing
N_WORKERS       = 4       # match your CPU core count


def save_result(result: dict, output_dir: str):
    """Save cleaned WAV + before/after spectrogram for one call."""
    from scipy.io import wavfile
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')  # non-interactive backend for server/RPi

    out      = Path(output_dir)
    call_id  = result['call_id']
    sr       = result['sr']
    cleaned  = result['cleaned']
    original = result.get('original', cleaned)
    min_len  = min(len(original), len(cleaned))

    # Save primary cleaned WAV
    wavfile.write(str(out / f"{call_id}_clean.wav"),
                  sr, cleaned[:min_len].astype(np.float32))

    # Save second elephant if detected
    if result.get('multi_elephant') and result.get('cleaned_b') is not None:
        wavfile.write(str(out / f"{call_id}_elephant_b.wav"),
                      sr, result['cleaned_b'].astype(np.float32))

    # Before/after spectrogram comparison
    try:
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        for ax, audio, title in [
            (axes[0], original[:min_len], f"BEFORE — {result.get('noise_type','')}"),
            (axes[1], cleaned[:min_len],
             f"AFTER — F0={result.get('f0_hz',0)}Hz "
             f"SNR+{result.get('snr_improvement_db',0):.1f}dB "
             f"[{result.get('harmonics_present',0)}/{result.get('harmonics_possible',0)} harmonics]"),
        ]:
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
            if msg.get('valid') and 'cleaned' in msg:
                save_result(msg, output_dir)
            print(f"✓ {call_id} | {msg.get('noise_type')} | "
                  f"F0={msg.get('f0_hz')}Hz | "
                  f"SNR+{msg.get('snr_improvement_db')}dB | "
                  f"valid={msg.get('valid')}")
        except Exception as e:
            print(f"✗ {call_id}: {e}")

    pd.DataFrame(results).to_csv(out / "batch_results.csv", index=False)
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
        if r.get('valid') and 'cleaned' in r:
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
    pd.DataFrame(all_results).to_csv(f"{output_dir}/batch_results.csv", index=False)
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
    CSV_PATH       = "data/timestamps.csv"
    AUDIO_DIR      = "data/recordings/"
    OUTPUT_DIR     = "results/"
    CLAUDE_API_KEY = None            # set your key for AI hypotheses
    SENSECAP_PORT  = "/dev/ttyUSB0"  # change if port differs
    # ─────────────────────────────────────────────────────────────────

    if SEQUENTIAL_MODE:
        print("Running in SEQUENTIAL mode (debug)")
        results = run_sequential(CSV_PATH, AUDIO_DIR, OUTPUT_DIR)
    else:
        print("Running in PARALLEL mode (4× agents)")
        results = launch_parallel(
            CSV_PATH, AUDIO_DIR, OUTPUT_DIR,
            claude_api_key=CLAUDE_API_KEY,
            sensecap_port=SENSECAP_PORT,
        )

    print(f"\nDone. Run dashboard with: streamlit run dashboard/app.py")
