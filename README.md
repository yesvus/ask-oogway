# ask-oogway

Thin CLI wrapper around `claude -p` so cheap-model agents can consult Opus
for hard tasks or important decisions, without knowing Claude CLI syntax.

## Install

```sh
uv tool install --editable .
```

Installs `ask-oogway` onto your PATH via uv.

## Usage

```sh
ask-oogway -m "should I use a queue or a cron job here?"
echo "some long context piped from stdin" | ask-oogway
ask-oogway --model sonnet -m "quick question, don't need Opus for this"
```

`-m`/`--message` is required (unless piping via stdin) — a bare `ask-oogway`
call or one missing the flag fails with a usage error instead of silently
reaching Opus. The question must be a single quoted argument; unquoted
multi-word input is also rejected with a usage error. This is deliberate:
Opus is expensive, and the whole point is that accidental/malformed calls
never make it to the model.

Defaults to `--model opus`, which the `claude` CLI resolves to the latest
Opus model. Exits non-zero and prints an error to stderr if the `claude`
CLI is missing or fails.

## Layout

- `src/ask_oogway/cli.py` — argument parsing, stdin fallback, entrypoint
- `src/ask_oogway/runner.py` — the actual `claude` subprocess call
