"""Command-line entrypoint for ask-oogway."""

import argparse
import os
import secrets
import sys
from datetime import datetime
from importlib.metadata import version

from . import history
from . import jobs
from . import wizard
from .errors import AskOogwayError
from .runner import ask


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        print(f"{self.prog}: {message}", file=sys.stderr)
        print(f"Try '{self.prog} --help' for more information.", file=sys.stderr)
        sys.exit(2)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="ask-oogway",
        description="are you unsure? ask-oogway",
        epilog=(
            'Examples:\n'
            '  ask-oogway init\n'
            '  ask-oogway -m "should I use a queue or a cron job here?"\n'
            '  echo "long context" | ask-oogway\n'
            '  ask-oogway -m "..." --quiet --timeout 300\n'
            "  ask-oogway history"
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
        "-o",
        "--output",
        metavar="PATH",
        help=(
            "also tee the answer to PATH; if PATH is a directory, write a "
            "timestamped file in it"
        ),
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="suppress stderr status output (heartbeats, wrote notices)",
    )
    parser.add_argument(
        "--timeout",
        metavar="SECONDS",
        type=int,
        default=None,
        help="cap a call at SECONDS total (0 disables the absolute limit)",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"ask-oogway {version('ask-oogway')}",
        help="show the version",
    )
    return parser


def _output_path(path: str) -> str:
    if os.path.isdir(path):
        return os.path.join(
            path,
            f"ask-oogway-{datetime.now().strftime('%Y%m%d-%H%M%S')}-"
            f"{secrets.token_hex(2)}.txt",
        )
    return path


def _write_output(path: str, answer: str, quiet: bool = False) -> None:
    final = _output_path(path)
    try:
        with open(final, "w") as f:
            f.write(answer + "\n")
    except OSError as exc:
        raise AskOogwayError(f"cannot write output file {final}: {exc}") from exc
    if not quiet:
        print(f"ask-oogway: wrote {final}", file=sys.stderr)


def main() -> None:
    parser = build_parser()

    if sys.argv[1:2] == ["help"]:
        parser.print_help()
        return

    if sys.argv[1:2] == ["init"]:
        wizard.run()
        return

    if sys.argv[1:2] == ["history"]:
        code = history.main(sys.argv[2:])
        if code:
            sys.exit(code)
        return

    if sys.argv[1:2] == ["run"]:
        sys.exit(jobs.run_main(sys.argv[2:]))

    if sys.argv[1:2] == ["ps"]:
        code = jobs.ps_main(sys.argv[2:])
        if code:
            sys.exit(code)
        return

    if sys.argv[1:2] == ["outputs"]:
        code = jobs.outputs_main(sys.argv[2:])
        if code:
            sys.exit(code)
        return

    args = parser.parse_args()

    if args.timeout is not None and args.timeout < 0:
        parser.error("--timeout must be >= 0 seconds")

    prompt = (args.message or "").strip()
    if not prompt and not sys.stdin.isatty():
        prompt = sys.stdin.read().strip()

    if not prompt:
        parser.error("missing message")

    try:
        answer = ask(prompt, timeout=args.timeout, quiet=args.quiet)
        if args.output:
            _write_output(args.output, answer, quiet=args.quiet)
    except AskOogwayError as exc:
        print(f"ask-oogway: {exc}", file=sys.stderr)
        sys.exit(1)

    print(answer)


if __name__ == "__main__":
    main()
