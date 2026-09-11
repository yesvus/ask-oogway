"""claude CLI provider."""

import os
import selectors
import subprocess
import time

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

# Silence this long means stuck, not working. Any stdout/stderr byte
# resets the clock, so long productive runs survive.
_STALL_TIMEOUT = 300
# Backstop for pathological trickles. Configurable --timeout lands in #6.
_ABSOLUTE_TIMEOUT = 1800
_TAIL_CHARS = 2000


def _tail(text):
    text = text.strip()
    if len(text) > _TAIL_CHARS:
        return "(truncated)\n" + text[-_TAIL_CHARS:]
    return text


def ask(prompt: str) -> str:
    try:
        proc = subprocess.Popen(
            [*_ARGS, prompt],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise AskOogwayError("the `claude` CLI was not found on PATH") from exc

    # Single-threaded drain over non-blocking pipes. Reader threads were
    # tried first but a stale thread can close an fd number the OS has
    # since reused for the next call, SIGPIPE-ing an innocent child.
    streams = {"stdout": proc.stdout, "stderr": proc.stderr}
    for pipe in streams.values():
        os.set_blocking(pipe.fileno(), False)
    sel = selectors.DefaultSelector()
    for name, pipe in streams.items():
        sel.register(pipe, selectors.EVENT_READ, name)
    out_parts: list[bytes] = []
    err_parts: list[bytes] = []
    finished = set()
    start = time.monotonic()
    last_activity = start
    try:
        while True:
            if proc.poll() is not None and len(finished) == 2:
                break
            now = time.monotonic()
            idle = now - last_activity
            total = now - start
            if idle >= _STALL_TIMEOUT or total >= _ABSOLUTE_TIMEOUT:
                break
            quantum = min(_STALL_TIMEOUT - idle, _ABSOLUTE_TIMEOUT - total)
            if len(finished) == 2:
                # Pipes are EOF but the process still runs: wait for the
                # exit itself instead of selecting on an empty selector.
                try:
                    proc.wait(timeout=quantum)
                except subprocess.TimeoutExpired:
                    pass
                continue
            for key, _mask in sel.select(timeout=quantum):
                try:
                    data = os.read(key.fd, 65536)
                except OSError:
                    data = b""
                if data:
                    last_activity = time.monotonic()
                    (out_parts if key.data == "stdout" else err_parts).append(data)
                elif key.data not in finished:
                    sel.unregister(key.fileobj)
                    finished.add(key.data)

        stdout = b"".join(out_parts).decode("utf-8", "replace")
        stderr = b"".join(err_parts).decode("utf-8", "replace")
        if proc.poll() is None:
            stalled = (time.monotonic() - last_activity) >= _STALL_TIMEOUT
            total = int(time.monotonic() - start)
            proc.kill()
            partial = _tail(stdout + "\n" + stderr)
            if stalled:
                raise AskOogwayError(
                    f"claude stalled with no output for {_STALL_TIMEOUT}s "
                    f"({total}s total) and was killed"
                    + (f". Partial output:\n{partial}" if partial else "")
                )
            raise AskOogwayError(
                f"claude timed out after {total}s (limit {_ABSOLUTE_TIMEOUT}s) "
                "and was killed" + (f". Partial output:\n{partial}" if partial else "")
            )
        if proc.returncode != 0:
            raise AskOogwayError(
                f"claude exited with {proc.returncode}: {stderr.strip()}"
            )
        answer = stdout.strip()
        if not answer:
            detail = stderr.strip()
            raise AskOogwayError(
                "claude returned empty output"
                + (f": {detail}" if detail else "")
            )
        return answer
    finally:
        sel.close()
        for pipe in streams.values():
            try:
                pipe.close()
            except OSError:
                pass
        if proc.poll() is None:
            proc.kill()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
