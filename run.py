"""Run the workshop, check a build, or prepare presenter backups."""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--solution", action="store_true", help="Rehearse with completed code."
    )
    parser.add_argument(
        "--check", choices=("personal", "shared"), help="Check the saved code."
    )
    parser.add_argument(
        "--export", action="store_true", help="Build the offline replay and download."
    )
    parser.add_argument(
        "--evaluate",
        action="store_true",
        help="Audit the declared two groups of eight flies.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Check dense versus lazy neural integration.",
    )
    args = parser.parse_args()
    if args.check:
        from _internal.maze.checks import check

        try:
            print(check(args.check, args.solution))
        except Exception as error:
            print(f"{type(error).__name__}: {error}", file=sys.stderr)
            raise SystemExit(1) from error
        return
    if args.verify:
        import subprocess

        subprocess.run(["node", "_internal/brain/validate.ts"], check=True)
        return
    if args.evaluate:
        import json
        from pathlib import Path

        from _internal.maze.cohort_evaluate import evaluate

        result = evaluate([50000, 50008])
        Path("_maintainer/evaluation.json").write_text(json.dumps(result, indent=2))
        raise SystemExit(0 if result["passed"] else 1)
    if args.export:
        from _internal.maze.package import export

        export()
        return
    import uvicorn

    from _internal.maze import server

    server.reference_mode = args.solution
    print("Open http://127.0.0.1:8766")
    print(
        "Completed code"
        if args.solution
        else "Edit memory.py, then pipeline.py. Save and click Run again."
    )
    uvicorn.run(server.app, host="127.0.0.1", port=8766, log_level="warning")


if __name__ == "__main__":
    main()
