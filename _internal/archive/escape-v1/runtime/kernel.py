"""Supervise the local neural worker and validate its replay protocol."""

import json
import shutil
import subprocess
from pathlib import Path
from selectors import EVENT_READ, DefaultSelector

PROTOCOL = "flywire-v783-doodle-2a8a031-escape-v1"
ROOT = Path(__file__).resolve().parents[2]


class Kernel:
    def __init__(self):
        node = shutil.which("node")
        if node is None:
            raise RuntimeError("Install Node.js 22.18 or later, then run again.")
        self.process = subprocess.Popen(
            [node, str(Path(__file__).parent / "neural/runtime.ts")],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self.selector = DefaultSelector()
        self.selector.register(self.process.stdout, EVENT_READ)
        info = self.request({"command": "info"})
        if info["protocol"] != PROTOCOL:
            self.close()
            raise RuntimeError("The neural worker uses an incompatible protocol.")
        self.info = info

    def request(self, message):
        if self.process.poll() is not None:
            raise RuntimeError("The neural worker stopped. Restart the workshop.")
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()
        if not self.selector.select(timeout=30):
            self.close()
            raise RuntimeError("The neural worker exceeded its 30-second deadline.")
        line = self.process.stdout.readline()
        if not line:
            detail = self.process.stderr.read()[-600:]
            raise RuntimeError(f"The neural worker stopped: {detail}")
        response = json.loads(line)
        if "error" in response:
            raise ValueError(response["error"])
        return response["result"]

    def encounter(
        self, fly, seed, threat, lead_ms, recording=None, trace=False, disconnect=False
    ):
        if lead_ms not in range(5, 196, 5):
            raise ValueError(
                "Visual lead time must use the declared five-millisecond steps."
            )
        return self.request(
            {
                "command": "encounter",
                "fly": fly,
                "seed": seed,
                "threat": threat,
                "lead_ms": lead_ms,
                "replay": recording,
                "trace": trace,
                "disconnect": disconnect,
            }
        )

    def close(self):
        if getattr(self, "process", None) is None:
            return
        self.selector.close()
        if self.process.poll() is None:
            self.process.terminate()
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            stream.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
