"""OpenAI-compatible endpoint provider."""

import json
import os
import socket
import urllib.error
import urllib.request

from ..errors import AskOogwayError
from ..prompts import SYSTEM_PROMPT

_DEFAULT_BASE_URL = "https://api.openai.com/v1"
_DEFAULT_MODEL = "claude-opus-4-6-thinking"
_KEY_ENV = ("ASK_OOGWAY_API_KEY", "OPENAI_API_KEY")

_ABSOLUTE_TIMEOUT = 1800
_TAIL_CHARS = 2000


def _base_url() -> str:
    return (os.environ.get("ASK_OOGWAY_BASE_URL") or _DEFAULT_BASE_URL).rstrip("/")


def _model() -> str:
    return os.environ.get("ASK_OOGWAY_MODEL") or _DEFAULT_MODEL


def _api_key() -> str:
    for name in _KEY_ENV:
        value = os.environ.get(name)
        if value:
            return value
    raise AskOogwayError(
        "no API key: set ASK_OOGWAY_API_KEY (or OPENAI_API_KEY)"
    )


def _tail(text: str) -> str:
    text = text.strip()
    if len(text) > _TAIL_CHARS:
        return "(truncated)\n" + text[-_TAIL_CHARS:]
    return text


# Substring rules for common endpoint failure modes, checked in order.
# Each alternative is a tuple of markers that must ALL appear. Heuristic
# on purpose: the endpoint's own message is always included, so a miss
# only costs the hint, never the evidence.
_ERROR_HINTS = [
    (
        "auth failed",
        "check the API key and endpoint",
        [
            ("invalid api key",),
            ("unauthorized",),
            ("authentication",),
            ("401",),
        ],
    ),
    (
        "rate-limited",
        "wait and retry",
        [
            ("rate limit",),
            ("rate_limit",),
            ("too many requests",),
            ("429",),
        ],
    ),
    (
        "out of funds",
        "top up the endpoint account or switch ASK_OOGWAY_MODEL",
        [
            ("insufficient", "fund"),
            ("insufficient_quota",),
            ("quota",),
            ("billing",),
        ],
    ),
    (
        "rejected",
        "the endpoint denied this account or model",
        [
            ("permission_error",),
            ("not allowed",),
            ("forbidden",),
            ("403",),
        ],
    ),
    (
        "model unavailable",
        "set ASK_OOGWAY_MODEL to a model the endpoint serves",
        [
            ("model not found",),
            ("model", "not found"),
            ("model", "does not exist"),
            ("unknown model",),
            ("invalid model",),
            ("not supported",),
        ],
    ),
    (
        "network error",
        "check connectivity and retry",
        [
            ("timed out",),
            ("connection",),
            ("unreachable",),
            ("offline",),
            ("getaddrinfo",),
        ],
    ),
]


def _message_from_body(body: str) -> str:
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return ""
    error = parsed.get("error")
    if isinstance(error, dict):
        return error.get("message") or ""
    if isinstance(error, str):
        return error
    return ""


def _describe_http(exc: urllib.error.HTTPError) -> str:
    try:
        body = exc.read().decode("utf-8", "replace")
    except OSError:
        body = ""
    detail = _message_from_body(body) or body.strip()
    lowered = detail.lower()
    for label, hint, alternatives in _ERROR_HINTS:
        if any(all(m in lowered for m in alt) for alt in alternatives):
            msg = f"openai {label} (HTTP {exc.code}): {hint}"
            return msg + (f". Endpoint said: {detail[:300]}" if detail else "")
    msg = f"openai HTTP {exc.code}"
    return msg + (f": {detail[:300]}" if detail else "")


def _extract(raw: str) -> str:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AskOogwayError(
            f"openai returned invalid JSON: {_tail(raw)}"
        ) from exc
    error = parsed.get("error")
    if error:
        detail = error.get("message") if isinstance(error, dict) else error
        raise AskOogwayError(f"openai error: {detail or _tail(raw)}")
    choices = parsed.get("choices") or []
    if not choices:
        raise AskOogwayError(f"openai returned no choices: {_tail(raw)}")
    content = (choices[0].get("message") or {}).get("content")
    if isinstance(content, list):
        content = "".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
    answer = (content or "").strip()
    if not answer:
        raise AskOogwayError("openai returned empty output")
    return answer


def ask(prompt: str, *, timeout: int | None = None, quiet: bool = False) -> str:
    if timeout is not None and timeout < 0:
        raise AskOogwayError("--timeout must be >= 0 seconds")
    ceiling = _ABSOLUTE_TIMEOUT if timeout is None else timeout
    payload = {
        "model": _model(),
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    }
    request = urllib.request.Request(
        f"{_base_url()}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {_api_key()}",
            "User-Agent": "ask-oogway",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(
            request, timeout=None if ceiling == 0 else ceiling
        ) as response:
            raw = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        raise AskOogwayError(_describe_http(exc)) from exc
    except urllib.error.URLError as exc:
        raise AskOogwayError(f"openai network error: {exc.reason}") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise AskOogwayError(f"openai timed out after {ceiling}s") from exc
    return _extract(raw)
