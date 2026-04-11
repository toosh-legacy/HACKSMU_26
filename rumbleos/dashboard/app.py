import streamlit as st
import pandas as pd
import json
from pathlib import Path

st.set_page_config(page_title="RumbleOS", layout="wide")
st.title("RumbleOS — Elephant Infrasound Research Platform")

OUT = Path("results")
csv_path = OUT / "batch_results.csv"
if not csv_path.exists():
    st.info("No results yet. Run: python main.py"); st.stop()

df    = pd.read_csv(csv_path)
valid = df[df['valid'] == True] if 'valid' in df.columns else df.head(0)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Calls Processed",  len(df))
c2.metric("Valid Calls",       len(valid))
if len(valid) and 'snr_improvement_db' in valid.columns:
    c3.metric("Avg SNR Gain", f"{valid['snr_improvement_db'].mean():.1f} dB")
if 'noise_type' in df.columns:
    c4.metric("Noise Categories", df['noise_type'].nunique())
if 'multi_elephant' in df.columns:
    c5.metric("Multi-Elephant Calls", int(df['multi_elephant'].sum()))

st.divider()

col_left, col_right = st.columns([1, 2])
with col_left:
    st.subheader("Select Call")
    options  = df['call_id'].tolist() if 'call_id' in df.columns else []
    selected = st.selectbox("Call ID", options)
    if selected and 'noise_type' in df.columns:
        row = df[df['call_id'] == selected].iloc[0]
        st.metric("Noise Type",    row.get('noise_type', '—'))
        st.metric("F0 (Hz)",       row.get('f0_hz', '—'))
        st.metric("SNR Gain (dB)", row.get('snr_improvement_db', '—'))
        st.metric("Harmonics",     f"{row.get('harmonics_present','?')}/{row.get('harmonics_possible','?')}")
        st.metric("Valid",         str(row.get('valid', '—')))

with col_right:
    st.subheader("Before / After Spectrogram")
    if selected:
        img = OUT / f"{selected}_comparison.png"
        if img.exists():
            st.image(str(img), use_container_width=True)
        else:
            st.info("Image not found — check results/ directory")

st.divider()
clust_file = OUT / "cluster_summaries.json"
if clust_file.exists():
    st.subheader("Communication Pattern Clusters (Stage 7)")
    summaries = json.loads(clust_file.read_text())
    cols = st.columns(min(len(summaries), 7))
    for col, (c, s) in zip(cols, summaries.items()):
        col.metric(f"Cluster {c}", f"{s['count']} calls")
        col.caption(f"F0={s['mean_f0_hz']}Hz\n{s['mean_dur_s']}s\n{s['mean_harmonics']} harmonics")

hyp_file = OUT / "ai_hypotheses.txt"
if hyp_file.exists():
    st.subheader("AI Research Hypotheses (Claude API)")
    with st.expander("View hypotheses", expanded=True):
        st.text(hyp_file.read_text())

tribe_file = OUT / "tribe_edges.csv"
if tribe_file.exists():
    st.subheader("Tribe Similarity Graph")
    edges = pd.read_csv(tribe_file)
    st.metric("Similar Call Pairs", len(edges))
    st.dataframe(edges.head(20), use_container_width=True)

st.divider()
st.subheader("All Results")
if len(df):
    show_cols = [c for c in ['call_id', 'noise_type', 'f0_hz', 'snr_improvement_db',
                              'harmonic_completeness', 'harmonics_present', 'valid',
                              'multi_elephant', 'cluster'] if c in df.columns]
    st.dataframe(df[show_cols], use_container_width=True)
