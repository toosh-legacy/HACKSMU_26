import multiprocessing as mp
import serial
import json

class SenseCapAgent(mp.Process):
    """
    Singleton agent: receives detection events and sends to SenseCAP Indicator
    via USB serial (CH340 chip, /dev/ttyUSB0, 115200 baud).

    Runs throughout the entire processing session. Never blocks the pipeline.
    """
    def __init__(self, in_queue, port='/dev/ttyUSB0', baud=115200):
        super().__init__(daemon=True)
        self.in_queue = in_queue
        self.port     = port
        self.baud     = baud
        self.count    = 0

    def run(self):
        try:
            ser = serial.Serial(self.port, self.baud, timeout=1)
            print(f"[SenseCAP] connected on {self.port}")
        except Exception as e:
            print(f"[SenseCAP] WARNING: serial unavailable ({e}) — display disabled")
            ser = None

        while True:
            msg = self.in_queue.get()
            if msg is None:
                print(f"[SenseCAP] shutdown — total detections: {self.count}")
                break
            if msg.get('detected'):
                self.count += 1
            payload = {**msg, "count": self.count}
            line    = json.dumps(payload) + "\n"
            if ser:
                try:
                    ser.write(line.encode('utf-8'))
                except Exception as e:
                    print(f"[SenseCAP] write error: {e}")
            print(f"[SenseCAP] detected={msg.get('detected')} "
                  f"f0={msg.get('f0_hz')}Hz noise={msg.get('noise_type')} "
                  f"count={self.count}")
