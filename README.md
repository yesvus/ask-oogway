# ask-oogway

Simple CLI tool for saving tokens by using expensive models only for hard
questions/decisions.

## Usage

```sh
ask-oogway init
ask-oogway -m "should I use a queue or a cron job here?"
echo "some long context" | ask-oogway
```

## Install

Requires [uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/yesvus/ask-oogway.git
cd ask-oogway
uv tool install --editable .
```

## Config

`ask-oogway init` writes `~/.config/ask-oogway/config.toml`:

```toml
provider = "claude"  # default. also: chatgpt (not implemented yet)
```

It also offers to install `SKILL.md` to `~/.claude/skills/ask-oogway/`, so
Claude Code agents auto-discover ask-oogway without being told about it.

## Stack

Python 3.12+, uv, stdlib only. Requires `claude` CLI on PATH.

## Layout

- `src/ask_oogway/cli.py` — argument parsing, entrypoint
- `src/ask_oogway/wizard.py` — the `init` setup wizard
- `src/ask_oogway/runner.py` — dispatches to the configured provider
- `src/ask_oogway/providers/` — one module per provider
- `src/ask_oogway/skill/SKILL.md` — installed by `init` for agent discovery
