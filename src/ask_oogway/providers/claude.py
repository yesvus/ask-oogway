"""claude CLI provider."""

import subprocess

from ..errors import AskOogwayError

_MODEL = "opus"

# ask-oogway only asks. It must never be able to write files, run
# commands, or otherwise change anything, including via MCP tools -
# only read-only tools (file reading, search, web) are allowed.
_READONLY_TOOLS = "Read,Glob,Grep,WebSearch,WebFetch"

_ARGS = [
    "claude",
    "-p",
    "--model",
    _MODEL,
    "--restricted",
    "--strict-mcp-config",
    f"--tools={_READONLY_TOOLS}",
    f"--allowedTools={_READONLY_TOOLS}",
]


def ask(prompt: str) -> str:
    try:
        result = subprocess.run(
            [*_ARGS, prompt],
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

    output = result.stdout.strip()
    if not output:
        raise AskOogwayError("claude returned an empty response")

    return output
