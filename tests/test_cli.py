import io
import unittest
from unittest.mock import patch

from ask_oogway.cli import main
from ask_oogway.errors import AskOogwayError


@patch("ask_oogway.cli.version", return_value="0.1.0")
class TestCLI(unittest.TestCase):
    @patch("ask_oogway.cli.ask", return_value="Here is the wisdom")
    @patch("sys.argv", ["ask-oogway", "-m", "should I use X?"])
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_cli_success(self, mock_stdout, _mock_ask, _mock_ver):
        main()
        self.assertEqual(mock_stdout.getvalue().strip(), "Here is the wisdom")

    @patch("ask_oogway.cli.ask", side_effect=AskOogwayError("claude returned an empty response"))
    @patch("sys.argv", ["ask-oogway", "-m", "should I use X?"])
    @patch("sys.stderr", new_callable=io.StringIO)
    def test_cli_empty_response_error(self, mock_stderr, _mock_ask, _mock_ver):
        with self.assertRaises(SystemExit) as ctx:
            main()
        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("ask-oogway: claude returned an empty response", mock_stderr.getvalue())

    @patch("sys.argv", ["ask-oogway"])
    @patch("sys.stdin.isatty", return_value=True)
    @patch("sys.stderr", new_callable=io.StringIO)
    def test_cli_missing_message(self, mock_stderr, _mock_isatty, _mock_ver):
        with self.assertRaises(SystemExit) as ctx:
            main()
        self.assertEqual(ctx.exception.code, 2)
        self.assertIn("missing message", mock_stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
