"""Reads the user's provider preference, detecting it when unconfigured."""

import shutil
import tomllib
from pathlib import Path

from .errors import AskOogwayError
from .providers import REGISTRY

DEFAULT_PROVIDER = "claude"
CONFIG_PATH = Path.home() / ".config" / "ask-oogway" / "config.toml"


def detect_provider() -> str:
    # Walks REGISTRY in order, so its literal order is detection priority.
    # Binary name defaults to the provider name.
    for name in REGISTRY:
        if shutil.which(name):
            return name
    return DEFAULT_PROVIDER


def get_provider() -> str:
    if not CONFIG_PATH.exists():
        return detect_provider()

    try:
        with CONFIG_PATH.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise AskOogwayError(f"invalid config.toml at {CONFIG_PATH}: {exc}") from exc

    provider = data.get("provider")
    if provider is None:
        return detect_provider()
    return provider
