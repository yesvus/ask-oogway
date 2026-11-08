"""Dispatches a prompt to the configured provider."""

import time

from . import history
from .config import get_provider
from .errors import AskOogwayError
from .providers import REGISTRY


def ask(prompt: str, *, timeout: int | None = None, quiet: bool = False) -> str:
    provider = get_provider()
    handler = REGISTRY.get(provider)
    if handler is None:
        raise AskOogwayError(
            f"unknown provider '{provider}' in config "
            f"(known: {', '.join(sorted(REGISTRY))})"
        )
    start = time.monotonic()
    live = history.begin(prompt, provider) if provider == "claude" else None
    try:
        options = {"timeout": timeout, "quiet": quiet}
        if provider == "claude":
            options["on_chunk"] = (
                (lambda text: history.append_output(live["id"], text))
                if live else None
            )
        answer = handler(prompt, **options)
    except AskOogwayError as exc:
        if live:
            history.finish(
                live["id"],
                duration=time.monotonic() - start,
                answer=getattr(exc, "partial_answer", ""),
                error=str(exc),
            )
        else:
            history.record(
                prompt, provider=provider,
                duration=time.monotonic() - start, error=str(exc),
            )
        raise
    if live:
        history.finish(live["id"], duration=time.monotonic() - start, answer=answer)
    else:
        history.record(
            prompt, provider=provider, duration=time.monotonic() - start,
            answer=answer,
        )
    return answer
