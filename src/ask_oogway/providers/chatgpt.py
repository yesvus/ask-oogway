"""chatgpt provider. Not implemented yet — tracked as a GitHub issue."""

from ..errors import AskOogwayError


def ask(prompt: str, *, timeout: int | None = None, quiet: bool = False) -> str:
    raise AskOogwayError("chatgpt provider isn't implemented yet")
