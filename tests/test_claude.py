"""Tests for the claude CLI provider."""

import contextlib
import io
import os
import stat
import tempfile
import time
import unittest
from unittest import mock

from ask_oogway.errors import AskOogwayError
from ask_oogway.providers import claude

_FAKE_SCRIPT = """\
#!/bin/sh
case "$FAKE_MODE" in
  trickle)
    for i in 1 2 3 4 5 6; do
      echo "line$i"
      sleep 0.2
    done
    ;;
  silent)
    sleep 10
    ;;
  fail)
    echo "boom" >&2
    exit 3
    ;;
  auth)
    echo "Error: Not authenticated. Please run /login" >&2
    exit 1
    ;;
  rate-limited)
    echo "Error 429: rate limit exceeded, retry later" >&2
    exit 1
    ;;
  bad-model)
    echo "Error: model 'opus' not found" >&2
    exit 1
    ;;
  offline)
    echo "fetch failed: getaddrinfo ENOTFOUND api.anthropic.com" >&2
    exit 1
    ;;
  empty)
    exit 0
    ;;
  stdin-block)
    read line || true
    echo got
    ;;
  *)
    printf '  hello world  \\n'
    ;;
esac
"""


class TestClaudeAsk(unittest.TestCase):
    def setUp(self):
        self._orig_stall = claude._STALL_TIMEOUT
        self._orig_absolute = claude._ABSOLUTE_TIMEOUT
        self._orig_after = claude._HEARTBEAT_AFTER
        self._orig_every = claude._HEARTBEAT_EVERY
        claude._STALL_TIMEOUT = 2
        claude._ABSOLUTE_TIMEOUT = 10
        claude._HEARTBEAT_AFTER = 1000
        self.addCleanup(self._restore_constants)

    def _restore_constants(self):
        claude._STALL_TIMEOUT = self._orig_stall
        claude._ABSOLUTE_TIMEOUT = self._orig_absolute
        claude._HEARTBEAT_AFTER = self._orig_after
        claude._HEARTBEAT_EVERY = self._orig_every

    def _write_fake(self, tmpdir):
        path = os.path.join(tmpdir, "claude")
        with open(path, "w") as f:
            f.write(_FAKE_SCRIPT)
        os.chmod(
            path,
            stat.S_IRWXU
            | stat.S_IRGRP
            | stat.S_IXGRP
            | stat.S_IROTH
            | stat.S_IXOTH,
        )
        return path

    def _env(self, tmpdir, mode):
        return {
            "PATH": tmpdir + os.pathsep + os.environ["PATH"],
            "FAKE_MODE": mode,
        }

    def test_success_passthrough_strips_stdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_fake(tmp)
            with mock.patch.dict(os.environ, self._env(tmp, "success")):
                self.assertEqual(claude.ask("hi"), "hello world")

    def test_missing_binary(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"PATH": tmp}):
                with self.assertRaises(AskOogwayError) as cm:
                    claude.ask("hi")
        self.assertIn("not found on PATH", str(cm.exception))

    def test_nonzero_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_fake(tmp)
            with mock.patch.dict(os.environ, self._env(tmp, "fail")):
                with self.assertRaises(AskOogwayError) as cm:
                    claude.ask("hi")
        self.assertIn("3", str(cm.exception))
        self.assertIn("boom", str(cm.exception))

    def _classified(self, mode):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_fake(tmp)
            with mock.patch.dict(os.environ, self._env(tmp, mode)):
                with self.assertRaises(AskOogwayError) as cm:
                    claude.ask("hi")
        return str(cm.exception)

    def test_auth_failure_hint(self):
        msg = self._classified("auth")
        self.assertIn("auth failed", msg)
        self.assertIn("claude login", msg)
        self.assertIn("Not authenticated", msg)

    def test_rate_limit_hint(self):
        msg = self._classified("rate-limited")
        self.assertIn("rate-limited", msg)
        self.assertIn("429", msg)

    def test_model_unavailable_hint(self):
        msg = self._classified("bad-model")
        self.assertIn("model unavailable", msg)
        self.assertIn("not found", msg)

    def test_network_error_hint(self):
        msg = self._classified("offline")
        self.assertIn("network error", msg)
        self.assertIn("ENOTFOUND", msg)

    def test_unmatched_stderr_stays_generic(self):
        msg = self._classified("fail")
        self.assertIn("claude exited with 3: boom", msg)

    def test_empty_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_fake(tmp)
            with mock.patch.dict(os.environ, self._env(tmp, "empty")):
                with self.assertRaises(AskOogwayError) as cm:
                    claude.ask("hi")
        self.assertIn("empty output", str(cm.exception))

    def test_stall_watchdog(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_fake(tmp)
            with mock.patch.dict(os.environ, self._env(tmp, "silent")):
                start = time.monotonic()
                with self.assertRaises(AskOogwayError) as cm:
                    claude.ask("hi")
                elapsed = time.monotonic() - start
        self.assertIn("stalled", str(cm.exception))
        self.assertLess(elapsed, 10)

    def test_activity_resets_stall_clock(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_fake(tmp)
            with mock.patch.dict(os.environ, self._env(tmp, "trickle")):
                result = claude.ask("hi")
        self.assertIn("line1", result)
        self.assertIn("line6", result)

    def test_heartbeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_fake(tmp)
            buf = io.StringIO()
            with mock.patch.dict(os.environ, self._env(tmp, "success")):
                with contextlib.redirect_stderr(buf):
                    result = claude.ask("hi")
            self.assertEqual(result, "hello world")
            self.assertEqual(buf.getvalue(), "")
            claude._HEARTBEAT_AFTER = 1
            claude._HEARTBEAT_EVERY = 1
            buf = io.StringIO()
            with mock.patch.dict(os.environ, self._env(tmp, "silent")):
                with contextlib.redirect_stderr(buf):
                    with self.assertRaises(AskOogwayError) as cm:
                        claude.ask("hi")
        self.assertIn("stalled", str(cm.exception))
        self.assertIn("pondering", buf.getvalue())

    def test_stdin_is_devnull(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_fake(tmp)
            with mock.patch.dict(os.environ, self._env(tmp, "stdin-block")):
                start = time.monotonic()
                result = claude.ask("hi")
                elapsed = time.monotonic() - start
        self.assertIn("got", result)
        self.assertLess(elapsed, 10)

    def test_timeout_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_fake(tmp)
            with mock.patch.dict(os.environ, self._env(tmp, "silent")):
                claude._STALL_TIMEOUT = 100
                start = time.monotonic()
                with self.assertRaises(AskOogwayError) as cm:
                    claude.ask("hi", timeout=2)
                elapsed = time.monotonic() - start
        self.assertIn("timed out after 2s (limit 2s)", str(cm.exception))
        self.assertLess(elapsed, 10)

    def test_timeout_zero_disables_absolute_ceiling(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_fake(tmp)
            with mock.patch.dict(os.environ, self._env(tmp, "silent")):
                with self.assertRaises(AskOogwayError) as cm:
                    claude.ask("hi", timeout=0)
        self.assertIn("stalled", str(cm.exception))

    def test_quiet_suppresses_heartbeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_fake(tmp)
            claude._HEARTBEAT_AFTER = 1
            claude._HEARTBEAT_EVERY = 1
            buf = io.StringIO()
            with mock.patch.dict(os.environ, self._env(tmp, "silent")):
                with contextlib.redirect_stderr(buf):
                    with self.assertRaises(AskOogwayError):
                        claude.ask("hi", quiet=True)
            self.assertEqual(buf.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
