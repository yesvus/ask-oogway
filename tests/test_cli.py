"""Tests for ask_oogway.cli.main."""

import contextlib
import io
import sys
import unittest
from unittest import mock

from ask_oogway import cli
from ask_oogway.errors import AskOogwayError


class _TtyStdin:
    def isatty(self):
        return True

    def read(self):
        return ""


class TestMain(unittest.TestCase):
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

    def test_missing_message_exits_2(self):
        with mock.patch("ask_oogway.cli.ask") as ask_mock:
            code, out, err = self.run_main(["ask-oogway"], _TtyStdin())
        self.assertEqual(code, 2)
        self.assertIn("missing message", err)
        ask_mock.assert_not_called()

    def test_message_flag_dispatches(self):
        with mock.patch("ask_oogway.cli.ask", return_value="yo") as ask_mock:
            code, out, err = self.run_main(
                ["ask-oogway", "-m", "hi"], _TtyStdin()
            )
        self.assertIsNone(code)
        self.assertEqual(out, "yo\n")
        ask_mock.assert_called_once_with("hi")

    def test_piped_stdin_prompt(self):
        with mock.patch("ask_oogway.cli.ask", return_value="ok") as ask_mock:
            code, out, err = self.run_main(
                ["ask-oogway"], io.StringIO("from pipe\n")
            )
        self.assertIsNone(code)
        ask_mock.assert_called_once_with("from pipe")

    def test_provider_error_exits_1(self):
        with mock.patch(
            "ask_oogway.cli.ask", side_effect=AskOogwayError("boom")
        ):
            code, out, err = self.run_main(
                ["ask-oogway", "-m", "hi"], _TtyStdin()
            )
        self.assertEqual(code, 1)
        self.assertIn("ask-oogway: boom", err)
        self.assertEqual(out, "")

    def test_init_delegates_to_wizard(self):
        with mock.patch("ask_oogway.cli.wizard.run") as run_mock:
            with mock.patch("ask_oogway.cli.ask") as ask_mock:
                code, out, err = self.run_main(
                    ["ask-oogway", "init"], _TtyStdin()
                )
        run_mock.assert_called_once_with()
        ask_mock.assert_not_called()
        self.assertIsNone(code)

    def test_success_prints_only_answer(self):
        with mock.patch("ask_oogway.cli.ask", return_value="yo"):
            code, out, err = self.run_main(
                ["ask-oogway", "-m", "hi"], _TtyStdin()
            )
        self.assertIsNone(code)
        self.assertEqual(out, "yo\n")
        self.assertEqual(err, "")


if __name__ == "__main__":
    unittest.main()
