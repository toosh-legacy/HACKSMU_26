"""
RumbleOS Edge Listener
Runs on Raspberry Pi with a microphone to capture live infrasound.
Streams audio chunks to the main pipeline via a shared queue or MQTT.

Usage:
    python edge/listen.py
"""

import numpy as np
import sounddevice as sd
import json
import time

TARGET_SR    = 4000
CHUNK_SEC    = 10       # seconds per live capture chunk
DEVICE_INDEX = None     # None = system default; set to int for specific device

def list_devices():
    print(sd.query_devices())

def capture_chunk(duration=CHUNK_SEC, sr=TARGET_SR, device=DEVICE_INDEX):
    """Capture a single audio chunk from the microphone."""
    audio = sd.rec(int(duration * sr), samplerate=sr, channels=1,
                   dtype='float32', device=device)
    sd.wait()
    return audio.flatten()

def run_live(output_queue=None, mqtt_client=None, topic="rumbleos/audio"):
    """
    Continuously capture audio and either:
    - Put chunks into output_queue (for local pipeline)
    - Publish via MQTT (for remote processing)
    """
    print(f"[EdgeListener] starting live capture at {TARGET_SR} Hz")
    chunk_id = 0
    while True:
        try:
            audio = capture_chunk()
            chunk_id += 1
            payload = {
                "chunk_id":  chunk_id,
                "timestamp": time.time(),
                "sr":        TARGET_SR,
                "samples":   len(audio),
            }
            print(f"[EdgeListener] chunk {chunk_id} | {len(audio)} samples | "
                  f"peak={audio.max():.4f}")

            if output_queue is not None:
                output_queue.put({"audio": audio, **payload})

            if mqtt_client is not None:
                import paho.mqtt.client as mqtt
                mqtt_client.publish(topic, json.dumps(payload))

        except KeyboardInterrupt:
            print("[EdgeListener] stopped by user")
            break
        except Exception as e:
            print(f"[EdgeListener] error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    list_devices()
    run_live()
