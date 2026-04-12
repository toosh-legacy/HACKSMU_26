"""One-shot script: read cluster_summaries.json → call Gemini → write ai_hypotheses.txt."""
import json, os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from google import genai

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise SystemExit("GEMINI_API_KEY not set in .env")

summaries = json.loads((Path("results") / "cluster_summaries.json").read_text())

total = sum(v["count"] for v in summaries.values())
prompt = (
    f"You are an elephant bioacoustics expert. I clustered {total} rumble calls into {len(summaries)} groups:\n\n"
    + "\n".join(
        f"C{c}: {v['count']} calls | F0={v['mean_f0_hz']}Hz | dur={v['mean_dur_s']}s | harmonics={v['mean_harmonics']} | SNR={v['mean_snr_db']}dB"
        for c, v in summaries.items()
    )
    + "\n\nRespond in this EXACT format, no extra text:\n\n"
    "**Cluster Behaviors** (one line each)\n"
    "C0: <behavior>\n"
    "C1: <behavior>\n"
    "...\n\n"
    "**Likely Same Individual** (by F0 proximity)\n"
    "<group1 e.g. C0+C6 — both ~19Hz, large adult>\n"
    "<group2 if any>\n\n"
    "**Top 3 Hypotheses**\n"
    "1. <one sentence hypothesis citing acoustic property>\n"
    "2. <one sentence hypothesis citing acoustic property>\n"
    "3. <one sentence hypothesis citing acoustic property>\n\n"
    "Total response under 300 words. Be specific, cite Hz/duration/harmonics."
)

client = genai.Client(api_key=api_key)
print("Calling Gemini...")
resp = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
out = Path("results") / "ai_hypotheses.txt"
out.write_text(resp.text)
print(f"Saved to {out}")
print(resp.text[:300])
