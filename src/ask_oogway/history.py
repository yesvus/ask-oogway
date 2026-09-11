"""Stores tool-side call history for the ask-oogway CLI."""

import json
import os
import secrets
import shutil
import sys
from datetime import datetime
from pathlib import Path

HISTORY_DIR = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")) / "ask-oogway" / "history"


def record(prompt: str, *, provider: str, duration: float, answer: str = "", error: str | None = None) -> str | None:
    now = datetime.now().astimezone()
    record_id = now.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(2)
    record_dir = HISTORY_DIR / record_id
    try:
        record_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    try:
        os.chmod(HISTORY_DIR, 0o700)
    except OSError:
        pass
    meta = {
        "id": record_id,
        "timestamp": now.isoformat(timespec="seconds"),
        "duration_s": round(duration, 1),
        "provider": provider,
        "status": "error" if error is not None else "ok",
        "error": error,
    }
    try:
        (record_dir / "input.txt").write_text(prompt, encoding="utf-8")
        (record_dir / "output.txt").write_text(answer if error is None else "", encoding="utf-8")
        (record_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    except OSError:
        return None
    try:
        prune()
    except OSError:
        pass
    return record_id


def preview(prompt: str) -> str:
    lines = prompt.splitlines()
    first = lines[0].strip() if lines else ""
    if len(first) > 60 or len(lines) > 1:
        return first[:60] + "…"
    return first


def list_recent(limit: int = 20) -> list[dict]:
    try:
        dirs = [d for d in HISTORY_DIR.iterdir() if d.is_dir()]
    except OSError:
        return []
    items = []
    for d in dirs:
        try:
            meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(meta, dict):
            continue
        try:
            mtime = d.stat().st_mtime
        except OSError:
            continue
        try:
            prompt = (d / "input.txt").read_text(encoding="utf-8")
        except (OSError, ValueError):
            prompt = ""
        items.append(
            (
                mtime,
                d.name,
                {
                    "id": meta.get("id", d.name),
                    "timestamp": meta.get("timestamp", ""),
                    "duration_s": meta.get("duration_s", 0.0),
                    "provider": meta.get("provider", ""),
                    "status": meta.get("status", ""),
                    "error": meta.get("error"),
                    "dir": str(d),
                    "preview": preview(prompt),
                },
            )
        )
    items.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [rec for _, _, rec in items[:limit]]


def prune(keep: int = 50) -> None:
    try:
        dirs = [d for d in HISTORY_DIR.iterdir() if d.is_dir() and (d / "meta.json").is_file()]
    except OSError:
        return
    items = []
    for d in dirs:
        try:
            items.append((d.stat().st_mtime, d.name, d))
        except OSError:
            continue
    items.sort(key=lambda item: (item[0], item[1]))
    for _, _, d in items[: max(0, len(items) - keep)]:
        shutil.rmtree(d, ignore_errors=True)


def main(argv: list[str]) -> int:
    limit: int | None = None
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
        print("usage: history [-n N | --limit N | N]", file=sys.stderr)
        return 2
    recs = list_recent(limit)
    if not recs:
        print("no history yet")
        return 0
    for rec in recs:
        try:
            duration = float(rec.get("duration_s", 0.0))
        except (TypeError, ValueError):
            duration = 0.0
        print(
            f"{rec.get('id', '')}  {rec.get('timestamp', '')}  "
            f"{duration:.1f}s  {rec.get('provider', '')}  "
            f"{rec.get('status', '')}  {rec.get('preview', '')}"
        )
        print(f"    {rec.get('dir', '')}/input.txt  {rec.get('dir', '')}/output.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
