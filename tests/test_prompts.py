"""Tests for the Oogway character prompt wiring."""

import unittest

from ask_oogway.prompts import SYSTEM_PROMPT
from ask_oogway.providers import claude


class TestPrompts(unittest.TestCase):
    def test_prompt_visible_and_nonempty(self):
        self.assertIn("Oogway", SYSTEM_PROMPT)
        self.assertIn("Verdict first", SYSTEM_PROMPT)

    def test_claude_appends_prompt_one_shot(self):
        flag = "--append-system-prompt"
        self.assertIn(flag, claude._ARGS)
        self.assertEqual(claude._ARGS[claude._ARGS.index(flag) + 1], SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
