"""Dispatches a prompt to the configured provider."""

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
    return handler(prompt)
