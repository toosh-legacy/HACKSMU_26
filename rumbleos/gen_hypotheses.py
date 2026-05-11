"""One-shot script: read cluster_summaries.json → call Gemini (or Claude) → write ai_hypotheses.txt."""
import json, os, time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

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

out = Path("results") / "ai_hypotheses.txt"
resp_text = None

# ── 1. Try Gemini ────────────────────────────────────────────────────────────
gemini_key = os.environ.get("GEMINI_API_KEY")
if gemini_key:
    try:
        from google import genai
        from google.genai import errors as genai_errors

        MODELS = [
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-flash-latest",
        ]
        client = genai.Client(api_key=gemini_key)

        for model in MODELS:
            print(f"Trying Gemini {model}...")
            try:
                resp = client.models.generate_content(model=model, contents=prompt)
                resp_text = resp.text
                print(f"  OK Success with {model}")
                break
            except (genai_errors.ClientError, genai_errors.ServerError) as e:
                err_str = str(e)
                if any(x in err_str for x in ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE", "quota")):
                    retry_msg = ""
                    try:
                        delay = int(err_str.split("retryDelay': '")[1].split("s'")[0])
                        retry_msg = f" (retry in {delay}s)"
                    except Exception:
                        pass
                    print(f"  Skipping {model} ({err_str[:60].strip()}){retry_msg}")
                    time.sleep(2)
                    continue
                raise
        if resp_text is None:
            print("All Gemini models exhausted — trying Claude fallback.")
    except ImportError:
        print("google-genai not installed — trying Claude fallback.")
else:
    print("GEMINI_API_KEY not set — trying Claude fallback.")

# ── 2. Try Anthropic Claude ──────────────────────────────────────────────────
if resp_text is None:
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if anthropic_key:
        try:
            import anthropic
            print("Trying Anthropic claude-haiku-4-5...")
            client_a = anthropic.Anthropic(api_key=anthropic_key)
            msg = client_a.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=600,
                messages=[{"role": "user", "content": prompt}],
            )
            resp_text = msg.content[0].text
            print("  OK Success with claude-haiku-4-5")
        except ImportError:
            print("anthropic package not installed — using data-driven fallback.")
        except Exception as e:
            print(f"  Claude error: {e} — using data-driven fallback.")
    else:
        print("ANTHROPIC_API_KEY not set — using data-driven fallback.")

# ── 3. Data-driven fallback (always works) ───────────────────────────────────
if resp_text is None:
    print("Generating data-driven hypotheses from cluster statistics...")

    def behavior(cid, s):
        f0, dur, harm, snr = s["mean_f0_hz"], s["mean_dur_s"], s["mean_harmonics"], s["mean_snr_db"]
        if f0 >= 28:
            age = "juvenile or young adult"
        elif f0 >= 22:
            age = "adult female"
        else:
            age = "large adult or adult male"
        if dur >= 5:
            call_type = "long-duration contact call"
        elif dur >= 3:
            call_type = "mid-range social rumble"
        else:
            call_type = "short alarm or alert call"
        return f"{call_type}, likely {age} ({f0}Hz F0, {dur}s, {harm:.0f} harmonics)"

    lines = ["**Cluster Behaviors** (one line each)"]
    for cid, s in summaries.items():
        lines.append(f"C{cid}: {behavior(cid, s)}")

    lines.append("")
    lines.append("**Likely Same Individual** (by F0 proximity)")

    # Group clusters within 2 Hz of each other
    items = sorted(summaries.items(), key=lambda x: x[1]["mean_f0_hz"])
    groups = []
    used = set()
    for i, (cid, s) in enumerate(items):
        if cid in used:
            continue
        group = [cid]
        for j, (cid2, s2) in enumerate(items):
            if j <= i or cid2 in used:
                continue
            if abs(s["mean_f0_hz"] - s2["mean_f0_hz"]) <= 2.5:
                group.append(cid2)
                used.add(cid2)
        if len(group) > 1:
            f0s = [summaries[c]["mean_f0_hz"] for c in group]
            avg_f0 = sum(f0s) / len(f0s)
            lines.append(f"C{'+C'.join(group)} — all ~{avg_f0:.0f}Hz, likely same individual or age cohort")
        used.add(cid)

    lines.append("")
    lines.append("**Top 3 Hypotheses**")

    # Find longest-duration cluster
    long_c, long_s = max(summaries.items(), key=lambda x: x[1]["mean_dur_s"])
    # Find richest harmonics cluster
    rich_c, rich_s = max(summaries.items(), key=lambda x: x[1]["mean_harmonics"])
    # Find lowest F0 cluster
    low_c, low_s = min(summaries.items(), key=lambda x: x[1]["mean_f0_hz"])

    lines.append(
        f"1. C{long_c} ({long_s['mean_dur_s']}s duration) represents long-range contact calls — "
        f"extended duration suggests the caller is broadcasting over distance to maintain herd cohesion."
    )
    lines.append(
        f"2. C{rich_c} ({rich_s['mean_harmonics']:.0f} harmonics) exhibits the richest harmonic structure, "
        f"consistent with emotionally aroused or highly motivated callers signaling urgency or greeting."
    )
    lines.append(
        f"3. C{low_c} ({low_s['mean_f0_hz']}Hz F0) is the lowest-frequency cluster, likely produced by the "
        f"largest-bodied individuals (adult bulls or matriarchs) — body mass inversely correlates with F0 in elephants."
    )

    resp_text = "\n".join(lines)

out.write_text(resp_text)
print(f"\nSaved to {out}")
print(resp_text[:400])
