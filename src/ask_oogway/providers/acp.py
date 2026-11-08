"""ACP agent client provider (opt-in). Not an OS sandbox."""

import asyncio
import os
import shlex

from ..errors import AskOogwayError
from ..prompts import SYSTEM_PROMPT

_ABSOLUTE_TIMEOUT = 1800
_COMMAND_ENV = "ASK_OOGWAY_ACP_COMMAND"
# Mode names are agent-defined. Never silently run in its default edit mode.
_SAFE_MODES = ("read-only", "read_only", "plan", "architect")


def _command() -> list[str]:
    raw = os.environ.get(_COMMAND_ENV, "").strip()
    if not raw:
        raise AskOogwayError(
            f"ACP agent not configured: set {_COMMAND_ENV} "
            '(e.g. "opencode acp")'
        )
    try:
        argv = shlex.split(raw)
    except ValueError as exc:
        raise AskOogwayError(f"invalid {_COMMAND_ENV}: {exc}") from exc
    if not argv:
        raise AskOogwayError(f"empty {_COMMAND_ENV}")
    return argv


def _safe_mode(session) -> str:
    modes = getattr(session, "modes", None)
    available = getattr(modes, "available_modes", ()) or ()
    ids = {mode.id for mode in available}
    for candidate in _SAFE_MODES:
        if candidate in ids:
            return candidate
    raise AskOogwayError(
        "ACP agent does not advertise a non-editing session mode "
        "(read-only/plan/architect); refusing to run. "
        "Choose an agent with a non-editing mode."
    )


async def _exchange(prompt: str, argv: list[str]) -> str:
    try:
        from acp import PROTOCOL_VERSION, Client, RequestError, spawn_agent_process
        from acp.schema import AgentMessageChunk, TextContentBlock
    except ModuleNotFoundError as exc:
        if exc.name == "acp":
            raise AskOogwayError(
                "ACP Python SDK missing: install with "
                "'uv tool install --editable . --with agent-client-protocol'"
            ) from exc
        raise

    class ReadOnlyClient(Client):
        def __init__(self):
            self.chunks: list[str] = []

        async def request_permission(self, session_id, tool_call, options, **kwargs):
            # Do not approve even a nominally read-only tool: the agent's
            # advertised classifications and permission choices are untrusted.
            return {"outcome": {"outcome": "cancelled"}}

        async def session_update(self, session_id, update, **kwargs):
            if isinstance(update, AgentMessageChunk):
                content = update.content
                if isinstance(content, TextContentBlock):
                    self.chunks.append(content.text)

        async def write_text_file(self, session_id, path, content, **kwargs):
            raise RequestError.invalid_params({"reason": "ask-oogway is read-only"})

        async def create_terminal(self, session_id, command, **kwargs):
            raise RequestError.invalid_params({"reason": "ask-oogway cannot create terminals"})

        async def read_text_file(self, session_id, path, **kwargs):
            # Do not provide a second, unchecked file-access path. Native
            # agent tools are still subject to the agent's own sandbox.
            raise RequestError.invalid_params({"reason": "client file access disabled"})

    client = ReadOnlyClient()
    async with spawn_agent_process(client, *argv) as (connection, _process):
        await connection.initialize(protocol_version=PROTOCOL_VERSION)
        session = await connection.new_session(cwd=os.getcwd(), mcp_servers=[])
        mode = _safe_mode(session)
        await connection.set_session_mode(session_id=session.session_id, mode_id=mode)
        await connection.prompt(
            session_id=session.session_id,
            prompt=[TextContentBlock(type="text", text=f"{SYSTEM_PROMPT}\n\n{prompt}")],
        )
    answer = "".join(client.chunks).strip()
    if not answer:
        raise AskOogwayError("ACP agent returned no text answer")
    return answer


def ask(prompt: str, *, timeout: int | None = None, quiet: bool = False) -> str:
    if timeout is not None and timeout < 0:
        raise AskOogwayError("--timeout must be >= 0 seconds")
    argv = _command()
    ceiling = _ABSOLUTE_TIMEOUT if timeout is None else timeout
    try:
        return asyncio.run(
            asyncio.wait_for(_exchange(prompt, argv), timeout=ceiling or None)
        )
    except TimeoutError as exc:
        raise AskOogwayError(f"ACP agent timed out after {ceiling}s") from exc
    except FileNotFoundError as exc:
        raise AskOogwayError(f"ACP agent executable not found: {argv[0]}") from exc
    except OSError as exc:
        raise AskOogwayError(f"ACP agent process error: {exc}") from exc
