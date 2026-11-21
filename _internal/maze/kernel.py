"""Supervise the local neural worker. Fail clearly when it stops or times out."""

import json
import re
import shutil
import subprocess
from pathlib import Path
from queue import Empty, Queue
from threading import Thread

MINIMUM_NODE = (22, 18)


def node_version_ok(text):
    """True when `node --version` output such as 'v22.18.0' meets the minimum."""
    match = re.match(r"v?(\d+)\.(\d+)", text.strip())
    return match is not None and (int(match[1]), int(match[2])) >= MINIMUM_NODE


def find_node():
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("Install Node.js 22.18 or later.")
    try:
        found = subprocess.run(
            [node, "--version"], capture_output=True, text=True, timeout=10, check=False
        ).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        found = ""
    if not node_version_ok(found):
        raise RuntimeError(
            f"Node.js 22.18 or later is required; found {found or 'an unknown version'}."
        )
    return node


class Kernel:
    def __init__(self):
        node = find_node()
        self.process = subprocess.Popen(
            [node, str(Path(__file__).with_name("neural.ts"))],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        # A reader thread keeps the 30-second deadline portable; Windows cannot select() pipes.
        self.lines = Queue()
        Thread(target=self._read, daemon=True).start()
        try:
            self.info = self.request({"command": "info"})
        except Exception:
            self.close()
            raise

    def _read(self):
        try:
            for line in self.process.stdout:
                self.lines.put(line)
        except (OSError, ValueError):
            pass
        self.lines.put("")

    def request(self, message):
        if self.process.poll() is not None:
            raise RuntimeError("The neural worker stopped. Restart the workshop.")
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()
        try:
            line = self.lines.get(timeout=30)
        except Empty:
            self.close()
            raise RuntimeError(
                "The neural worker exceeded its 30-second deadline."
            ) from None
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
