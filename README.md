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

When `ask-oogway init` runs without interactive input (for example from an
agent shell), it selects the detected default and skips optional skill
installation. An EOF will not crash the setup or silently approve extra writes.

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

## Claude provider reliability

The Claude CLI provider uses `--output-format stream-json --verbose
--include-partial-messages` to capture answer text as it arrives, while
preserving clean text-only CLI output. For completed calls, Claude's final
`result` is authoritative; thinking, tools and metadata are excluded.
During a call, partial answer text is persisted to the history `output.txt`
file. If a call stalls, times out or its process exits unexpectedly, captured
text is retained alongside error metadata. This does not guarantee a response
when the upstream model emits no text.

## ACP agent transport (opt-in)

ACP is a **client-to-agent** protocol, not an alternative to a direct model API such as
OpenAI-compatible `/chat/completions`. Install the official Python ACP SDK:

```sh
uv tool install --editable . --with agent-client-protocol==0.12.1
# Install and authenticate OpenCode independently, then:
export ASK_OOGWAY_ACP_COMMAND='opencode acp'
mkdir -p ~/.config/ask-oogway
printf 'provider = "acp"\n' > ~/.config/ask-oogway/config.toml
ask-oogway -m 'Review this architecture, without changing files.'
```

The provider uses a fresh ACP session, selects an advertised `read-only`, `read_only`, `plan`, or `architect`
mode (including modern `configOptions` mode catalogs), denies all ACP permission
requests and client filesystem/terminal requests, and collects streamed answer text.
Existing `claude` and `openai` providers, CLI output, history and background jobs
are unchanged. `ask-oogway` never auto-detects ACP to avoid unintended migration.

**OpenCode hardening:** When the ACP command is `opencode acp`, ask-oogway supplies
a restrictive inline tool policy supporting both OpenCode V1 and V2. It disables
edits, shell commands, subagents, external-directory operations and unapproved
extensions and external web fetch/search tools while permitting local file read/search.
Existing inline model
settings are preserved. `plan` alone is *not* read-only, so the extra policy matters.

**Security limit:** ACP itself is **not an OS sandbox**. An agent's native code,
plugins or startup routines may still execute with the process user's privileges.
OpenCode's tool policy is defense in depth, not a filesystem isolation guarantee.
Use an isolated OS account/container if strict no-write semantics are required.
Unknown ACP agents are rejected by default unless a separately isolated/trusted
agent is explicitly approved with `ASK_OOGWAY_ACP_TRUST_AGENT=1`.

**Authentication:** ACP does not grant ChatGPT/Codex subscription quotas. Your
agent must be authenticated using its supported login method.

This is ACP **client** support. Issue #21 separately tracks exposing ask-oogway
as an MCP **server**.

## Stack

Python 3.12+, uv, stdlib only. See `pyproject.toml`.
