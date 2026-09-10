"""Interactive `ask-oogway init` setup wizard."""

import sys
from importlib import resources
from pathlib import Path

from .config import CONFIG_PATH
from .providers import REGISTRY

SKILL_DEST = Path.home() / ".claude" / "skills" / "ask-oogway" / "SKILL.md"


def _prompt_choice(question: str, choices: list[str]) -> str:
    choice_str = "/".join(choices)
    while True:
        answer = input(f"{question} [{choice_str}] ").strip().lower()
        if answer in choices:
            return answer
        print(f"please enter one of: {choice_str}")


def _confirm(question: str, default: bool = True) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    answer = input(f"{question} {suffix} ").strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes")


def run() -> None:
    print("ask-oogway setup\n")

    providers = sorted(REGISTRY)
    provider = _prompt_choice("which provider?", providers)

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(f'provider = "{provider}"\n')
    print(f"wrote {CONFIG_PATH}")

    if _confirm("\ninstall the SKILL.md so agents auto-discover ask-oogway?"):
        skill_text = resources.files("ask_oogway.skill").joinpath("SKILL.md").read_text()
        SKILL_DEST.parent.mkdir(parents=True, exist_ok=True)
        SKILL_DEST.write_text(skill_text)
        print(f"installed {SKILL_DEST}")
    else:
        print("skipped")

    print("\ndone")
    if provider not in ("claude",):
        print(f"note: the {provider} provider isn't implemented yet", file=sys.stderr)
