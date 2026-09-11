import subprocess
import unittest
from unittest.mock import MagicMock, patch

from ask_oogway.errors import AskOogwayError
from ask_oogway.providers.claude import ask


class TestClaudeProvider(unittest.TestCase):
    @patch("ask_oogway.providers.claude.subprocess.run")
    def test_ask_success(self, mock_run):
        mock_run.return_value = MagicMock(stdout="Hello from Claude!\n", returncode=0)
        result = ask("test question")
        self.assertEqual(result, "Hello from Claude!")
        mock_run.assert_called_once()
        self.assertIn("test question", mock_run.call_args[0][0])

    @patch("ask_oogway.providers.claude.subprocess.run")
    def test_ask_empty_stdout_raises_error(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        with self.assertRaises(AskOogwayError) as ctx:
            ask("test question")
        self.assertIn("claude returned an empty response", str(ctx.exception))

    @patch("ask_oogway.providers.claude.subprocess.run")
    def test_ask_whitespace_stdout_raises_error(self, mock_run):
        mock_run.return_value = MagicMock(stdout="   \n\t  \n", returncode=0)
        with self.assertRaises(AskOogwayError) as ctx:
            ask("test question")
        self.assertIn("claude returned an empty response", str(ctx.exception))

    @patch("ask_oogway.providers.claude.subprocess.run")
    def test_ask_cli_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError("claude not found")
        with self.assertRaises(AskOogwayError) as ctx:
            ask("test question")
        self.assertIn("the `claude` CLI was not found on PATH", str(ctx.exception))

    @patch("ask_oogway.providers.claude.subprocess.run")
    def test_ask_called_process_error(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["claude"],
            stderr="authentication failed",
        )
        with self.assertRaises(AskOogwayError) as ctx:
            ask("test question")
        self.assertIn("claude exited with 1: authentication failed", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
