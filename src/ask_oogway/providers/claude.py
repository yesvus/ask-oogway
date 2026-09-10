"""claude CLI provider."""

import subprocess

from ..errors import AskOogwayError

_MODEL = "opus"


def ask(prompt: str) -> str:
    try:
        result = subprocess.run(
            ["claude", "-p", "--model", _MODEL, prompt],
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
