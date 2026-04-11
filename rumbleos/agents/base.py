import multiprocessing as mp
import traceback

SENTINEL = None  # poison pill — put this in a queue to stop a worker

class BaseAgent(mp.Process):
    """
    Base class for all RumbleOS agents.
    Each agent is a separate OS process.
    Reads from in_queue, calls self.process(msg), writes result to out_queue.
    Stops when it receives SENTINEL (None).
    """
    def __init__(self, agent_id, in_queue, out_queue,
                 extra_queues=None, name="Agent"):
        super().__init__(daemon=True)
        self.agent_id     = agent_id
        self.in_queue     = in_queue
        self.out_queue    = out_queue
        self.extra_queues = extra_queues or {}
        self.name         = f"{name}-{agent_id}"
        self.processed    = 0
        self.errors       = 0

    def process(self, msg: dict) -> dict:
        """Override in subclass. Receives message dict, returns result dict."""
        raise NotImplementedError

    def run(self):
        print(f"[{self.name}] started (pid={self.pid})")
        while True:
            msg = self.in_queue.get()
            if msg is SENTINEL:
                print(f"[{self.name}] shutdown — processed={self.processed} errors={self.errors}")
                break
            try:
                result = self.process(msg)
                if result is not None:
                    self.out_queue.put(result)
                self.processed += 1
            except Exception as e:
                self.errors += 1
                print(f"[{self.name}] ERROR on call_id={msg.get('call_id','?')}: {e}")
                traceback.print_exc()
                # Forward error so pipeline doesn't stall
                self.out_queue.put({
                    **msg,
                    "error": str(e),
                    "stage_failed": self.name,
                    "valid": False
                })
