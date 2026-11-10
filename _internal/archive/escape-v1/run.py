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
        help="Run declared seeds and causal controls.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Check dense versus lazy neural integration.",
    )
    args = parser.parse_args()
    if args.check:
        from _internal.escape.checks import check

        try:
            print(check(args.check, args.solution))
        except Exception as error:
            print(f"{type(error).__name__}: {error}", file=sys.stderr)
            raise SystemExit(1) from error
        return
    if args.verify:
        import subprocess

        subprocess.run(["node", "_internal/escape/neural/validate.ts"], check=True)
        return
    if args.evaluate:
        from _internal.escape.evaluate import evaluate

        evaluate()
        return
    if args.export:
        from _internal.escape.package import export

        export()
        return
    import uvicorn

    from _internal.escape import server

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
