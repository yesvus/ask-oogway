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

`ask-oogway init` writes `~/.config/ask-oogway/config.toml` with the
chosen provider. Values: `claude` (default), `openai`, `acp`, or `chatgpt`
(not implemented yet). For example:

```toml
provider = "openai"
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

## ACP agent transport (opt-in)\n\nACP standardizes the **client-to-agent** protocol. It does not replace direct model inference APIs such as OpenAI-compatible `/chat/completions`. To talk to an ACP-capable agent:\n\n```sh\nuv tool install --editable . --with agent-client-protocol\n# Install and authenticate an ACP agent separately (for example, OpenCode).\nexport ASK_OOGWAY_ACP_COMMAND='opencode acp'\nprintf 'provider = "acp"\\n' > ~/.config/ask-oogway/config.toml\nask-oogway -m 'Critique this architecture without changing anything.'\n```\n\nThe command is split into arguments without invoking a shell. This provider runs the maintained Python ACP SDK, creates a fresh session, uses an advertised `read-only`, `plan`, or `architect` mode, refuses agents without one, denies all permission requests, and does not offer client-side write/terminal operations or MCP servers. It preserves the existing CLI, history, and timeout behavior. The SDK is installed separately to keep the base CLI dependency-free.\n\n**Security limitation:** ACP is a transport and permission interface, **not a sandbox**. An agent can have its own built-in tools or a misleading `plan` mode and may bypass client permission requests. Use an OS/container read-only sandbox and trusted agent configuration if filesystem safety is required. ACP also does not grant ChatGPT/Codex subscription access; authenticate the selected agent according to its own rules.\n\nThe existing `claude` adapter and `openai` API provider remain supported for backwards compatibility. `ask-oogway` is an ACP **client** here; this is separate from issue #21, which proposes an MCP **server**.\n\n## Stack

Python 3.12+, uv, stdlib only. See `pyproject.toml`.
