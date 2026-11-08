"""Local, credential-free ACP echo agent for integration tests."""

import asyncio
import os
from pathlib import Path


def trace(text):
    path = os.environ.get('ACP_SMOKE_TRACE')
    if path:
        with Path(path).open('a') as fp:
            fp.write(text + '\n')


from acp import Agent, InitializeResponse, NewSessionResponse, PromptResponse, run_agent
from acp.schema import AgentMessageChunk, SessionMode, SessionModeState, SessionConfigOptionSelect, SessionConfigSelectOption, SetSessionModeResponse, SetSessionConfigOptionResponse, TextContentBlock


class EchoAgent(Agent):
    def on_connect(self, conn):
        self.conn = conn
        self.mode = None

    async def initialize(self, protocol_version, **kwargs):
        trace("initialized")
        return InitializeResponse(protocol_version=protocol_version)

    async def new_session(self, cwd, mcp_servers=None, **kwargs):
        if mcp_servers:
            raise ValueError("test client must not expose MCP servers")
        trace("new_session")
        return NewSessionResponse(
            session_id="echo-test",
            config_options=[SessionConfigOptionSelect(
                id="mode", name="Mode", category="mode", type="select", current_value="code",
                options=[SessionConfigSelectOption(value="code", name="Code"), SessionConfigSelectOption(value="plan", name="Plan")],
            )] if os.environ.get("ACP_SMOKE_CONFIG_ONLY") else None,
            modes=None if os.environ.get("ACP_SMOKE_CONFIG_ONLY") else SessionModeState(
                current_mode_id="code",
                available_modes=[
                    SessionMode(id="code", name="Code"),
                    SessionMode(id="read-only", name="Read Only"),
                ],
            ),
        )

    async def set_session_mode(self, session_id, mode_id, **kwargs):
        if os.environ.get("ACP_SMOKE_CONFIG_ONLY") or mode_id != "read-only":
            raise ValueError("legacy mode not advertised")
        trace("set_mode " + mode_id)
        self.mode = mode_id
        return SetSessionModeResponse()

    async def set_config_option(self, config_id, session_id, value, **kwargs):
        if not os.environ.get("ACP_SMOKE_CONFIG_ONLY") or config_id != "mode" or value != "plan":
            raise ValueError("config mode not advertised")
        trace("set_config_option " + value)
        self.mode = value
        return SetSessionConfigOptionResponse(config_options=[
            SessionConfigOptionSelect(
                id="mode", name="Mode", category="mode", type="select", current_value="plan",
                options=[
                    SessionConfigSelectOption(value="code", name="Code"),
                    SessionConfigSelectOption(value="plan", name="Plan"),
                ],
            ),
        ])

    async def prompt(self, session_id, prompt, **kwargs):
        trace("prompt_start mode=" + str(self.mode))
        if os.environ.get("ACP_SMOKE_HANG"):
            await asyncio.sleep(60)
        expected = "plan" if os.environ.get("ACP_SMOKE_CONFIG_ONLY") else "read-only"
        if self.mode != expected:
            raise ValueError("advertised safe mode was not selected")
        trace("before_update")
        try:
            chunk = AgentMessageChunk(session_update="agent_message_chunk", content=TextContentBlock(type="text", text="ACP smoke OK"))
            trace("chunk_created")
            await self.conn.session_update(session_id=session_id, update=chunk)
            trace("after_update")
        except BaseException as exc:
            trace("agent_error: " + repr(exc))
            raise
        return PromptResponse(stop_reason="end_turn")


if __name__ == "__main__":
    asyncio.run(run_agent(EchoAgent()))
