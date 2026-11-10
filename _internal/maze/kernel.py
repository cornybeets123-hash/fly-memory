"""Supervise the local neural worker. Fail clearly when it stops or times out."""

import json
import shutil
import subprocess
from pathlib import Path
from selectors import EVENT_READ, DefaultSelector


class Kernel:
    def __init__(self):
        node = shutil.which("node")
        if node is None:
            raise RuntimeError("Install Node.js 22.18 or later.")
        self.process = subprocess.Popen(
            [node, str(Path(__file__).with_name("neural.ts"))],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self.selector = DefaultSelector()
        self.selector.register(self.process.stdout, EVENT_READ)
        try:
            self.info = self.request({"command": "info"})
        except Exception:
            self.close()
            raise

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

    def step(self, fly, seed, left, right, trace=False):
        return self.request(
            {
                "command": "step",
                "fly": fly,
                "seed": seed,
                "left": left,
                "right": right,
                "ms": 20,
                "trace": trace,
            }
        )

    def drop(self, fly):
        return self.request({"command": "drop", "fly": fly})

    def close(self):
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
