# RumbleOS — How to Run

Remove mechanical noise from elephant infrasound recordings and discover communication patterns.

## Prerequisites

- Python 3.10+
- ~4 GB RAM per recording for NMF processing
- WAV recordings (44 kHz or 48 kHz, mono or stereo)
- A `timestamps.csv` annotation file (see format below)

## Setup

```bash
cd rumbleos
pip install -r requirements.txt
```

> **Note:** If you see pip dependency conflicts (pandas, torch), they are harmless — the pipeline only uses the packages listed in `requirements.txt`.

## Prepare Your Data

### 1. Recordings

Place all WAV files in a single flat directory (no subdirectories):

```
recordings/
  my_file_01.wav
  my_file_02.wav
  ...
```

### 2. Timestamps CSV

Create a CSV with one row per annotated elephant call:

```csv
filename,start_time,end_time,call_type,noise_type
my_file_01.wav,30.6,33.4,rumble,car
my_file_01.wav,32.0,36.4,rumble,car
my_file_02.wav,25.7,30.2,rumble,airplane
```

| Column | Description |
|--------|-------------|
| `filename` | WAV filename (basename only, no path) |
| `start_time` | Call start in seconds |
| `end_time` | Call end in seconds |
| `call_type` | e.g. `rumble` |
| `noise_type` | `car`, `airplane`, `generator_60hz`, `generator_90hz`, `generator_45hz`, or `unknown` |

If `noise_type` is `unknown`, the pipeline auto-detects it via spectral fingerprinting.

## Run the Pipeline

```bash
cd rumbleos

CSV_PATH="data/timestamps.csv" \
AUDIO_DIR="/path/to/your/recordings" \
OUTPUT_DIR="/path/to/results" \
python main.py
```

Replace the paths with your actual directories. Results folder is created automatically if it doesn't exist.

### Example (this repo's dataset)

```bash
cd rumbleos

CSV_PATH="data/timestamps.csv" \
AUDIO_DIR="../recordings" \
OUTPUT_DIR="../results" \
python main.py
```

## Output Files

All outputs land in the `OUTPUT_DIR` you specified:

| File | Description |
|------|-------------|
| `*_clean.wav` | Noise-removed audio at native sample rate (one per recording) |
| `*_comparison.png` | Before/after spectrogram for each annotated call |
| `batch_results.csv` | Per-call metrics: F0, SNR improvement, validity |
| `batch_results_clustered.csv` | Same as above with cluster assignments |
| `cluster_summaries.json` | Per-cluster statistics (F0, duration, harmonics) |
| `tribe_edges.csv` | High-similarity call pairs (cosine > 0.80) |
| `knowledge_base.json` | Full call records with cluster and association links |
| `context_clusters.csv` | Clusters with metadata context columns |

## Configuration Flags

Edit the top of `rumbleos/main.py` to change behaviour:

```python
SEQUENTIAL_MODE = False   # True = debug mode, no multiprocessing
FULL_FILE_MODE  = True    # True = clean entire recordings (recommended)
                          # False = clean annotated windows only
N_WORKERS       = 4       # parallel workers (match your CPU core count)
```

## Optional: Gemini AI Hypotheses

Set `GEMINI_API_KEY` to generate behavioral hypotheses from cluster patterns:

```bash
GEMINI_API_KEY="your-key-here" \
CSV_PATH="data/timestamps.csv" \
AUDIO_DIR="../recordings" \
OUTPUT_DIR="../results" \
python main.py
```

Hypotheses are written to `ai_hypotheses.txt` in the output directory.

## Optional: SenseCAP Indicator Display

Connect a SenseCAP Indicator device and set the serial port:

```bash
SENSECAP_PORT="/dev/ttyUSB0" python main.py   # Linux/Mac
SENSECAP_PORT="COM3"          python main.py   # Windows
```

## Process a Single File

To run on just one recording (useful for testing):

```bash
PROCESS_ONLY="my_file_01.wav" \
CSV_PATH="data/timestamps.csv" \
AUDIO_DIR="../recordings" \
OUTPUT_DIR="../results" \
python main.py
```

## Smoke Test

Verify the core NMF stage works before a full run:

```bash
cd rumbleos
python -c "
import numpy as np
from agents.nmf_masking import NMFMaskingAgent
sr=4000; t=np.linspace(0,10,40000)
sig=sum(np.sin(2*np.pi*18*n*t)/n for n in range(1,8))
noisy=sig+np.random.randn(len(t))*0.5
r=NMFMaskingAgent(0,None,None,name='T').process({
    'segment':noisy,'sr':sr,'noise_type':'airplane',
    'original':noisy,'call_id':'test'
})
assert 14<=r['detected_f0']<=22, r['detected_f0']
print('Stage 3 OK — F0=', r['detected_f0'])
"
```

## Pipeline Stages

The system runs 7 sequential stages per recording:

1. **Preprocess** — load WAV → resample to 4 kHz → bandpass 10–1000 Hz
2. **Fingerprint** — classify noise type (car / airplane / generator)
3. **NMF Masking** — STFT → NMF decomposition → harmonic scoring → Wiener mask
4. **Reconstruction** — exponential decay fit → repair damaged harmonics
5. **Overlap** — detect two simultaneous callers → dual-NMF separation
6. **Quality Scorer** — SNR before/after, harmonic completeness, validity flag
7. **Clustering** — PCA/UMAP + K-means → tribe similarity graph

## Troubleshooting

| Error | Fix |
|-------|-----|
| `librosa.load` fails | `pip install soundfile` |
| `iircomb` not found | `pip install "scipy>=1.9"` |
| Files not found | Ensure all WAVs are in a **flat** directory (no subdirectories) |
| UMAP crashes | Pipeline automatically falls back to PCA — no action needed |
| Queue deadlock | Set `SEQUENTIAL_MODE = True` in `main.py` |
| Out of memory | Reduce `N_WORKERS` to 2 in `main.py` |
| NMF F0 wrong | Increase `max_iter` to 600 in `agents/nmf_masking.py` |
| SenseCAP not found | Try `/dev/ttyACM0` (Linux) or check Device Manager (Windows) |
