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
    response = handler(prompt)
    if not response or not response.strip():
        raise AskOogwayError(f"provider '{provider}' returned an empty response")
    return response.strip()
