# ask-oogway

Give your agents a chance to re-think. Meet them with their new mentor,
Master Oogway.

## Install

Requires [uv](https://docs.astral.sh/uv/). The `claude` provider also
needs the `claude` CLI on PATH.

```sh
git clone https://github.com/yesvus/ask-oogway.git
cd ask-oogway
uv tool install --editable .
```

## Install via prompt

Paste this to your agent:

```txt
Install ask-oogway from https://github.com/yesvus/ask-oogway using uv
(editable install), run ask-oogway init accepting defaults, then confirm
ask-oogway -m "say hi" returns an answer.
```

## Usage

```sh
ask-oogway init
ask-oogway -m "should I use a queue or a cron job here?"
echo "some long context" | ask-oogway
ask-oogway -m "..." -o answer.md  # also tee answer to a file (dir -> timestamped file)
```

See `ask-oogway --help` for `--quiet` and `--timeout`.

## Config

`ask-oogway init` writes `~/.config/ask-oogway/config.toml`:

```toml
provider = "claude"  # default. also: openai, chatgpt (not implemented yet)
```

The `openai` provider talks to any OpenAI-compatible `/chat/completions`
endpoint:

| variable | default | meaning |
| --- | --- | --- |
| `ASK_OOGWAY_BASE_URL` | `https://api.openai.com/v1` | endpoint root |
| `ASK_OOGWAY_MODEL` | `claude-opus-4-6-thinking` | model id |
| `ASK_OOGWAY_API_KEY` | falls back to `OPENAI_API_KEY` | bearer token |

```sh
export ASK_OOGWAY_BASE_URL="https://your-gateway.example/v1"
export ASK_OOGWAY_MODEL="claude-opus-4-6-thinking"
export ASK_OOGWAY_API_KEY="..."
```

It also offers to install `SKILL.md` to `~/.claude/skills/ask-oogway/`
and `~/.config/opencode/skills/ask-oogway/`, so agents auto-discover
ask-oogway without being told about it.

## Stack

Python 3.12+, uv, stdlib only. See `pyproject.toml`.
