"""Mocked ACP protocol tests: no credentials or agent binaries needed."""

import asyncio
import os
import sys
import types
import unittest
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import patch

from ask_oogway.errors import AskOogwayError
from ask_oogway.providers import acp


class FakeRequestError(Exception):
    @staticmethod
    def invalid_params(detail):
        return FakeRequestError(str(detail))


class FakeText:
    def __init__(self, text, type="text"):
        self.text = text


class FakeThoughtChunk:
    def __init__(self, content):
        self.content = content


class FakeImage:
    def __init__(self, payload):
        self.payload = payload


class FakeAgentChunk:
    def __init__(self, content):
        self.content = content


class FakeConnection:
    def __init__(self, client, *, modes=("read-only",), chunks=("Answer",), config_modes=(), stop_reason="end_turn"):
        self.client = client
        self.modes = modes
        self.chunks = chunks
        self.config_modes = config_modes
        self.stop_reason = stop_reason
        self.chosen = None
        self.selection_api = None
        self.seen_prompt = None
        self.cwd = None
        self.mcp_servers = None

    async def initialize(self, *, protocol_version):
        self.protocol_version = protocol_version

    async def new_session(self, *, cwd, mcp_servers):
        self.cwd, self.mcp_servers = cwd, mcp_servers
        return SimpleNamespace(
            session_id="s1",
            config_options=[SimpleNamespace(id="mode", options=[SimpleNamespace(value=x) for x in self.config_modes])],
            modes=SimpleNamespace(
                available_modes=[SimpleNamespace(id=item) for item in self.modes]
            ) if self.modes is not None else None,
        )

    async def set_session_mode(self, *, session_id, mode_id):
        if self.modes is None or mode_id not in self.modes:
            raise RuntimeError("unadvertised legacy mode")
        self.chosen = mode_id
        self.selection_api = "legacy"

    async def set_config_option(self, *, config_id, session_id, value):
        if config_id != "mode" or value not in self.config_modes:
            raise RuntimeError("unadvertised config mode")
        self.chosen = value
        self.selection_api = "config"

    async def prompt(self, *, session_id, prompt):
        self.seen_prompt = prompt[0].text
        # Only agent message text is returned. Ignore thoughts, tool updates
        # and non-text content even when emitted during the same prompt.
        await self.client.session_update("s1", FakeThoughtChunk(FakeText("internal thought")))
        await self.client.session_update("s1", SimpleNamespace(kind="tool_call", title="read"))
        await self.client.session_update("s1", FakeAgentChunk(FakeImage("image bytes")))
        for chunk in self.chunks:
            await self.client.session_update("s1", FakeAgentChunk(FakeText(chunk)))
        return SimpleNamespace(stop_reason=self.stop_reason)


class TestACP(unittest.TestCase):
    def sdk(self, *, modes=("read-only",), chunks=("Answer",), config_modes=(), stop_reason="end_turn", fail_spawn=False):
        state = {}
        fake_acp = types.ModuleType("acp")
        fake_schema = types.ModuleType("acp.schema")

        class Client:
            pass

        @asynccontextmanager
        async def spawn(client, *argv, env=None):
            if fail_spawn:
                raise FileNotFoundError(argv[0])
            conn = FakeConnection(client, modes=modes, chunks=chunks, config_modes=config_modes, stop_reason=stop_reason)
            state["conn"], state["argv"] = conn, argv
            yield conn, object()

        fake_acp.Client = Client
        fake_acp.PROTOCOL_VERSION = 1
        fake_acp.RequestError = FakeRequestError
        fake_acp.spawn_agent_process = spawn
        fake_schema.AgentMessageChunk = FakeAgentChunk
        fake_schema.TextContentBlock = FakeText
        return patch.dict(sys.modules, {"acp": fake_acp, "acp.schema": fake_schema}), state

    def test_missing_command(self):
        with patch.dict(os.environ, {_env(): ""}):
            with self.assertRaisesRegex(AskOogwayError, "not configured"):
                acp.ask("hi")

    def test_success_collects_only_answer_and_selects_safe_mode(self):
        mocked, state = self.sdk(modes=("auto", "plan"), chunks=("A", "B"))
        with mocked, patch.dict(os.environ, {_env(): "opencode acp"}):
            self.assertEqual(acp.ask("My question"), "AB")
        conn = state["conn"]
        self.assertEqual(conn.chosen, "plan")
        self.assertEqual(conn.selection_api, "legacy")
        self.assertEqual(conn.mcp_servers, [])
        self.assertEqual(state["argv"], ("opencode", "acp"))
        self.assertIn("My question", conn.seen_prompt)

    def test_fails_closed_without_read_only_mode(self):
        mocked, state = self.sdk(modes=("code",))
        with mocked, patch.dict(os.environ, {_env(): "opencode acp"}):
            with self.assertRaisesRegex(AskOogwayError, "refusing"):
                acp.ask("hi")
        self.assertIsNone(state["conn"].seen_prompt)

    def test_fails_closed_when_no_modes_advertised(self):
        mocked, _ = self.sdk(modes=None)
        with mocked, patch.dict(os.environ, {_env(): "opencode acp"}):
            with self.assertRaisesRegex(AskOogwayError, "supported advisory mode"):
                acp.ask("hi")

    def test_deny_permissions_and_client_side_writes(self):
        mocked, state = self.sdk()
        with mocked, patch.dict(os.environ, {_env(): "opencode acp"}):
            acp.ask("hi")
        client = state["conn"].client
        decision = asyncio.run(client.request_permission("s1", None, []))
        self.assertEqual(decision, {"outcome": {"outcome": "cancelled"}})
        with self.assertRaises(FakeRequestError):
            asyncio.run(client.write_text_file("s1", "/tmp/x", "secret"))
        with self.assertRaises(FakeRequestError):
            asyncio.run(client.create_terminal("s1", "rm -rf ."))
        with self.assertRaises(FakeRequestError):
            asyncio.run(client.read_text_file("s1", "/tmp/x"))

    def test_config_options_mode_for_current_opencode(self):
        mocked, state = self.sdk(modes=None, config_modes=("build", "plan"))
        with mocked, patch.dict(os.environ, {_env(): "opencode acp"}):
            self.assertEqual(acp.ask("design review"), "Answer")
        self.assertEqual(state["conn"].chosen, "plan")
        self.assertEqual(state["conn"].selection_api, "config")

    def test_unknown_agent_requires_explicit_trust(self):
        with patch.dict(os.environ, {_env(): "generic-agent --acp"}, clear=True):
            with self.assertRaisesRegex(AskOogwayError, "TRUST_AGENT"):
                acp.ask("hi")

    def test_opencode_policy_fails_closed_and_keeps_existing_config(self):
        with patch.dict(os.environ, {
            "OPENCODE_CONFIG_CONTENT": '{"model":"vendor/model","permissions":[{"action":"edit","resource":"*","effect":"allow"}]}',
        }):
            import json
            config = json.loads(acp._agent_env(["opencode", "acp"])["OPENCODE_CONFIG_CONTENT"])
        self.assertEqual(config["model"], "vendor/model")
        self.assertEqual(config["permission"]["bash"], "deny")
        self.assertEqual(config["permission"]["edit"], "deny")
        self.assertEqual(config["permissions"][-1]["effect"], "deny")
        self.assertEqual(config["agents"]["plan"]["permissions"][0]["effect"], "deny")
        self.assertEqual(config["agents"]["plan"]["permissions"][1]["action"], "read")

    def test_web_tools_denied_by_default(self):
        import json
        with patch.dict(os.environ, {"OPENCODE_CONFIG_CONTENT": "{}"}):
            config = json.loads(acp._agent_env(["opencode", "acp"])["OPENCODE_CONFIG_CONTENT"])
        self.assertEqual(config["permission"]["webfetch"], "deny")
        self.assertEqual(config["permission"]["websearch"], "deny")
        self.assertNotIn("webfetch", [r["action"] for r in config["permissions"] if r["effect"] == "allow"])
        self.assertNotIn("websearch", [r["action"] for r in config["permissions"] if r["effect"] == "allow"])

    def test_protocol_failures_are_normalized(self):
        async def broken(prompt, argv):
            raise RuntimeError("server disconnected")
        with patch.dict(os.environ, {_env(): "opencode acp"}), patch.object(acp, "_exchange", side_effect=broken):
            with self.assertRaisesRegex(AskOogwayError, "server disconnected"):
                acp.ask("hi")

    def test_invalid_opencode_inline_config(self):
        with patch.dict(os.environ, {"OPENCODE_CONFIG_CONTENT": "invalid"}):
            with self.assertRaisesRegex(AskOogwayError, "invalid OPENCODE"):
                acp._agent_env(["opencode", "acp"])

    def test_incomplete_turn_does_not_report_success(self):
        mocked, _ = self.sdk(stop_reason="cancelled")
        with mocked, patch.dict(os.environ, {_env(): "opencode acp"}):
            with self.assertRaisesRegex(AskOogwayError, "did not finish"):
                acp.ask("hi")

    def test_empty_answer_is_error(self):
        mocked, _ = self.sdk(chunks=())
        with mocked, patch.dict(os.environ, {_env(): "opencode acp"}):
            with self.assertRaisesRegex(AskOogwayError, "no text answer"):
                acp.ask("hi")

    def test_missing_executable_is_actionable(self):
        mocked, _ = self.sdk(fail_spawn=True)
        with mocked, patch.dict(os.environ, {_env(): "missing-acp --foo", "ASK_OOGWAY_ACP_TRUST_AGENT": "1"}):
            with self.assertRaisesRegex(AskOogwayError, "missing-acp"):
                acp.ask("hi")

    def test_bad_command_and_negative_timeout(self):
        with patch.dict(os.environ, {_env(): 'unterminated "'}):
            with self.assertRaisesRegex(AskOogwayError, "invalid"):
                acp.ask("hi")
        with patch.dict(os.environ, {_env(): "opencode acp"}):
            with self.assertRaisesRegex(AskOogwayError, "timeout must"):
                acp.ask("hi", timeout=-1)

    def test_timeout(self):
        async def hang(prompt, argv):
            await asyncio.sleep(1)
        with (
            patch.dict(os.environ, {_env(): "opencode acp"}),
            patch.object(acp, "_ABSOLUTE_TIMEOUT", 0.01),
            patch.object(acp, "_exchange", side_effect=hang),
        ):
            with self.assertRaisesRegex(AskOogwayError, "timed out"):
                acp.ask("hi")

    def test_missing_sdk_guidance(self):
        with (
            patch.dict(os.environ, {_env(): "opencode acp"}),
            patch.dict(sys.modules, {"acp": None, "acp.schema": None}),
        ):
            with self.assertRaisesRegex(AskOogwayError, "SDK missing"):
                acp.ask("hi")


def _env():
    return "ASK_OOGWAY_ACP_COMMAND"


if __name__ == "__main__":
    unittest.main()
