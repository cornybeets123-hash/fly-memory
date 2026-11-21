"""Start, probe and stop the background preparation job on Windows, Linux and macOS."""

import os
import signal
import subprocess
import sys
from time import sleep, time

WINDOWS = sys.platform == "win32"
STILL_ACTIVE = 259


def launch_group(command, **options):
    """Start a job in its own process group so the whole tree can be stopped."""
    if WINDOWS:
        options["creationflags"] = (
            options.get("creationflags", 0) | subprocess.CREATE_NEW_PROCESS_GROUP
        )
    else:
        options["start_new_session"] = True
    return subprocess.Popen(command, **options)


def process_alive(pid):
    """True while the process exists. `os.kill(pid, 0)` is not a probe on Windows."""
    if WINDOWS:
        import ctypes

        kernel = ctypes.windll.kernel32
        kernel.OpenProcess.restype = ctypes.c_void_p
        handle = kernel.OpenProcess(
            0x1000, False, int(pid)
        )  # QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            return bool(
                kernel.GetExitCodeProcess(ctypes.c_void_p(handle), ctypes.byref(code))
            ) and (code.value == STILL_ACTIVE)
        finally:
            kernel.CloseHandle(ctypes.c_void_p(handle))
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def terminate_tree(pid):
    """Stop a job and every worker it started. Returns True when a stop was sent."""
    if WINDOWS:
        result = subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(pid)],
            capture_output=True,
            check=False,
        )
        return result.returncode == 0
    try:
        if os.getpgid(pid) != pid:
            return False
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return False
    return True


def wait_gone(pid, seconds=5):
    """Wait briefly for a stopped process to disappear."""
    for _ in range(int(seconds * 20)):
        if not process_alive(pid):
            return True
        sleep(0.05)
    return not process_alive(pid)


def replace_file(source, target, attempts=5):
    """Atomic replace. Windows can refuse briefly while a reader has the target open."""
    for attempt in range(attempts):
        try:
            source.replace(target)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            sleep(0.05 * (attempt + 1))


def start_heartbeat(path, every=5):
    """Touch a file from a daemon thread until the returned event is set."""
    from threading import Event, Thread

    stop = Event()

    def beat():
        while True:
            try:
                path.write_text(str(time()), encoding="utf-8")
            except OSError:
                pass
            if stop.wait(every):
                return

    Thread(target=beat, daemon=True).start()
    return stop


def heartbeat_stale(path, limit=60):
    """True when a heartbeat file exists but has not been touched recently."""
    try:
        return time() - path.stat().st_mtime > limit
    except OSError:
        return False  # No heartbeat file: an older job. Fall back to the PID check.
