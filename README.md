# ask-oogway

Simple CLI tool for saving tokens by using expensive models only for hard
questions/decisions.

## Usage

```sh
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

## Stack

Python 3.12+, uv, stdlib only. Requires the underlying model CLI on PATH.

## Layout

- `src/ask_oogway/cli.py` — argument parsing, entrypoint
- `src/ask_oogway/runner.py` — the subprocess call
