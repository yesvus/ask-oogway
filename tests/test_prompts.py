"""Tests for the Oogway character prompt wiring."""

import os
import stat
import tempfile
import unittest
from unittest import mock

from ask_oogway.prompts import SYSTEM_PROMPT
from ask_oogway.providers import claude

_FAKE_ECHO_ARGS = """\
#!/bin/sh
printf '%s\\n' "$@"
"""


class TestPrompts(unittest.TestCase):
    def test_prompt_visible_and_nonempty(self):
        self.assertIn("Oogway", SYSTEM_PROMPT)
        self.assertIn("refuse to comfort", SYSTEM_PROMPT)

    def test_claude_passes_prompt_in_real_argv(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = os.path.join(tmp, "claude")
            with open(fake, "w") as f:
                f.write(_FAKE_ECHO_ARGS)
            os.chmod(fake, stat.S_IRWXU | stat.S_IXGRP | stat.S_IXOTH)
            env = {"PATH": tmp + os.pathsep + os.environ["PATH"]}
            with mock.patch.dict(os.environ, env):
                answer = claude.ask("hi", quiet=True)
        argv = answer.splitlines()
        self.assertIn("--append-system-prompt", argv)
        self.assertIn(SYSTEM_PROMPT, answer)
        self.assertEqual(argv[-1], "hi")


if __name__ == "__main__":
    unittest.main()
