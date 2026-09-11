"""Tests for the chatgpt provider stub."""

import unittest

from ask_oogway.errors import AskOogwayError
from ask_oogway.providers import chatgpt


class TestChatgptStub(unittest.TestCase):
    def test_not_implemented(self):
        with self.assertRaisesRegex(AskOogwayError, "isn't implemented"):
            chatgpt.ask("hi")

    def test_accepts_provider_kwargs(self):
        with self.assertRaises(AskOogwayError):
            chatgpt.ask("hi", timeout=10, quiet=True)


if __name__ == "__main__":
    unittest.main()
