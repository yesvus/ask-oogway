"""End-to-end ACP SDK/stdio transport test (no credentials)."""

import importlib.util
import os
from pathlib import Path
import shlex
import sys
import unittest
from unittest.mock import patch

from ask_oogway.providers import acp


@unittest.skipUnless(importlib.util.find_spec("acp"), "install agent-client-protocol to run SDK test")
class TestACPIntegration(unittest.TestCase):
    def test_real_sdk_protocol_round_trip(self):
        fixture = Path(__file__).parent / "fixtures" / "acp_echo_agent.py"
        command = shlex.join([sys.executable, str(fixture)])
        with patch.dict(os.environ, {"ASK_OOGWAY_ACP_COMMAND": command}):
            self.assertEqual(acp.ask("hello", timeout=20), "ACP smoke OK")


if __name__ == "__main__":
    unittest.main()
