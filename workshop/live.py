"""Keep Brian2's global state and signal registration on a dedicated main thread."""

import atexit
from multiprocessing import get_context


def serve_brain(connection):
    """Own a full neural model until the parent closes the pipe."""
    brain = None
    try:
        while True:
            bitter, seed = connection.recv()
            try:
                if brain is None:
                    from workshop.brain import LiveBrain, RecordedBrain

                    brain = LiveBrain(RecordedBrain())
                connection.send((True, brain.response(bitter, seed)))
            except Exception as error:  # noqa: BLE001 - report neural failures across the process boundary
                connection.send((False, f"{type(error).__name__}: {error}"))
    except (EOFError, BrokenPipeError):
        pass
    finally:
        connection.close()


class LiveProxy:
    def __init__(self, *, timeout=180, worker=serve_brain):
        self.timeout = timeout
        self.worker = worker
        self.process = self.connection = None
        atexit.register(self.close)

    def close(self):
        if self.connection is not None:
            self.connection.close()
            self.connection = None
        if self.process is not None:
            if self.process.is_alive():
                self.process.terminate()
            self.process.join(timeout=5)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(timeout=5)
            self.process.close()
            self.process = None

    def response(self, bitter, seed):
        if self.process is None or not self.process.is_alive():
            self.close()
            context = get_context("spawn")
            self.connection, child = context.Pipe()
            self.process = context.Process(
                target=self.worker, args=(child,), daemon=True
            )
            self.process.start()
            child.close()
        try:
            self.connection.send((bitter, seed))
            if not self.connection.poll(self.timeout):
                raise TimeoutError("Live neural calculation timed out.")
            success, result = self.connection.recv()
            if not success:
                raise RuntimeError(result)
            return result
        except (EOFError, OSError, TimeoutError, RuntimeError) as error:
            self.close()
            raise RuntimeError(
                f"Live worker stopped. Retry to start a fresh worker. {error}"
            ) from error
