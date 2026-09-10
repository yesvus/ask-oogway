"""Subprocess wrapper around the underlying model CLI."""

import subprocess

_MODEL = "opus"


class AskOogwayError(RuntimeError):
    """Raised when the underlying CLI call fails."""


def ask(prompt: str) -> str:
    """Run one non-interactive query and return its stdout."""
    try:
        result = subprocess.run(
            ["claude", "-p", "--model", _MODEL, prompt],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise AskOogwayError("the underlying CLI was not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise AskOogwayError(
            f"underlying CLI exited with {exc.returncode}: {exc.stderr.strip()}"
        ) from exc

    return result.stdout.strip()
