# ask-oogway

Simple CLI tool for saving tokens by using expensive models only for hard
questions/decisions.

## Usage

```sh
ask-oogway init
ask-oogway -m "should I use a queue or a cron job here?"
echo "some long context" | ask-oogway
ask-oogway -m "..." -o answer.md  # also tee answer to a file (dir -> timestamped file)
```

## Install

Requires [uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/yesvus/ask-oogway.git
cd ask-oogway
uv tool install --editable .
```

## Tests

Stdlib `unittest`, no extra deps:

```sh
uv run python -m unittest discover -s tests -v
```

## Config

`ask-oogway init` writes `~/.config/ask-oogway/config.toml`:

```toml
provider = "claude"  # default. also: chatgpt (not implemented yet)
```

It also offers to install `SKILL.md` to `~/.claude/skills/ask-oogway/`, so
Claude Code agents auto-discover ask-oogway without being told about it.

`ask-oogway init` detects the available provider CLI and offers it as the
default; the choice is written down, and runtime honors the file.
Without config, the default is `claude`.

## History

Every call is recorded tool-side, no agent action needed:

```sh
ask-oogway history       # last 20 calls, newest first
ask-oogway history 5     # last 5
```

Records live under `~/.local/share/ask-oogway/history/` (or
`$XDG_DATA_HOME`), one dir per call with `input.txt`, `output.txt`, and
`meta.json` (time, duration, provider, exit status). Only the last 50 are
kept.

**Warning: the history dir is sensitive, prompts can contain secrets.**
Persistence is CLI-side on purpose, provider agents are read-only.

## Background runs

```sh
ask-oogway run -m "long question"        # detach, print job id + output path
ask-oogway run -m "..." -o answer.md     # also tee answer to a file on completion
echo "ctx" | ask-oogway run              # stdin prompt works like the foreground call
ask-oogway ps                            # running jobs with elapsed time, then stale ones
ask-oogway outputs                       # completed runs (newest first)
ask-oogway outputs /path/to/dir         # list ask-oogway-*.txt files in a dir, newest first
```

- `run` forks via `setsid`, so the job survives shell exit.
- Child stdio goes to `<record>/console.log`, answer to `<record>/output.txt`.
- Poll with `ps` (elapsed from start timestamp) or `outputs`; `console.log` shows progress.
- SIGKILLed workers stay as `running` metadata but show as `stale (process gone)` in `ps`.
- `-o` failures are noted in `console.log` and never fail the job.

## Read-only

ask-oogway only asks. It can read files, search, and use the web, but it
cannot write files, run commands, or use any MCP tool, so a question can
never turn into a change.

## Stack

Python 3.12+, uv, stdlib only. Requires `claude` CLI on PATH.

## Layout

- `src/ask_oogway/cli.py` — argument parsing, entrypoint
- `src/ask_oogway/wizard.py` — the `init` setup wizard
- `src/ask_oogway/runner.py` — dispatches to the configured provider
- `src/ask_oogway/history.py` — tool-side call history store
- `src/ask_oogway/jobs.py` — detached background runs (`run`/`ps`/`outputs`)
- `src/ask_oogway/providers/` — one module per provider
- `src/ask_oogway/skill/SKILL.md` — installed by `init` for agent discovery
