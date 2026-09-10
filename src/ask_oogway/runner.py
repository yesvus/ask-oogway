"""Subprocess wrapper around the `claude` CLI."""

import subprocess


class AskOogwayError(RuntimeError):
    """Raised when the underlying `claude` CLI call fails."""


def ask(prompt: str, model: str = "opus") -> str:
    """Run one non-interactive `claude` query and return its stdout."""
    try:
        result = subprocess.run(
            ["claude", "-p", "--model", model, prompt],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise AskOogwayError("the `claude` CLI was not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise AskOogwayError(
            f"claude exited with {exc.returncode}: {exc.stderr.strip()}"
        ) from exc

    return result.stdout.strip()
