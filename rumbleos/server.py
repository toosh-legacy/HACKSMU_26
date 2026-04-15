"""
RumbleOS Upload Server
Lightweight HTTP server (stdlib only) that accepts WAV uploads, saves them
to the recordings directory, appends a row to timestamps.csv, and spawns
main.py.  Runs on port 5050 — Vite proxies /api/* here.

Usage:
    cd rumbleos
    python server.py
"""

import json
import os
import struct
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import base64
import csv

# ── Paths ─────────────────────────────────────────────────────────────────────
AUDIO_DIR = Path(r"C:\Projects\HackSMU\HACKSMU_26\recordings\2026)-20260411T194946Z-3-001\Audio Files (04-10-2026)")
CSV_PATH  = Path(__file__).parent / "data" / "timestamps.csv"
MAIN_PY   = Path(__file__).parent / "main.py"
PORT      = 5050

# ── Pipeline state ─────────────────────────────────────────────────────────────
_state_lock = threading.Lock()
state = {"status": "idle", "logs": [], "progress": 0, "error": None}

def _set_state(**kwargs):
    with _state_lock:
        state.update(kwargs)

def _append_log(line: str):
    with _state_lock:
        state["logs"].append(line)
        if len(state["logs"]) > 600:
            state["logs"] = state["logs"][-600:]

def _update_progress(line: str):
    with _state_lock:
        if "dispatched" in line:
            state["progress"] = max(state["progress"], 10)
        elif "[full]" in line and "done" in line:
            state["progress"] = min(state["progress"] + 8, 80)
        elif "clustering" in line.lower():
            state["progress"] = 90
        elif "COMPLETE" in line:
            state["progress"] = 100


def run_pipeline(only_file: str = None):
    """Spawn main.py as a subprocess and stream its output into state.

    If only_file is given, sets PROCESS_ONLY so main.py skips all other files.
    """
    _set_state(status="running", logs=[], progress=0, error=None)

    def _worker():
        try:
            env = os.environ.copy()
            if only_file:
                env["PROCESS_ONLY"] = only_file
            elif "PROCESS_ONLY" in env:
                del env["PROCESS_ONLY"]

            proc = subprocess.Popen(
                [sys.executable, str(MAIN_PY)],
                cwd=str(MAIN_PY.parent),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
            )
            for line in proc.stdout:
                line = line.rstrip("\n")
                if line:
                    _append_log(line)
                    _update_progress(line)
            proc.wait()
            if proc.returncode == 0:
                _set_state(status="done", progress=100)
            else:
                _set_state(status="error", error=f"main.py exited with code {proc.returncode}")
        except Exception as exc:
            _set_state(status="error", error=str(exc))

    threading.Thread(target=_worker, daemon=True).start()


# ── WAV duration — scan RIFF chunks ──────────────────────────────────────────
def wav_duration(path: Path) -> float:
    """Return duration in seconds by scanning RIFF chunks (handles non-standard headers)."""
    try:
        with open(path, "rb") as f:
            header = f.read(12)
            if len(header) < 12 or header[:4] != b"RIFF" or header[8:12] != b"WAVE":
                return 30.0
            sample_rate = num_channels = bits_per_sample = data_bytes = 0
            for _ in range(64):
                chunk_hdr = f.read(8)
                if len(chunk_hdr) < 8:
                    break
                chunk_id   = chunk_hdr[:4]
                chunk_size = struct.unpack_from("<I", chunk_hdr, 4)[0]
                if chunk_id == b"fmt ":
                    fmt = f.read(min(16, chunk_size))
                    if len(fmt) >= 16:
                        num_channels   = struct.unpack_from("<H", fmt, 2)[0]
                        sample_rate    = struct.unpack_from("<I", fmt, 4)[0]
                        bits_per_sample = struct.unpack_from("<H", fmt, 14)[0]
                    skip = chunk_size - min(16, chunk_size)
                    if skip > 0:
                        f.seek(skip, 1)
                elif chunk_id == b"data":
                    data_bytes = chunk_size
                    break
                else:
                    f.seek(chunk_size + (chunk_size % 2), 1)
        if not (sample_rate and num_channels and bits_per_sample and data_bytes):
            return 30.0
        bytes_per_frame = num_channels * (bits_per_sample // 8)
        return data_bytes / (bytes_per_frame * sample_rate) if bytes_per_frame else 30.0
    except Exception:
        return 30.0


# ── timestamps.csv helper ─────────────────────────────────────────────────────
def ensure_csv_entry(filename: str, duration: float):
    """Append a row for filename if it isn't already in the CSV."""
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = CSV_PATH.read_text(encoding="utf-8") if CSV_PATH.exists() else ""
    for line in existing.splitlines():
        if line.startswith(filename + ","):
            return  # already present
    start = 3.0
    end   = max(start + 1, duration - 1)
    row   = f"{filename},{start:.4f},{end:.4f},rumble,unknown\n"
    with open(CSV_PATH, "a", encoding="utf-8", newline="") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        f.write(row)


# ── HTTP handler ──────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f"[server] {self.command} {self.path}")

    def _send_json(self, code: int, obj: dict):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length) if length else b""

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/") or "/"
        if path in ("/status", "/api/status"):
            with _state_lock:
                snapshot = dict(state)
            return self._send_json(200, snapshot)
        self._send_json(404, {"error": f"not found: {self.path}"})

    def do_POST(self):
        path = self.path.split("?")[0].rstrip("/") or "/"
        # POST /run — re-run without uploading
        if path in ("/run", "/api/run"):
            with _state_lock:
                running = state["status"] == "running"
            if running:
                return self._send_json(409, {"error": "Already running"})
            run_pipeline()
            return self._send_json(200, {"ok": True})

        # POST /upload — body: { filename: str, data: base64 }
        if path in ("/upload", "/api/upload"):
            with _state_lock:
                running = state["status"] == "running"
            if running:
                return self._send_json(409, {"error": "Pipeline already running"})

            try:
                body = json.loads(self._read_body())
            except Exception:
                return self._send_json(400, {"error": "Invalid JSON body"})

            filename = body.get("filename", "")
            data_b64 = body.get("data", "")
            if not filename.lower().endswith(".wav"):
                return self._send_json(400, {"error": "Only .wav files accepted"})

            AUDIO_DIR.mkdir(parents=True, exist_ok=True)
            dest = AUDIO_DIR / Path(filename).name
            try:
                dest.write_bytes(base64.b64decode(data_b64))
            except Exception as exc:
                return self._send_json(500, {"error": f"Failed to save file: {exc}"})

            duration = wav_duration(dest)
            ensure_csv_entry(dest.name, duration)
            run_pipeline(only_file=dest.name)
            return self._send_json(200, {
                "ok": True,
                "filename": dest.name,
                "duration": round(duration),
            })

        self._send_json(404, {"error": f"not found: {self.path}"})


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    server = HTTPServer(("localhost", PORT), Handler)
    print(f"RumbleOS upload server listening on http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
