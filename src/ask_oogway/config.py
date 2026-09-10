"""Reads the user's provider preference."""

import tomllib
from pathlib import Path

DEFAULT_PROVIDER = "claude"
CONFIG_PATH = Path.home() / ".config" / "ask-oogway" / "config.toml"


def get_provider() -> str:
    if not CONFIG_PATH.exists():
        return DEFAULT_PROVIDER

    with CONFIG_PATH.open("rb") as f:
        data = tomllib.load(f)

    return data.get("provider", DEFAULT_PROVIDER)
