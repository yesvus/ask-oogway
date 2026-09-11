"""Tests for ask_oogway.runner.ask dispatch."""

import unittest
from unittest.mock import patch

from ask_oogway.errors import AskOogwayError
from ask_oogway.runner import ask


class TestAsk(unittest.TestCase):
    def test_unknown_provider(self):
        with (
            patch("ask_oogway.runner.get_provider", return_value="nope"),
            patch("ask_oogway.runner.REGISTRY", {"stub": lambda p: "x"}),
        ):
            with self.assertRaises(AskOogwayError) as cm:
                ask("hello")
        self.assertIn("unknown provider 'nope'", str(cm.exception))
        self.assertIn("known:", str(cm.exception))

    def test_known_provider_dispatches(self):
        received = []

        def fake(prompt):
            received.append(prompt)
            return "stub-response"

        with (
            patch("ask_oogway.runner.get_provider", return_value="stub"),
            patch("ask_oogway.runner.REGISTRY", {"stub": fake}),
        ):
            result = ask("hello")
        self.assertEqual(result, "stub-response")
        self.assertEqual(received, ["hello"])

    def test_provider_errors_propagate(self):
        def fake(prompt):
            raise AskOogwayError("boom")

        with (
            patch("ask_oogway.runner.get_provider", return_value="stub"),
            patch("ask_oogway.runner.REGISTRY", {"stub": fake}),
        ):
            with self.assertRaisesRegex(AskOogwayError, "boom"):
                ask("hello")


if __name__ == "__main__":
    unittest.main()
