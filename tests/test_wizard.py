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

    def test_eof_uses_default_without_crashing(self):
        with mock.patch("builtins.input", side_effect=EOFError):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(
                    wizard._prompt_choice("which?", ["claude", "openai"], default="claude"),
                    "claude",
                )

    def test_eof_without_default_reports_actionable_error(self):
        from ask_oogway.errors import AskOogwayError
        with mock.patch("builtins.input", side_effect=EOFError):
            with self.assertRaisesRegex(AskOogwayError, "non-interactive init"):
                wizard._prompt_choice("which?", ["claude", "openai"])

    def test_confirm_eof_denies_side_effect(self):
        with mock.patch("builtins.input", side_effect=EOFError):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertFalse(wizard._confirm("install the skill?", default=True))

    def test_empty_without_default_reprompts(self):
        with mock.patch("builtins.input", side_effect=["", "claude"]):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(
                    wizard._prompt_choice("which?", ["chatgpt", "claude"]), "claude"
                )


class TestRunWritesDetectedDefault(unittest.TestCase):
    def test_eof_initializes_without_installing_skills(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "config.toml"
            skill = Path(td) / "skill" / "SKILL.md"
            opencode_skill = Path(td) / "opencode" / "SKILL.md"
            with (
                mock.patch.object(wizard, "CONFIG_PATH", cfg),
                mock.patch.object(wizard, "SKILL_DEST", skill),
                mock.patch.object(wizard, "OPENCODE_SKILL_DEST", opencode_skill),
                mock.patch.object(wizard, "detect_provider", return_value="claude"),
                mock.patch("builtins.input", side_effect=EOFError),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                wizard.run()
            self.assertEqual(cfg.read_text(), 'provider = "claude"\n')
            self.assertFalse(skill.exists())
            self.assertFalse(opencode_skill.exists())

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
