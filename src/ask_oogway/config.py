"""Reads the user's provider preference."""

import shutil
import tomllib
from pathlib import Path

from .errors import AskOogwayError
from .providers import REGISTRY

DEFAULT_PROVIDER = "claude"
CONFIG_PATH = Path.home() / ".config" / "ask-oogway" / "config.toml"


def detect_provider() -> str:
    # Walks REGISTRY in order, so its literal order is detection priority.
    # Binary name defaults to the provider name. Called at init time only:
    # the result is written to config.toml, runtime honors the file.
    for name in REGISTRY:
        if shutil.which(name):
            return name
    return DEFAULT_PROVIDER


def get_provider() -> str:
    if not CONFIG_PATH.exists():
        return DEFAULT_PROVIDER

    try:
        with CONFIG_PATH.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise AskOogwayError(f"invalid config.toml at {CONFIG_PATH}: {exc}") from exc

    return data.get("provider", DEFAULT_PROVIDER)
