"""Command-line entrypoint for ask-oogway."""

import argparse
import sys
from importlib.metadata import version

from .runner import AskOogwayError, ask


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ask-oogway",
        description="you don't know? ask oogway.",
        epilog=(
            'Examples:\n'
            '  ask-oogway -m "should I use a queue or a cron job here?"\n'
            '  echo "long context" | ask-oogway'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-m",
        "--message",
        help=(
            "The question or task, as ONE quoted argument "
            '(e.g. -m "should I use X or Y?"). Required unless piped via '
            "stdin. Explicit on purpose, so a bare/accidental invocation "
            "never fires."
        ),
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"ask-oogway {version('ask-oogway')}",
    )
    return parser


def main() -> None:
    parser = build_parser()

    if sys.argv[1:2] == ["help"]:
        parser.print_help()
        return

    args = parser.parse_args()

    prompt = (args.message or "").strip()
    if not prompt and not sys.stdin.isatty():
        prompt = sys.stdin.read().strip()

    if not prompt:
        parser.error('no prompt given: use -m/--message "..." or pipe via stdin')

    try:
        answer = ask(prompt)
    except AskOogwayError as exc:
        print(f"ask-oogway: {exc}", file=sys.stderr)
        sys.exit(1)

    print(answer)


if __name__ == "__main__":
    main()
