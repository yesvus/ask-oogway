"""Reads the user's provider preference."""

import tomllib
from pathlib import Path

from .errors import AskOogwayError

DEFAULT_PROVIDER = "claude"
CONFIG_PATH = Path.home() / ".config" / "ask-oogway" / "config.toml"


def get_provider() -> str:
    if not CONFIG_PATH.exists():
        return DEFAULT_PROVIDER

    try:
        with CONFIG_PATH.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise AskOogwayError(f"invalid config.toml at {CONFIG_PATH}: {exc}") from exc

    return data.get("provider", DEFAULT_PROVIDER)
