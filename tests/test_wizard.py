"""Tests for the init wizard's detected default."""

import contextlib
import io
import unittest
from pathlib import Path
from unittest import mock

from ask_oogway import wizard


class TestPromptChoice(unittest.TestCase):
    def test_empty_input_returns_default(self):
        with mock.patch("builtins.input", return_value=""):
            self.assertEqual(
                wizard._prompt_choice(
                    "which?", ["chatgpt", "claude"], default="claude"
                ),
                "claude",
            )

    def test_explicit_choice_wins_over_default(self):
        with mock.patch("builtins.input", return_value="chatgpt"):
            self.assertEqual(
                wizard._prompt_choice(
                    "which?", ["chatgpt", "claude"], default="claude"
                ),
                "chatgpt",
            )

    def test_empty_without_default_reprompts(self):
        with mock.patch("builtins.input", side_effect=["", "claude"]):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(
                    wizard._prompt_choice("which?", ["chatgpt", "claude"]), "claude"
                )


class TestRunWritesDetectedDefault(unittest.TestCase):
    def test_empty_choice_writes_detected_provider(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "config.toml"
            with (
                mock.patch.object(wizard, "CONFIG_PATH", cfg),
                mock.patch.object(
                    wizard, "detect_provider", return_value="claude"
                ),
                mock.patch("builtins.input", side_effect=["", "n"]),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                wizard.run()
            self.assertEqual(cfg.read_text(), 'provider = "claude"\n')


if __name__ == "__main__":
    unittest.main()
