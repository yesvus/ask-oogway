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
from acp.schema import AgentMessageChunk, SessionMode, SessionModeState, SetSessionModeResponse, TextContentBlock


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
            modes=SessionModeState(
                current_mode_id="code",
                available_modes=[
                    SessionMode(id="code", name="Code"),
                    SessionMode(id="read-only", name="Read Only"),
                ],
            ),
        )

    async def set_session_mode(self, session_id, mode_id, **kwargs):
        trace("set_mode " + mode_id)
        self.mode = mode_id
        return SetSessionModeResponse()

    async def prompt(self, session_id, prompt, **kwargs):
        trace("prompt_start mode=" + str(self.mode))
        if self.mode != "read-only":
            raise ValueError("read-only mode was not selected")
        trace("before_update")
        try:
            chunk = AgentMessageChunk(content=TextContentBlock(type="text", text="ACP smoke OK"))
            trace("chunk_created")
            await self.conn.session_update(session_id=session_id, update=chunk)
            trace("after_update")
        except BaseException as exc:
            trace("agent_error: " + repr(exc))
            raise
        return PromptResponse(stop_reason="end_turn")


if __name__ == "__main__":
    asyncio.run(run_agent(EchoAgent()))
