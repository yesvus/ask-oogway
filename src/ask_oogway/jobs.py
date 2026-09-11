"""Detached background runs, plus ps/outputs listings."""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from . import history
from . import runner
from .errors import AskOogwayError
from .providers import REGISTRY


def _child_redirect(record_dir: str) -> str:
    console = os.path.join(record_dir, "console.log")
    try:
        os.setsid()
    except OSError:
        pass
    try:
        fd_log = os.open(console, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    except OSError:
        os._exit(1)
    try:
        os.chmod(console, 0o600)
    except OSError:
        pass
    try:
        fd_null = os.open(os.devnull, os.O_RDONLY)
    except OSError:
        fd_null = None
    try:
        if fd_null is not None:
            os.dup2(fd_null, 0)
        os.dup2(fd_log, 1)
        os.dup2(fd_log, 2)
    except OSError:
        pass
    try:
        if fd_log not in (1, 2):
            os.close(fd_log)
    except OSError:
        pass
    try:
        if fd_null is not None and fd_null != 0:
            os.close(fd_null)
    except OSError:
        pass
    try:
        sys.stdin = open(os.devnull, "r")
    except OSError:
        pass
    try:
        sys.stdout = open(console, "a", encoding="utf-8", buffering=1)
    except OSError:
        pass
    try:
        sys.stderr = open(console, "a", encoding="utf-8", buffering=1)
    except OSError:
        pass
    return console


def run_detached(prompt: str, output: str | None = None) -> dict:
    if not hasattr(os, "fork"):
        raise AskOogwayError("background runs need fork (unix)")
    try:
        provider = runner.get_provider()
    except AskOogwayError:
        raise
    if REGISTRY.get(provider) is None:
        raise AskOogwayError(
            f"unknown provider '{provider}' in config "
            f"(known: {', '.join(sorted(REGISTRY))})"
        )
    rec = history.begin(prompt, provider)
    if rec is None:
        raise AskOogwayError("cannot create history record")
    record_id = rec["id"]
    record_dir = rec["dir"]
    output_abs = os.path.abspath(output) if output else None
    try:
        sys.stdout.flush()
    except OSError:
        pass
    try:
        sys.stderr.flush()
    except OSError:
        pass
    pid = os.fork()
    if pid != 0:
        print(f"job {record_id} started (pid {pid})")
        print(f"output: {record_dir}/output.txt")
        print("poll: ask-oogway ps | ask-oogway outputs")
        if output_abs:
            print(f"file: {output_abs}")
        return {"id": record_id, "pid": pid, "dir": record_dir}
    # child: never return
    console = _child_redirect(record_dir)
    try:
        history.set_pid(record_id, os.getpid())
    except Exception:
        pass
    try:
        child_provider = runner.get_provider()
    except AskOogwayError as exc:
        try:
            history.finish(
                record_id, duration=0.0, error=str(exc), pid=os.getpid()
            )
        except Exception:
            pass
        try:
            sys.stdout.flush()
        except Exception:
            pass
        try:
            sys.stderr.flush()
        except Exception:
            pass
        os._exit(1)
    handler = REGISTRY.get(child_provider)
    if handler is None:
        try:
            history.finish(
                record_id,
                duration=0.0,
                error=(
                    f"unknown provider '{child_provider}' in config "
                    f"(known: {', '.join(sorted(REGISTRY))})"
                ),
                pid=os.getpid(),
            )
        except Exception:
            pass
        try:
            sys.stdout.flush()
        except Exception:
            pass
        try:
            sys.stderr.flush()
        except Exception:
            pass
        os._exit(1)
    t0 = time.monotonic()
    try:
        answer = handler(prompt)
    except AskOogwayError as exc:
        try:
            history.finish(
                record_id,
                duration=time.monotonic() - t0,
                error=str(exc),
                pid=os.getpid(),
            )
        except Exception:
            pass
        try:
            sys.stdout.flush()
        except Exception:
            pass
        try:
            sys.stderr.flush()
        except Exception:
            pass
        os._exit(1)
    except BaseException as exc:
        try:
            history.finish(
                record_id,
                duration=time.monotonic() - t0,
                error=str(exc) or repr(exc),
                pid=os.getpid(),
            )
        except Exception:
            pass
        try:
            sys.stdout.flush()
        except Exception:
            pass
        try:
            sys.stderr.flush()
        except Exception:
            pass
        os._exit(1)
    if output_abs:
        from .cli import _output_path

        final = _output_path(output_abs)
        try:
            with open(final, "w", encoding="utf-8") as f:
                f.write(answer + "\n")
        except OSError as exc:
            try:
                with open(console, "a", encoding="utf-8") as lf:
                    lf.write(f"cannot write output file {final}: {exc}\n")
            except OSError:
                pass
    try:
        history.finish(
            record_id,
            duration=time.monotonic() - t0,
            answer=answer,
            pid=os.getpid(),
        )
    except Exception:
        pass
    try:
        sys.stdout.flush()
    except Exception:
        pass
    try:
        sys.stderr.flush()
    except Exception:
        pass
    os._exit(0)


def _pid_alive(pid) -> bool:
    if not isinstance(pid, int):
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _elapsed_s(timestamp: str) -> int:
    try:
        ts = datetime.fromisoformat(timestamp)
    except (ValueError, TypeError):
        return 0
    try:
        now = datetime.now().astimezone()
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=now.tzinfo)
        return max(0, int((now - ts).total_seconds()))
    except (OSError, ValueError, OverflowError):
        return 0


def ps_main(argv) -> int:
    base = history.HISTORY_DIR
    try:
        names = os.listdir(base)
    except OSError:
        print("no running jobs")
        return 0
    running = []
    for name in names:
        d = Path(base) / name
        try:
            if not d.is_dir():
                continue
        except OSError:
            continue
        try:
            meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(meta, dict) or meta.get("status") != "running":
            continue
        try:
            mtime = d.stat().st_mtime
        except OSError:
            mtime = 0.0
        try:
            prompt = (d / "input.txt").read_text(encoding="utf-8")
        except (OSError, ValueError):
            prompt = ""
        running.append(
            {
                "id": meta.get("id", d.name),
                "timestamp": meta.get("timestamp", ""),
                "pid": meta.get("pid"),
                "dir": str(d),
                "preview": history.preview(prompt),
                "mtime": mtime,
            }
        )
    if not running:
        print("no running jobs")
        return 0
    running.sort(key=lambda r: (r["timestamp"], r["id"]), reverse=True)
    alive = [r for r in running if _pid_alive(r["pid"])]
    stale = [r for r in running if not _pid_alive(r["pid"])]
    for r in alive:
        pid = r["pid"]
        print(f"  {pid}  {_elapsed_s(r['timestamp'])}s  {r['timestamp']}  {r['preview']}")
        print(f"      {r['dir']}")
    for r in stale:
        pid = r["pid"] if isinstance(r["pid"], int) else "-"
        print(
            f"  {pid}  stale (process gone)  {r['timestamp']}  {r['preview']}"
        )
        print(f"      {r['dir']}")
    return 0


def outputs_main(argv) -> int:
    if argv and os.path.isdir(argv[0]):
        target = argv[0]
        try:
            names = os.listdir(target)
        except OSError:
            print(f"no outputs in {target}")
            return 0
        files = []
        for name in names:
            if not (name.startswith("ask-oogway-") and name.endswith(".txt")):
                continue
            full = os.path.join(target, name)
            try:
                if not os.path.isfile(full):
                    continue
                mtime = os.path.getmtime(full)
            except OSError:
                continue
            files.append((mtime, name, full))
        files.sort(key=lambda item: (item[0], item[1]), reverse=True)
        if not files:
            print(f"no outputs in {target}")
            return 0
        for mtime, name, full in files:
            try:
                iso = datetime.fromtimestamp(mtime).astimezone().isoformat(
                    timespec="seconds"
                )
            except (OSError, ValueError, OverflowError):
                iso = ""
            print(f"{iso}  {name}")
            print(f"    {full}")
        return 0
    limit = None
    if len(argv) == 0:
        limit = 20
    elif len(argv) == 1 and argv[0] not in ("-n", "--limit"):
        try:
            limit = int(argv[0])
        except ValueError:
            limit = None
    elif len(argv) == 2 and argv[0] in ("-n", "--limit"):
        try:
            limit = int(argv[1])
        except ValueError:
            limit = None
    if limit is None or limit <= 0:
        print("usage: outputs [-n N | --limit N | N | DIR]", file=sys.stderr)
        return 2
    try:
        recs = history.list_recent(10000)
    except OSError:
        recs = []
    done = [r for r in recs if r.get("status") == "ok"][:limit]
    if not done:
        print("no outputs yet")
        return 0
    for r in done:
        print(
            f"{r.get('id', '')}  {r.get('timestamp', '')}  "
            f"{r.get('provider', '')}  {r.get('preview', '')}"
        )
        print(f"    {r.get('dir', '')}/output.txt")
    return 0


def run_main(argv) -> int:
    from .cli import build_parser

    parser = build_parser()
    parsed = parser.parse_args(argv)
    prompt = (getattr(parsed, "message", None) or "").strip()
    if not prompt and not sys.stdin.isatty():
        try:
            prompt = sys.stdin.read().strip()
        except OSError:
            prompt = ""
    if not prompt:
        parser.error("missing message")
    output = getattr(parsed, "output", None)
    try:
        run_detached(prompt, output)
    except AskOogwayError as exc:
        print(f"ask-oogway: {exc}", file=sys.stderr)
        return 1
    return 0
