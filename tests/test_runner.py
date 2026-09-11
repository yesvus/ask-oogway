"""Tests for ask_oogway.runner.ask dispatch."""

import unittest
from unittest.mock import patch

from ask_oogway.errors import AskOogwayError
from ask_oogway.runner import ask


class TestAsk(unittest.TestCase):
    def test_unknown_provider(self):
        with (
            patch("ask_oogway.runner.get_provider", return_value="nope"),
            patch("ask_oogway.runner.REGISTRY", {"stub": lambda p, **_: "x"}),
        ):
            with self.assertRaises(AskOogwayError) as cm:
                ask("hello")
        self.assertIn("unknown provider 'nope'", str(cm.exception))
        self.assertIn("known:", str(cm.exception))

    def test_known_provider_dispatches(self):
        received = []

        def fake(prompt, **_):
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
        def fake(prompt, **_):
            raise AskOogwayError("boom")

        with (
            patch("ask_oogway.runner.get_provider", return_value="stub"),
            patch("ask_oogway.runner.REGISTRY", {"stub": fake}),
        ):
            with self.assertRaisesRegex(AskOogwayError, "boom"):
                ask("hello")

    def test_forwards_timeout_and_quiet(self):
        seen = {}

        def fake(prompt, *, timeout=None, quiet=False):
            seen.update(prompt=prompt, timeout=timeout, quiet=quiet)
            return "ok"

        with (
            patch("ask_oogway.runner.get_provider", return_value="stub"),
            patch("ask_oogway.runner.REGISTRY", {"stub": fake}),
        ):
            self.assertEqual(ask("hi", timeout=45, quiet=True), "ok")
        self.assertEqual(seen, {"prompt": "hi", "timeout": 45, "quiet": True})


if __name__ == "__main__":
    unittest.main()
