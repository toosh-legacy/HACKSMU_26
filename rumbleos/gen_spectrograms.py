"""
gen_spectrograms.py — Retroactively generate {call_id}_comparison.png files.

For every call in results/batch_results_clustered.csv that is missing a
comparison PNG, this script:
  1. Loads the original raw WAV from the recordings directory (resampled to 4 kHz)
  2. Loads the corresponding *_clean.wav from results/ (resampled to 4 kHz)
  3. Extracts the [start_time, end_time] segment from both
  4. Renders the same before/after spectrogram that save_result() would produce
  5. Saves to results/{call_id}_comparison.png

Usage:
    cd rumbleos
    python gen_spectrograms.py
"""

import csv
import re
import sys
from pathlib import Path

import librosa
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

# ── Paths ──────────────────────────────────────────────────────────────────────
RESULTS_DIR   = Path(__file__).parent / "results"
RECORDINGS_DIR = Path(r"C:\Projects\HackSMU\HACKSMU_26\recordings\2026)-20260411T194946Z-3-001\Audio Files (04-10-2026)")
CSV_PATH      = RESULTS_DIR / "batch_results_clustered.csv"
TARGET_SR     = 4000


def recording_stem(call_id: str) -> str:
    """Strip the _c### suffix to get the recording stem."""
    return re.sub(r"_c\d+$", "", call_id)


def load_segment(wav_path: Path, start_sec: float, end_sec: float) -> np.ndarray:
    """Load a time-bounded mono segment resampled to TARGET_SR."""
    y, _ = librosa.load(str(wav_path), sr=TARGET_SR, mono=True,
                         offset=start_sec, duration=end_sec - start_sec)
    return y


def make_spectrogram(call_id: str, original: np.ndarray, cleaned: np.ndarray,
                     row: dict, out_dir: Path):
    """Render before/after spectrogram and save as {call_id}_comparison.png."""
    f0    = float(row.get("f0_hz") or row.get("detected_f0") or 0)
    snr_i = float(row.get("snr_improvement_db") or 0)
    h_pre = row.get("harmonics_present", "?")
    h_pos = row.get("harmonics_possible", "?")
    noise = row.get("noise_type", "")

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    for ax, audio, title in [
        (axes[0], original, f"BEFORE — {noise}"),
        (axes[1], cleaned,
         f"AFTER — F0={f0:.1f}Hz SNR+{snr_i:.1f}dB [{h_pre}/{h_pos} harmonics]"),
    ]:
        with np.errstate(divide='ignore', invalid='ignore'):
            ax.specgram(audio, NFFT=2048, Fs=TARGET_SR, noverlap=1536,
                        cmap='inferno', scale='dB', vmin=-80)
        ax.set_ylim(0, 400)
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Frequency (Hz)")
        ax.set_title(title, fontweight='bold', fontsize=10)
        if f0 > 5:
            for n in range(1, 15):
                if f0 * n > 400:
                    break
                ax.axhline(y=f0 * n, color='cyan', alpha=0.2, linewidth=0.6)

    fig.suptitle(f"Call: {call_id}", fontsize=10)
    fig.tight_layout()
    plt.savefig(str(out_dir / f"{call_id}_comparison.png"),
                dpi=150, bbox_inches='tight')
    plt.close(fig)


def resolve_original_path(audio_path_str: str) -> Path:
    """Convert the relative audio_path from CSV to an absolute Path."""
    # The CSV stores paths like: ..\recordings\...\file.wav
    # Resolve relative to the rumbleos/ directory.
    p = Path(audio_path_str)
    if p.is_absolute() and p.exists():
        return p
    # Try relative to rumbleos/
    resolved = (Path(__file__).parent / p).resolve()
    if resolved.exists():
        return resolved
    # Try just the filename in RECORDINGS_DIR
    fallback = RECORDINGS_DIR / p.name
    if fallback.exists():
        return fallback
    return resolved  # may not exist — caller handles FileNotFoundError


def main():
    if not CSV_PATH.exists():
        print(f"[gen] CSV not found: {CSV_PATH}")
        sys.exit(1)

    with open(CSV_PATH, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    missing = [r for r in rows
               if not (RESULTS_DIR / f"{r['call_id']}_comparison.png").exists()]

    if not missing:
        print("[gen] All spectrograms already present — nothing to do.")
        return

    print(f"[gen] {len(missing)} spectrograms to generate (out of {len(rows)} calls)")

    ok = skipped = errors = 0
    for row in missing:
        call_id   = row["call_id"]
        stem      = recording_stem(call_id)
        start_sec = float(row["start_time"])
        end_sec   = float(row["end_time"])

        # Resolve paths
        orig_path  = resolve_original_path(row["audio_path"])
        clean_path = RESULTS_DIR / f"{stem}_clean.wav"

        if not orig_path.exists():
            print(f"[gen] SKIP {call_id} — original not found: {orig_path}")
            skipped += 1
            continue
        if not clean_path.exists():
            print(f"[gen] SKIP {call_id} — clean wav not found: {clean_path}")
            skipped += 1
            continue

        try:
            original = load_segment(orig_path, start_sec, end_sec)
            cleaned  = load_segment(clean_path, start_sec, end_sec)

            if len(original) < 64 or len(cleaned) < 64:
                print(f"[gen] SKIP {call_id} — segment too short")
                skipped += 1
                continue

            make_spectrogram(call_id, original, cleaned, row, RESULTS_DIR)
            print(f"[gen] OK  {call_id}")
            ok += 1

        except Exception as exc:
            print(f"[gen] ERR {call_id}: {exc}")
            errors += 1

    print(f"\n[gen] Done — {ok} generated, {skipped} skipped, {errors} errors")


if __name__ == "__main__":
    main()
