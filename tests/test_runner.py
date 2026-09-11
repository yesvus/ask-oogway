import unittest
from unittest.mock import patch

from ask_oogway.errors import AskOogwayError
from ask_oogway.runner import ask


class TestRunner(unittest.TestCase):
    @patch("ask_oogway.runner.get_provider", return_value="claude")
    @patch("ask_oogway.runner.REGISTRY", {"claude": lambda prompt: "  test answer  "})
    def test_ask_success(self, _mock_provider):
        result = ask("hello")
        self.assertEqual(result, "test answer")

    @patch("ask_oogway.runner.get_provider", return_value="claude")
    @patch("ask_oogway.runner.REGISTRY", {"claude": lambda prompt: ""})
    def test_ask_empty_response(self, _mock_provider):
        with self.assertRaises(AskOogwayError) as ctx:
            ask("hello")
        self.assertIn("provider 'claude' returned an empty response", str(ctx.exception))

    @patch("ask_oogway.runner.get_provider", return_value="claude")
    @patch("ask_oogway.runner.REGISTRY", {"claude": lambda prompt: "   \n\t  "})
    def test_ask_whitespace_response(self, _mock_provider):
        with self.assertRaises(AskOogwayError) as ctx:
            ask("hello")
        self.assertIn("provider 'claude' returned an empty response", str(ctx.exception))

    @patch("ask_oogway.runner.get_provider", return_value="nonexistent")
    def test_ask_unknown_provider(self, _mock_provider):
        with self.assertRaises(AskOogwayError) as ctx:
            ask("hello")
        self.assertIn("unknown provider 'nonexistent' in config", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
