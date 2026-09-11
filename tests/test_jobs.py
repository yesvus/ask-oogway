"""Tests for background runs (jobs)."""

import contextlib
import io
import json
import os
import signal
import stat
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from ask_oogway import history
from ask_oogway import jobs
from ask_oogway.errors import AskOogwayError
from ask_oogway.providers import claude


_FAKE_SCRIPT = """\
#!/bin/sh
case "$FAKE_MODE" in
  trickle)
    for i in 1 2 3; do
      echo "line$i"
      sleep 0.2
    done
    ;;
  silent)
    sleep 10
    ;;
  *)
    printf '  hello world  \\n'
    ;;
esac
"""


class _TtyStdin:
    def isatty(self):
        return True

    def read(self):
        return ""


class TestJobs(unittest.TestCase):
    def setUp(self):
        self.children = []
        self.addCleanup(self._kill_children)
        self._orig_stall = claude._STALL_TIMEOUT
        self._orig_absolute = claude._ABSOLUTE_TIMEOUT
        self._orig_after = claude._HEARTBEAT_AFTER
        self._orig_every = claude._HEARTBEAT_EVERY
        claude._STALL_TIMEOUT = 10
        claude._ABSOLUTE_TIMEOUT = 30
        claude._HEARTBEAT_AFTER = 1000
        self.addCleanup(self._restore_constants)

    def _restore_constants(self):
        claude._STALL_TIMEOUT = self._orig_stall
        claude._ABSOLUTE_TIMEOUT = self._orig_absolute
        claude._HEARTBEAT_AFTER = self._orig_after
        claude._HEARTBEAT_EVERY = self._orig_every

    def _kill_children(self):
        for pid in self.children:
            try:
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                pass
        for pid in self.children:
            try:
                os.waitpid(pid, 0)
            except (ChildProcessError, OSError):
                pass
        self.children = []

    def _track(self, pid):
        self.children.append(pid)
        return pid

    def _write_fake(self, tmpdir):
        path = os.path.join(tmpdir, "claude")
        with open(path, "w") as f:
            f.write(_FAKE_SCRIPT)
        os.chmod(
            path,
            stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH,
        )
        return path

    def _env(self, tmpdir, mode):
        return {"PATH": tmpdir + os.pathsep + os.environ["PATH"], "FAKE_MODE": mode}

    def test_begin_finish_unit(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            with mock.patch.object(history, "HISTORY_DIR", tmp):
                rec = history.begin("hello", "claude")
                self.assertIn("id", rec)
                self.assertIn("dir", rec)
                d = Path(rec["dir"])
                self.assertTrue((d / "input.txt").is_file())
                self.assertEqual((d / "input.txt").read_text(), "hello")
                meta = json.loads((d / "meta.json").read_text())
                self.assertEqual(meta["id"], rec["id"])
                self.assertEqual(meta["status"], "running")
                self.assertIsNone(meta["duration_s"])
                self.assertEqual(meta["provider"], "claude")
                self.assertIsNone(meta["error"])
                self.assertIsNone(meta["pid"])
                self.assertTrue(meta["timestamp"])
                start_ts = meta["timestamp"]
                time.sleep(0.05)
                ok = history.finish(rec["id"], duration=1.234, answer="world", pid=999)
                self.assertTrue(ok)
                meta2 = json.loads((d / "meta.json").read_text())
                self.assertEqual(meta2["timestamp"], start_ts)
                self.assertEqual(meta2["status"], "ok")
                self.assertEqual(meta2["duration_s"], 1.2)
                self.assertEqual(meta2["pid"], 999)
                self.assertEqual((d / "output.txt").read_text(), "world")
                self.assertFalse(history.finish("no-such-id", duration=1.0))

    def test_prune_skips_running(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            with mock.patch.object(history, "HISTORY_DIR", tmp):
                running = history.begin("live prompt", "claude")
                done_ids = []
                for i in range(3):
                    rid = history.record(f"p{i}", provider="s", duration=0.1, answer="x")
                    done_ids.append(rid)
                base = time.time() - 100
                try:
                    os.utime(running["dir"], (base, base))
                except OSError:
                    pass
                history.prune(keep=2)
                self.assertTrue(Path(running["dir"]).exists())
                meta = json.loads(
                    (Path(running["dir"]) / "meta.json").read_text()
                )
                self.assertEqual(meta["status"], "running")

    def test_run_detached_fast_silent(self):
        with tempfile.TemporaryDirectory() as bintd:
            self._write_fake(bintd)
            with tempfile.TemporaryDirectory() as htd:
                tmp = Path(htd)
                with mock.patch.object(history, "HISTORY_DIR", tmp):
                    with mock.patch.dict(os.environ, self._env(bintd, "silent")):
                        with mock.patch(
                            "ask_oogway.runner.get_provider", return_value="claude"
                        ):
                            buf = io.StringIO()
                            start = time.monotonic()
                            with contextlib.redirect_stdout(buf):
                                info = jobs.run_detached("hi silent")
                            elapsed = time.monotonic() - start
                            self._track(info["pid"])
                self.assertLess(elapsed, 5)
                out = buf.getvalue()
                self.assertIn(info["id"], out)
                self.assertIn("output.txt", out)
                self.assertIn(info["dir"], out)
                meta = json.loads(
                    (Path(info["dir"]) / "meta.json").read_text()
                )
                self.assertEqual(meta["status"], "running")
                os.kill(info["pid"], 0)

    def test_trickle_completes(self):
        with tempfile.TemporaryDirectory() as bintd:
            self._write_fake(bintd)
            with tempfile.TemporaryDirectory() as htd:
                tmp = Path(htd)
                with mock.patch.object(history, "HISTORY_DIR", tmp):
                    with mock.patch.dict(os.environ, self._env(bintd, "trickle")):
                        with mock.patch(
                            "ask_oogway.runner.get_provider", return_value="claude"
                        ):
                            with contextlib.redirect_stdout(io.StringIO()):
                                info = jobs.run_detached("hi trickle")
                            self._track(info["pid"])
                            deadline = time.monotonic() + 10
                            found = ""
                            while time.monotonic() < deadline:
                                p = Path(info["dir"]) / "output.txt"
                                try:
                                    if p.is_file():
                                        found = p.read_text()
                                        if found.strip():
                                            break
                                except OSError:
                                    pass
                                time.sleep(0.1)
                self.assertTrue(found.strip(), "output.txt never appeared")
                self.assertIn("line1", found)
                meta = json.loads((Path(info["dir"]) / "meta.json").read_text())
                self.assertEqual(meta["status"], "ok")

    def test_sigkilled_shows_stale(self):
        with tempfile.TemporaryDirectory() as bintd:
            self._write_fake(bintd)
            with tempfile.TemporaryDirectory() as htd:
                tmp = Path(htd)
                with mock.patch.object(history, "HISTORY_DIR", tmp):
                    with mock.patch.dict(os.environ, self._env(bintd, "silent")):
                        with mock.patch(
                            "ask_oogway.runner.get_provider", return_value="claude"
                        ):
                            with contextlib.redirect_stdout(io.StringIO()):
                                info = jobs.run_detached("will die")
                            self._track(info["pid"])
                            try:
                                os.kill(info["pid"], signal.SIGKILL)
                            except ProcessLookupError:
                                pass
                            try:
                                os.waitpid(info["pid"], 0)
                            except (ChildProcessError, OSError):
                                pass
                            # keep pid tracked but already reaped; cleanup tolerates it
                            buf = io.StringIO()
                            with contextlib.redirect_stdout(buf):
                                rc = jobs.ps_main([])
                            self.assertEqual(rc, 0)
                            self.assertIn("stale", buf.getvalue())

    def test_unknown_provider_fails_fast_without_record(self):
        with tempfile.TemporaryDirectory() as htd:
            tmp = Path(htd)
            with mock.patch.object(history, "HISTORY_DIR", tmp):
                with mock.patch(
                    "ask_oogway.runner.get_provider", return_value="nope"
                ):
                    with self.assertRaisesRegex(AskOogwayError, "unknown provider"):
                        jobs.run_detached("hi")
                self.assertEqual(os.listdir(tmp), [])

    def test_run_output_dir_writes_timestamped_file(self):
        with tempfile.TemporaryDirectory() as bintd:
            self._write_fake(bintd)
            with tempfile.TemporaryDirectory() as htd:
                with tempfile.TemporaryDirectory() as otd:
                    tmp = Path(htd)
                    with mock.patch.object(history, "HISTORY_DIR", tmp):
                        with mock.patch.dict(os.environ, self._env(bintd, "trickle")):
                            with mock.patch(
                                "ask_oogway.runner.get_provider",
                                return_value="claude",
                            ):
                                with contextlib.redirect_stdout(io.StringIO()):
                                    info = jobs.run_detached("hi outdir", output=otd)
                                self._track(info["pid"])
                                deadline = time.monotonic() + 10
                                found = ""
                                while time.monotonic() < deadline:
                                    try:
                                        names = [
                                            n
                                            for n in os.listdir(otd)
                                            if n.startswith("ask-oogway-")
                                            and n.endswith(".txt")
                                        ]
                                    except OSError:
                                        names = []
                                    if names:
                                        try:
                                            found = Path(otd, names[0]).read_text()
                                        except OSError:
                                            found = ""
                                        if found.strip():
                                            break
                                    time.sleep(0.1)
                    self.assertTrue(found.strip(), "timestamped -o file never appeared")
                    self.assertIn("line1", found)

    def test_outputs_lists_only_completed(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            with mock.patch.object(history, "HISTORY_DIR", tmp):
                rid_ok = history.record("done one", provider="s", duration=0.1, answer="y")
                rec_run = history.begin("still running", "s")
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    rc = jobs.outputs_main([])
                self.assertEqual(rc, 0)
                out = buf.getvalue()
                self.assertIn(rid_ok, out)
                self.assertNotIn(rec_run["id"], out)

    def test_outputs_dir_mode(self):
        with tempfile.TemporaryDirectory() as td:
            p1 = Path(td) / "ask-oogway-aaa.txt"
            p2 = Path(td) / "ask-oogway-bbb.txt"
            other = Path(td) / "notes.txt"
            p1.write_text("old")
            p2.write_text("new")
            other.write_text("skip me")
            base = time.time() - 100
            os.utime(p1, (base, base))
            os.utime(p2, (base + 50, base + 50))
            os.utime(other, (base + 60, base + 60))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = jobs.outputs_main([td])
            self.assertEqual(rc, 0)
            out = buf.getvalue()
            self.assertIn("ask-oogway-aaa.txt", out)
            self.assertIn("ask-oogway-bbb.txt", out)
            self.assertNotIn("notes.txt", out)
            self.assertLess(out.index("ask-oogway-bbb.txt"), out.index("ask-oogway-aaa.txt"))

    def test_bad_args(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            with mock.patch.object(history, "HISTORY_DIR", tmp):
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    rc = jobs.outputs_main(["bogus-flag"])
                    # bogus-flag without dash tries int() -> fails -> 2
                    # but "--bogus" style also fails; test explicit bad flag
                # ["bogus-flag"] is treated as N parse failure -> 2
                self.assertEqual(rc, 2)
                self.assertTrue(err.getvalue())
                err2 = io.StringIO()
                with contextlib.redirect_stderr(err2):
                    rc2 = jobs.outputs_main(["-n", "bogus"])
                self.assertEqual(rc2, 2)
                # run_main with no message on a tty -> parser.error exits 2
                with mock.patch.object(sys, "stdin", _TtyStdin()):
                    with self.assertRaises(SystemExit) as cm:
                        jobs.run_main([])
                    self.assertEqual(cm.exception.code, 2)
                # ps always returns 0 even with extra args
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(jobs.ps_main([]), 0)


if __name__ == "__main__":
    unittest.main()
