"""End-to-end ACP SDK/stdio transport test (no credentials)."""

import importlib.util
import os
from pathlib import Path
import shlex
import sys
import unittest
import tempfile
from unittest.mock import patch

from ask_oogway.providers import acp


@unittest.skipUnless(importlib.util.find_spec("acp"), "install agent-client-protocol to run SDK test")
class TestACPIntegration(unittest.TestCase):
    def test_real_sdk_config_options_mode(self):
        fixture = Path(__file__).parent / "fixtures" / "acp_echo_agent.py"
        command = shlex.join([sys.executable, str(fixture)])
        with patch.dict(os.environ, {
            "ASK_OOGWAY_ACP_COMMAND": command,
            "ASK_OOGWAY_ACP_TRUST_AGENT": "1",
            "ACP_SMOKE_CONFIG_ONLY": "1",
        }):
            self.assertEqual(acp.ask("hello", timeout=10), "ACP smoke OK")

    def test_real_sdk_protocol_round_trip(self):
        fixture = Path(__file__).parent / "fixtures" / "acp_echo_agent.py"
        command = shlex.join([sys.executable, str(fixture)])
        with tempfile.TemporaryDirectory() as tmp:
            trace = Path(tmp) / "trace.txt"
            with patch.dict(os.environ, {"ASK_OOGWAY_ACP_COMMAND": command, "ASK_OOGWAY_ACP_TRUST_AGENT": "1", "ACP_SMOKE_TRACE": str(trace)}):
                try:
                    self.assertEqual(acp.ask("hello", timeout=10), "ACP smoke OK")
                except Exception as exc:
                    self.fail(f"{exc}; agent trace: {trace.read_text() if trace.exists() else 'no trace'}")


if __name__ == "__main__":
    unittest.main()
