"""Launch the workshop or check the code you just wrote."""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--solution", action="store_true", help="Use completed code for rehearsal."
    )
    parser.add_argument(
        "--check", choices=("personal", "shared"), help="Check the current task."
    )
    parser.add_argument(
        "--export", action="store_true", help="Build an offline demo and workshop ZIP."
    )
    parser.add_argument(
        "--verify", action="store_true", help="Verify the fixed warning trial live."
    )
    parser.add_argument(
        "--evaluate", action="store_true", help="Run the declared evaluation worlds."
    )
    parser.add_argument(
        "--setup-brain",
        action="store_true",
        help="Download the optional pinned live model.",
    )
    args = parser.parse_args()
    if args.setup_brain:
        from _internal.setup import setup_brain

        setup_brain()
        return
    if args.check:
        from _internal.checks import check

        try:
            print(check(args.check, args.solution))
        except (
            ImportError,
            KeyError,
            IndexError,
            ValueError,
            NotImplementedError,
            AssertionError,
            SyntaxError,
            NameError,
            TypeError,
            AttributeError,
        ) as error:
            print(str(error), file=sys.stderr)
            raise SystemExit(1) from error
        return
    if args.export:
        from _internal.package import export

        export()
        return
    if args.evaluate:
        from _internal.evaluate import evaluate

        evaluate("artifacts/evaluation.json")
        return
    if args.verify:
        from _internal.brain import LiveBrain, RecordedBrain

        result = LiveBrain(RecordedBrain()).response(200, 103)
        print(
            f"Live MN9: {result['readouts_hz']['MN9'][0]} Hz. Recording matched: {result['matches_recording']}."
        )
        if not result["matches_recording"]:
            raise SystemExit(1)
        return
    import uvicorn

    from _internal import server

    server.reference_mode = args.solution
    print("Open http://127.0.0.1:8766")
    print(
        "Completed code"
        if args.solution
        else "Edit memory.py, then pipeline.py. Click Run again after each change."
    )
    uvicorn.run(server.app, host="127.0.0.1", port=8766, log_level="warning")


if __name__ == "__main__":
    main()
