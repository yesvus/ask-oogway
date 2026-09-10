"""Command-line entrypoint for ask-oogway."""

import argparse
import sys
from importlib.metadata import version

from .errors import AskOogwayError
from .runner import ask


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        print(f"Try '{self.prog} --help' for more information.", file=sys.stderr)
        sys.exit(2)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="ask-oogway",
        description="are you unsure? ask-oogway",
        epilog=(
            'Examples:\n'
            '  ask-oogway -m "should I use a queue or a cron job here?"\n'
            '  echo "long context" | ask-oogway'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )
    parser.add_argument(
        "-h",
        "--help",
        action="help",
        help="show this help message",
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
        help="show the version",
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
