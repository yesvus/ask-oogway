"""Interactive `ask-oogway init` setup wizard."""

import os
import sys
from importlib import resources
from pathlib import Path

from .config import CONFIG_PATH, detect_provider
from .providers import IMPLEMENTED, REGISTRY

SKILL_DEST = Path.home() / ".claude" / "skills" / "ask-oogway" / "SKILL.md"
_XDG_CONFIG_HOME = os.environ.get("XDG_CONFIG_HOME")
_CONFIG_HOME = (
    Path(_XDG_CONFIG_HOME)
    if _XDG_CONFIG_HOME and Path(_XDG_CONFIG_HOME).is_absolute()
    else Path.home() / ".config"
)
OPENCODE_SKILL_DEST = _CONFIG_HOME / "opencode" / "skills" / "ask-oogway" / "SKILL.md"


def _prompt_choice(
    question: str, choices: list[str], default: str | None = None
) -> str:
    hint = f" (default: {default})" if default else ""
    while True:
        answer = input(f"{question} [{'/'.join(choices)}]{hint} ").strip().lower()
        if not answer and default in choices:
            return default
        if answer in choices:
            return answer
        print(f"please enter one of: {'/'.join(choices)}")


def _confirm(question: str, default: bool = True) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    answer = input(f"{question} {suffix} ").strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes")


def run() -> None:
    print("ask-oogway setup\n")

    providers = sorted(REGISTRY)
    detected = detect_provider()
    print(f"detected provider: {detected}")
    provider = _prompt_choice("which provider?", providers, default=detected)

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(f'provider = "{provider}"\n')
    print(f"wrote {CONFIG_PATH}")

    if _confirm("\ninstall the SKILL.md so agents auto-discover ask-oogway?"):
        skill_text = resources.files("ask_oogway.skill").joinpath("SKILL.md").read_text()
        for dest in (SKILL_DEST, OPENCODE_SKILL_DEST):
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(skill_text)
            print(f"installed {dest}")
    else:
        print("skipped")

    print("\ndone")
    if provider not in IMPLEMENTED:
        print(f"note: the {provider} provider isn't implemented yet", file=sys.stderr)
