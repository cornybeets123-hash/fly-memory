# Platform support

Last checked 2026-11-21 on branch `hive-shared-memory`. Windows was run. Linux and macOS were read from the code and package metadata, but not run.

## Requirements

- Python 3.12 exactly (`requires-python = "==3.12.*"`). Use `uv`, which fetches it. Plain `pip` on a newer system Python fails.
- Node.js 22.18 or later, because the worker runs TypeScript directly. `kernel.find_node()` rejects older versions with a clear message. `.nvmrc` pins 22.18. Many Linux distributions still ship Node 18 or 20.
- A current Chrome or Edge, Safari 16 or later, or Firefox 121 or later. The page uses `:has()`, `dvh` units and `CanvasRenderingContext2D.roundRect`. iPhone Safari has no `requestFullscreen`, so the fullscreen button does nothing there.

## Status

| | Windows | Linux | macOS |
| --- | --- | --- | --- |
| Tests: 47 pytest, 32 JS, 4 dense neural checks, ruff | Pass | Expected (not run) | Expected (not run) |
| `qdrant-edge-py` 0.8.0 wheel | `win_amd64` only. **No Windows on ARM.** | x86_64 and aarch64 (manylinux, musllinux) | Intel and Apple Silicon |
| 200-fly preparation | Pass (73 min, 8 cores) | Not run | Not run |
| Stop preparation and crash detection | Pass | Expected (POSIX process groups) | Expected (POSIX process groups) |
| `run.py --export` | Pass | Expected | Expected |
| Recordings portable between machines | Yes. Fingerprints ignore line endings. | Expected | Expected |

## What was fixed

1. **Text encoding.** Every live text read and write passes `encoding="utf-8"`. Before, `--export` failed on Windows (cp1252) while decoding `app.js`.
2. **Stop preparation.** `_internal/maze/jobs.py` starts the job in its own process group and stops the whole tree. Windows uses `CREATE_NEW_PROCESS_GROUP` and `taskkill /T /F`; POSIX uses `killpg`. Verified live: cancel stopped all 18 job processes, with none left.
3. **Crash detection.** There is a real process probe (`OpenProcess` on Windows, `os.kill(pid, 0)` on POSIX), plus a heartbeat file that counts as stale after 60 s. Verified live: killing the job parent showed `interrupted` within 2 s.
4. **Line endings.** `.gitattributes` stores text as LF. `workshop_evaluate.file_digest()` normalises CRLF before hashing, so a recording made on Windows matches on Linux and macOS.
5. **Node version.** It is checked at startup (see Requirements).
6. **File replace race.** `jobs.replace_file` retries briefly when Windows refuses a replace because a reader has the file open.

## Known limits and observations

- **Windows on ARM:** unsupported until `qdrant-edge-py` publishes a `win_arm64` wheel.
- **A hard crash leaves workers running.** If the preparation parent dies without the cancel path (for example killed from Task Manager), its pool workers keep running until they are stopped by hand. Cancel from the page is clean.
- **Linux pool start method.** Linux uses `fork` on Python 3.12, while Windows and macOS use `spawn`. The heartbeat thread is running when the pool forks, so Python warns, and a deadlock is possible but unlikely. Passing `mp_context=multiprocessing.get_context("spawn")` to the `ProcessPoolExecutor` in `webinar_population.prepare` would make every OS use the verified path. That needs a fresh recording, because it changes the fingerprint.
- **Export line endings.** `--export` embeds assets as they are checked out. A CRLF checkout embeds CRLF inside the base64 SVG. Behaviour and data are identical, apart from float rounding at about 1e-15 between machines.
- **Hive memory.** The 200-fly hive needs about 1.2 GB in Node and up to about 2.3 GB in Python. See [hive parallelism](hive-parallelism.md) for the single-core hive and its memory growth.

## How to verify Linux or macOS

```sh
uv sync --locked
uv run ruff check
uv run pytest
node --test _internal/tests/test_maze_rerun.cjs
uv run python -m _internal.maze.webinar_population --count 8 --output /tmp/hive-check
```

Then copy a Windows-made recording into `_internal/artifacts/webinar-hive/`, start `uv run run.py`, and confirm that `/api/hive/status` is not `stale`. That proves the line-ending fix end to end. Docker works for Linux (`python:3.12` with Node 22.18 or later and `uv`). macOS needs a Mac or a CI runner.
