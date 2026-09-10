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
ask-oogway "should I use a queue or a cron job here?"
echo "some long context piped from stdin" | ask-oogway
ask-oogway --model sonnet "quick question, don't need Opus for this"
```

Defaults to `--model opus`, which the `claude` CLI resolves to the latest
Opus model. Exits non-zero and prints an error to stderr if the `claude`
CLI is missing or fails.

## Layout

- `src/ask_oogway/cli.py` — argument parsing, stdin fallback, entrypoint
- `src/ask_oogway/runner.py` — the actual `claude` subprocess call
