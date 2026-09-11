"""Dispatches a prompt to the configured provider."""

import time

from . import history
from .config import get_provider
from .errors import AskOogwayError
from .providers import REGISTRY


def ask(prompt: str) -> str:
    provider = get_provider()
    handler = REGISTRY.get(provider)
    if handler is None:
        raise AskOogwayError(
            f"unknown provider '{provider}' in config "
            f"(known: {', '.join(sorted(REGISTRY))})"
        )
    start = time.monotonic()
    try:
        answer = handler(prompt)
    except AskOogwayError as exc:
        history.record(
            prompt,
            provider=provider,
            duration=time.monotonic() - start,
            error=str(exc),
        )
        raise
    history.record(
        prompt, provider=provider, duration=time.monotonic() - start, answer=answer
    )
    return answer
