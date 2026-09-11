"""Tests for ask_oogway.cli -o/--output support."""

import contextlib
import glob
import io
import os
import sys
import tempfile
import unittest
from unittest import mock

from ask_oogway import cli


class _TtyStdin:
    def isatty(self):
        return True

    def read(self):
        return ""


class TestOutput(unittest.TestCase):
    def run_main(self, argv, stdin):
        out = io.StringIO()
        err = io.StringIO()
        code = None
        with mock.patch.object(sys, "argv", argv):
            with mock.patch.object(sys, "stdin", stdin):
                with contextlib.redirect_stdout(out):
                    with contextlib.redirect_stderr(err):
                        try:
                            cli.main()
                        except SystemExit as exc:
                            code = exc.code
        return code, out.getvalue(), err.getvalue()

    def test_output_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "answer.md")
            with mock.patch("ask_oogway.cli.ask", return_value="yo"):
                code, out, err = self.run_main(
                    ["ask-oogway", "-m", "hi", "-o", target], _TtyStdin()
                )
            self.assertIsNone(code)
            with open(target) as f:
                self.assertEqual(f.read(), "yo\n")
            self.assertEqual(out, "yo\n")
            self.assertIn("wrote", err)
            self.assertIn(target, err)

    def test_output_dir_timestamped_no_clobber(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("ask_oogway.cli.ask", return_value="yo"):
                code1, out1, err1 = self.run_main(
                    ["ask-oogway", "-m", "hi", "-o", tmp], _TtyStdin()
                )
                code2, out2, err2 = self.run_main(
                    ["ask-oogway", "-m", "hi", "-o", tmp], _TtyStdin()
                )
            self.assertIsNone(code1)
            self.assertIsNone(code2)
            self.assertEqual(out1, "yo\n")
            self.assertEqual(out2, "yo\n")
            files = sorted(glob.glob(os.path.join(tmp, "ask-oogway-*.txt")))
            self.assertEqual(len(files), 2)
            self.assertNotEqual(files[0], files[1])
            for path in files:
                with open(path) as f:
                    self.assertEqual(f.read(), "yo\n")

    def test_output_missing_parent_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "nope", "answer.md")
            with mock.patch("ask_oogway.cli.ask", return_value="yo"):
                code, out, err = self.run_main(
                    ["ask-oogway", "-m", "hi", "-o", target], _TtyStdin()
                )
            self.assertEqual(code, 1)
            self.assertEqual(out, "")
            self.assertIn(target, err)
            self.assertNotIn("Traceback", err)
            self.assertFalse(os.path.exists(target))

    def test_no_output_unchanged(self):
        with mock.patch("ask_oogway.cli.ask", return_value="yo"):
            code, out, err = self.run_main(
                ["ask-oogway", "-m", "hi"], _TtyStdin()
            )
        self.assertIsNone(code)
        self.assertEqual(out, "yo\n")
        self.assertEqual(err, "")

    def test_output_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "answer.md")
            with open(target, "w") as f:
                f.write("stale\n")
            with mock.patch("ask_oogway.cli.ask", return_value="fresh"):
                code, out, err = self.run_main(
                    ["ask-oogway", "-m", "hi", "-o", target], _TtyStdin()
                )
            self.assertIsNone(code)
            with open(target) as f:
                self.assertEqual(f.read(), "fresh\n")
            self.assertEqual(out, "fresh\n")

    def test_quiet_suppresses_wrote_notice(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "answer.md")
            with mock.patch("ask_oogway.cli.ask", return_value="yo"):
                code, out, err = self.run_main(
                    ["ask-oogway", "-m", "hi", "-o", target, "--quiet"],
                    _TtyStdin(),
                )
            self.assertIsNone(code)
            with open(target) as f:
                self.assertEqual(f.read(), "yo\n")
            self.assertEqual(out, "yo\n")
            self.assertEqual(err, "")


if __name__ == "__main__":
    unittest.main()
