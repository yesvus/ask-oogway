# ask-oogway

Simple CLI tool for saving tokens by using expensive models only for hard
questions/decisions.

Give your cheap-model agents one command to escalate to a stronger model
when they hit something hard, instead of teaching every agent how to call
that model's CLI directly.

## Usage

```sh
ask-oogway -m "should I use a queue or a cron job here?"
echo "some long context piped from stdin" | ask-oogway
```

`-m`/`--message` is required (unless piping via stdin) — a bare `ask-oogway`
call, or one missing the flag, fails with a usage error instead of silently
firing a request. The question must be passed as a single quoted argument;
unquoted multi-word input is also rejected with a usage error. This is
deliberate: strong models are expensive, and the point of this tool is that
accidental or malformed calls never reach one.

Exits non-zero and prints an error to stderr if the underlying model CLI is
missing or fails.

## Install

Requires [uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/yesvus/ask-oogway.git
cd ask-oogway
uv tool install --editable .
```

Installs `ask-oogway` onto your PATH.

## Tech stack

- Python 3.12+, packaged and installed with [uv](https://docs.astral.sh/uv/)
- No runtime dependencies — stdlib only (`argparse`, `subprocess`)
- Requires the underlying model CLI on PATH (not bundled)

## Layout

- `src/ask_oogway/cli.py` — argument parsing, stdin fallback, entrypoint
- `src/ask_oogway/runner.py` — the subprocess call to the underlying model CLI
