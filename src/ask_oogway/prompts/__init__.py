"""Oogway character prompt, loaded verbatim as an append-only addition."""

from importlib import resources


def load() -> str:
    return resources.files("ask_oogway.prompts").joinpath("oogway.md").read_text()


SYSTEM_PROMPT = load()
