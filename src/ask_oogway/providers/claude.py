"""claude CLI provider."""

import os
import selectors
import subprocess
import sys
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
# First heartbeat after this long with no answer yet, then repeating.
# Stderr only, so stdout stays clean-pipeable. Suppression flag lands in #6.
_HEARTBEAT_AFTER = 5
_HEARTBEAT_EVERY = 30


def _tail(text):
    text = text.strip()
    if len(text) > _TAIL_CHARS:
        return "(truncated)\n" + text[-_TAIL_CHARS:]
    return text


# Substring rules for common provider failure modes, checked in order.
# Each alternative is a tuple of markers that must ALL appear. Heuristic
# on purpose: the raw stderr is always included, so a miss only costs
# the hint, never the evidence. Extend as real samples arrive.
_ERROR_HINTS = [
    (
        "auth failed",
        "run `claude login` and retry",
        [
            ("not authenticated",),
            ("not logged in",),
            ("invalid api key",),
            ("unauthorized",),
            ("authentication failed",),
            (" 401",),
            ("(401",),
            ("login required",),
            ("please log in",),
        ],
    ),
    (
        "rate-limited",
        "wait and retry",
        [
            ("rate limit",),
            ("rate_limit",),
            ("429",),
            ("too many requests",),
            ("overloaded",),
            ("capacity",),
        ],
    ),
    (
        "model unavailable",
        "the configured model may be wrong or retired",
        [
            ("model not found",),
            ("model unavailable",),
            ("unknown model",),
            ("invalid model",),
            ("no such model",),
            ("model", "not found"),
            ("model", "does not exist"),
        ],
    ),
    (
        "network error",
        "check connectivity and retry",
        [
            ("network",),
            ("connection",),
            ("econn",),
            ("enotfound",),
            ("eai_again",),
            ("dns",),
            ("unreachable",),
            ("offline",),
            ("socket hang up",),
            ("fetch failed",),
            ("timed out",),
        ],
    ),
]


def _describe_exit(code, stderr):
    lowered = stderr.lower()
    for label, hint, alternatives in _ERROR_HINTS:
        if any(all(m in lowered for m in alt) for alt in alternatives):
            lines = stderr.strip().splitlines()
            quoted = lines[0].strip()[:300] if lines else ""
            msg = f"claude {label} (exit {code}): {hint}"
            return msg + (f". Provider said: {quoted}" if quoted else "")
    return f"claude exited with {code}: {stderr.strip()}"


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
    next_heartbeat = start + _HEARTBEAT_AFTER
    first_beat = True
    bytes_received = 0
    try:
        while True:
            if proc.poll() is not None and len(finished) == 2:
                break
            now = time.monotonic()
            idle = now - last_activity
            total = now - start
            if idle >= _STALL_TIMEOUT or total >= _ABSOLUTE_TIMEOUT:
                break
            if now >= next_heartbeat:
                if bytes_received >= 1024:
                    detail = f", {bytes_received / 1024:.1f}KB received"
                elif bytes_received:
                    detail = f", {bytes_received}B received"
                else:
                    detail = ", no output yet"
                word = "pondering... " if first_beat else "still pondering... "
                print(
                    f"ask-oogway: {word}({int(total)}s elapsed{detail})",
                    file=sys.stderr,
                    flush=True,
                )
                first_beat = False
                next_heartbeat = now + _HEARTBEAT_EVERY
            quantum = min(
                _STALL_TIMEOUT - idle,
                _ABSOLUTE_TIMEOUT - total,
                next_heartbeat - now,
            )
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
                    bytes_received += len(data)
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
            raise AskOogwayError(_describe_exit(proc.returncode, stderr))
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
