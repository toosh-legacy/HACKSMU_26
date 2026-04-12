---
name: build-frontend
description: Build the RumbleOS Next.js frontend with warm elephant-themed UI
user_invocable: true
trigger: /build-frontend
---

# Build RumbleOS Frontend

Build a Next.js 14 (App Router) + TypeScript + Tailwind CSS frontend for the RumbleOS elephant infrasound research platform. Warm earth-tone color scheme.

## Tech Stack
- Next.js 14 (App Router) + TypeScript
- Tailwind CSS with custom warm palette
- Static data from `results/` (JSON, CSV, PNG, WAV) — no backend needed
- papaparse for CSV, d3-force or vis-network for graph viz
- Optional: framer-motion for transitions

## Color Palette (Tailwind config)

| Token   | Hex       | Use                        |
|---------|-----------|----------------------------|
| cream   | #FFF8F0   | Page background            |
| orange  | #D4782F   | Primary buttons, headings  |
| brown   | #8B5E3C   | Secondary text, borders    |
| amber   | #F5A623   | Accents, highlights, hover |
| dark    | #3D2B1F   | Body text                  |
| card    | #FEF0E1   | Card backgrounds           |

## Pages to Build

### 1. Landing (`/`)
- Hero: "RumbleOS" title + tagline "Decoding elephant voices hidden in noise"
- Animated waveform (CSS or canvas)
- Stats bar: calls processed, valid calls, avg SNR gain (from batch_results.csv)
- CTA button → Explorer

### 2. Pipeline (`/pipeline`)
- Horizontal 7-stage flowchart: Preprocess → Fingerprint → NMF → Reconstruct → Overlap → Quality → Clustering
- Click stage → slide-out panel: what it does, key params, input/output format
- Stage status badges if run data exists

### 3. Explorer (`/explorer`)
- Left sidebar: call list with search/filter (noise type, valid, cluster)
- Center: before/after spectrogram (load `{call_id}_comparison.png`)
- Audio player: play cleaned WAV (`{call_id}_clean.wav`) in browser via `<audio>`
- Right panel: metadata — F0, SNR gain, harmonics, elephant ID, sex, age, clan, call type

### 4. Knowledge Base (`/knowledge`)
- Source: `results/knowledge_base.json`
- Searchable card grid — one card per call with context tags
- Association links rendered as interactive force-directed graph
- Filter by: elephant, clan, family group, relationship

### 5. Clusters (`/clusters`)
- Cluster summary cards from `results/cluster_summaries.json`
- UMAP scatter or cluster bar chart
- AI hypotheses panel from `results/ai_hypotheses.txt`
- Tribe similarity table from `results/tribe_edges.csv`

### 6. About (`/about`)
- Team, hackathon context, tech stack diagram
- Link to repo

## File Structure

```
frontend/
├── src/app/
│   ├── layout.tsx          # nav + warm theme wrapper
│   ├── page.tsx            # landing hero
│   ├── pipeline/page.tsx
│   ├── explorer/page.tsx
│   ├── knowledge/page.tsx
│   ├── clusters/page.tsx
│   └── about/page.tsx
├── src/components/
│   ├── Navbar.tsx
│   ├── WaveformAnimation.tsx
│   ├── PipelineStage.tsx
│   ├── CallCard.tsx
│   ├── AudioPlayer.tsx
│   ├── AssociationGraph.tsx
│   └── ClusterChart.tsx
├── public/data/            # symlink → ../rumbleos/results/
├── tailwind.config.ts      # warm palette tokens
└── package.json
```

## Data Strategy
- Symlink: `frontend/public/data/` → `rumbleos/results/`
- Next.js serves static files from `public/`
- CSV parsed client-side with papaparse
- JSON loaded via fetch from `/data/`
- Images served as `/data/{call_id}_comparison.png`
- Audio served as `/data/{call_id}_clean.wav`

## Implementation Order
1. Scaffold Next.js + Tailwind, configure palette
2. Layout + Navbar (shared across pages)
3. Landing hero page
4. Explorer page (most demo value)
5. Knowledge base page
6. Pipeline visualization
7. Clusters page
8. About page
9. Symlink data, test all pages

## Key Data Files
- `results/batch_results.csv` or `results/batch_results_clustered.csv` — main call data
- `results/knowledge_base.json` — context KB
- `results/cluster_summaries.json` — cluster stats
- `results/ai_hypotheses.txt` — Claude-generated hypotheses
- `results/tribe_edges.csv` — similarity graph
- `results/{call_id}_comparison.png` — spectrograms
- `results/{call_id}_clean.wav` — cleaned audio
