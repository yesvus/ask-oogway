"""Local, credential-free ACP echo agent for integration tests."""

import asyncio

from acp import Agent, InitializeResponse, NewSessionResponse, PromptResponse, run_agent
from acp.schema import AgentMessageChunk, SessionMode, SessionModeState, SetSessionModeResponse, TextContentBlock


class EchoAgent(Agent):
    def on_connect(self, conn):
        self.conn = conn
        self.mode = None

    async def initialize(self, protocol_version, **kwargs):
        return InitializeResponse(protocol_version=protocol_version)

    async def new_session(self, cwd, mcp_servers=None, **kwargs):
        if mcp_servers:
            raise ValueError("test client must not expose MCP servers")
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
        self.mode = mode_id
        return SetSessionModeResponse()

    async def prompt(self, session_id, prompt, **kwargs):
        if self.mode != "read-only":
            raise ValueError("read-only mode was not selected")
        await self.conn.session_update(
            session_id=session_id,
            update=AgentMessageChunk(content=TextContentBlock(text="ACP smoke OK")),
        )
        return PromptResponse(stop_reason="end_turn")


if __name__ == "__main__":
    asyncio.run(run_agent(EchoAgent()))
