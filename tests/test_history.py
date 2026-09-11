"""Tests for ask_oogway history store."""

import contextlib
import io
import json
import os
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from ask_oogway import history
from ask_oogway import runner
from ask_oogway.errors import AskOogwayError


def _record_dir(tmp, rid):
    return next(tmp.glob(f"{rid}*"))


class TestHistory(unittest.TestCase):
    def test_record_success(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            with mock.patch.object(history, "HISTORY_DIR", tmp):
                rid = history.record("hello", provider="stub", duration=1.5, answer="world")
            self.assertTrue(rid)
            dirs = list(tmp.iterdir())
            self.assertEqual(len(dirs), 1)
            d = dirs[0]
            self.assertTrue(d.name.startswith(rid))
            self.assertEqual((d / "input.txt").read_text(), "hello")
            self.assertEqual((d / "output.txt").read_text(), "world")
            meta = json.loads((d / "meta.json").read_text())
            self.assertEqual(meta["id"], rid)
            self.assertEqual(meta["status"], "ok")
            self.assertEqual(meta["provider"], "stub")
            self.assertEqual(meta.get("duration_s", meta.get("duration")), 1.5)
            self.assertTrue(meta.get("timestamp"))

    def test_record_error(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            with mock.patch.object(history, "HISTORY_DIR", tmp):
                rid = history.record("hi", provider="stub", duration=0.5, error="boom")
            self.assertTrue(rid)
            d = _record_dir(tmp, rid)
            meta = json.loads((d / "meta.json").read_text())
            self.assertEqual(meta["status"], "error")
            self.assertIn("boom", str(meta.get("error")))
            self.assertEqual((d / "output.txt").read_text(), "")

    def test_record_never_raises(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            blocker = Path(f.name)
        self.addCleanup(lambda: blocker.unlink(missing_ok=True))
        with mock.patch.object(history, "HISTORY_DIR", blocker):
            try:
                rid = history.record("hi", provider="stub", duration=0.1, answer="yo")
            except OSError:
                self.fail("record raised OSError")
            self.assertIsNone(rid)

    def test_preview(self):
        self.assertEqual(history.preview("hi"), "hi")
        self.assertEqual(history.preview("x" * 60), "x" * 60)
        self.assertEqual(history.preview("x" * 61), "x" * 60 + "…")
        self.assertEqual(history.preview("first\nsecond"), "first…")

    def test_list_recent_ordering_and_limit(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            with mock.patch.object(history, "HISTORY_DIR", tmp):
                id1 = history.record("first", provider="s", duration=0.1, answer="1")
                id2 = history.record("second", provider="s", duration=0.1, answer="2")
                id3 = history.record("third", provider="s", duration=0.1, answer="3")
                base = time.time() - 100
                for i, rid in enumerate([id1, id2, id3]):
                    m = base + i * 10
                    os.utime(_record_dir(tmp, rid), (m, m))
                recs = history.list_recent()
                self.assertEqual([r["id"] for r in recs], [id3, id2, id1])
                limited = history.list_recent(limit=2)
                self.assertEqual(len(limited), 2)
                self.assertEqual([r["id"] for r in limited], [id3, id2])

    def test_list_recent_skips_garbage(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            with mock.patch.object(history, "HISTORY_DIR", tmp):
                rid = history.record("hi", provider="s", duration=0.1, answer="yo")
                (tmp / "stray.txt").write_text("junk")
                (tmp / "emptydir").mkdir()
                recs = history.list_recent()
            self.assertEqual(len(recs), 1)
            self.assertEqual(recs[0]["id"], rid)

    def test_prune_keeps_newest_50(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            with mock.patch.object(history, "HISTORY_DIR", tmp):
                base = time.time() - 1000
                for i in range(55):
                    d = tmp / f"rec{i:03d}"
                    d.mkdir(parents=True)
                    (d / "input.txt").write_text(f"p{i}")
                    ts = datetime.fromtimestamp(base + i, tz=timezone.utc).isoformat()
                    (d / "meta.json").write_text(json.dumps({
                        "id": f"rec{i:03d}",
                        "timestamp": ts,
                        "duration_s": 0.1,
                        "provider": "s",
                        "status": "ok",
                        "error": None,
                    }))
                    m = base + i
                    for p in (d, d / "meta.json", d / "input.txt"):
                        os.utime(p, (m, m))
                history.prune()
                remain = list(tmp.iterdir())
            self.assertEqual(len(remain), 50)
            self.assertFalse((tmp / "rec000").exists())
            self.assertTrue((tmp / "rec054").exists())

    def test_runner_records_success(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            with mock.patch.object(history, "HISTORY_DIR", tmp):
                with mock.patch("ask_oogway.runner.get_provider", return_value="stub"):
                    with mock.patch.object(runner, "REGISTRY", {"stub": lambda p, **_: "ok!"}):
                        self.assertEqual(runner.ask("hi"), "ok!")
            dirs = list(tmp.iterdir())
            self.assertEqual(len(dirs), 1)
            self.assertEqual((dirs[0] / "input.txt").read_text(), "hi")

    def test_runner_records_failure(self):
        def boom(p, **_):
            raise AskOogwayError("boom")

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            with mock.patch.object(history, "HISTORY_DIR", tmp):
                with mock.patch("ask_oogway.runner.get_provider", return_value="stub"):
                    with mock.patch.object(runner, "REGISTRY", {"stub": boom}):
                        with self.assertRaises(AskOogwayError):
                            runner.ask("hi")
            dirs = list(tmp.iterdir())
            self.assertEqual(len(dirs), 1)
            meta = json.loads((dirs[0] / "meta.json").read_text())
            self.assertEqual(meta["status"], "error")
            self.assertIn("boom", str(meta.get("error")))

    def test_main_empty(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            with mock.patch.object(history, "HISTORY_DIR", tmp):
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    rc = history.main([])
            self.assertEqual(rc, 0)
            self.assertIn("no history yet", out.getvalue())

    def test_main_lists_record(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            with mock.patch.object(history, "HISTORY_DIR", tmp):
                rid = history.record("hello world", provider="stub", duration=1.0, answer="ok")
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    rc = history.main([])
            self.assertEqual(rc, 0)
            self.assertIn(rid, out.getvalue())
            self.assertIn(history.preview("hello world"), out.getvalue())

    def test_main_bad_arg(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            with mock.patch.object(history, "HISTORY_DIR", tmp):
                out, err = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    rc = history.main(["bogus-flag"])
            self.assertEqual(rc, 2)
            self.assertTrue(err.getvalue())


if __name__ == "__main__":
    unittest.main()
