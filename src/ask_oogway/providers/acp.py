"""ACP agent client provider (opt-in). Not an OS sandbox."""

import asyncio
import json
import os
import shlex
from pathlib import Path

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


def _safe_mode(session) -> tuple[str, str, str | None]:
    """Choose an advertised mode and its corresponding ACP selection API."""
    legacy = {
        item.id
        for item in (getattr(getattr(session, "modes", None), "available_modes", ()) or ())
    }
    config_ids: dict[str, str] = {}
    for option in getattr(session, "config_options", ()) or ():
        option_id = getattr(option, "id", None)
        if option_id != "mode" and getattr(option, "category", None) != "mode":
            continue
        for item in getattr(option, "options", ()) or ():
            value = getattr(item, "value", None)
            if isinstance(value, str):
                config_ids[value] = option_id
            else:  # grouped select options
                for child in getattr(item, "options", ()) or ():
                    if isinstance(getattr(child, "value", None), str):
                        config_ids[child.value] = option_id
    for candidate in _SAFE_MODES:
        if candidate in legacy:
            return candidate, "legacy", None
        if candidate in config_ids:
            return candidate, "config", config_ids[candidate]
    raise AskOogwayError(
        "ACP agent does not advertise a supported advisory mode "
        "(read-only/read_only/plan/architect) in modes or configOptions; refusing to run"
    )


def _agent_env(argv: list[str]) -> dict[str, str]:
    """Apply a deny-by-default tool policy for OpenCode; trust others explicitly.

    ACP controls the client transport, not native agent tools. These tool
    permissions are defense in depth, not an OS isolation boundary.
    """
    env = os.environ.copy()
    command = Path(argv[0]).name.lower()
    is_opencode = command in ("opencode", "opencode.exe") and "acp" in argv[1:]
    if not is_opencode:
        if env.get("ASK_OOGWAY_ACP_TRUST_AGENT") != "1":
            raise AskOogwayError(
                "unknown ACP agent tool policy; configure an isolated agent and "
                "set ASK_OOGWAY_ACP_TRUST_AGENT=1 to explicitly opt in"
            )
        return env

    try:
        config = json.loads(env.get("OPENCODE_CONFIG_CONTENT") or "{}")
    except json.JSONDecodeError as exc:
        raise AskOogwayError("invalid OPENCODE_CONFIG_CONTENT JSON") from exc
    if not isinstance(config, dict):
        raise AskOogwayError("OPENCODE_CONFIG_CONTENT must contain a JSON object")

    # OpenCode V1 uses 'permission', V2 uses ordered 'permissions'. The latter
    # includes wildcard-deny first, then narrowly permitted inspection tools.
    v1 = {
        "*": "deny",
        "read": {"*": "allow", "*.env": "deny", "*.env.*": "deny"},
        "glob": "allow", "grep": "allow", "list": "allow",
        "webfetch": "deny", "websearch": "deny",
        "edit": "deny", "bash": "deny", "task": "deny",
        "external_directory": "deny",
    }
    rules = [
        {"action": "*", "resource": "*", "effect": "deny"},
        *(
            {"action": name, "resource": "*", "effect": "allow"}
            for name in ("read", "glob", "grep")
        ),
        {"action": "read", "resource": "*.env", "effect": "deny"},
        {"action": "read", "resource": "*.env.*", "effect": "deny"},
    ]
    config["permission"] = v1
    existing = config.get("permissions") or []
    if not isinstance(existing, list):
        raise AskOogwayError("OpenCode inline permissions must be a list")
    config["permissions"] = [*existing, *rules]

    # Agent-level permissions can override global permissions in OpenCode.
    # The plan agent is the common ACP advisory mode. Restrict it as well.
    v1_agents = config.get("agent") or {}
    v2_agents = config.get("agents") or {}
    if not isinstance(v1_agents, dict) or not isinstance(v2_agents, dict):
        raise AskOogwayError("OpenCode inline agent configurations must be objects")
    v1_plan = dict(v1_agents.get("plan") or {})
    v1_plan["permission"] = v1
    v1_agents["plan"] = v1_plan
    v2_plan = dict(v2_agents.get("plan") or {})
    current = v2_plan.get("permissions") or []
    if not isinstance(current, list):
        raise AskOogwayError("OpenCode plan permissions must be a list")
    v2_plan["permissions"] = [*current, *rules]
    v2_agents["plan"] = v2_plan
    config["agent"] = v1_agents
    config["agents"] = v2_agents
    env["OPENCODE_CONFIG_CONTENT"] = json.dumps(config)
    return env


async def _exchange(prompt: str, argv: list[str]) -> str:
    try:
        from acp import PROTOCOL_VERSION, Client, RequestError, spawn_agent_process
        from acp.schema import AgentMessageChunk, TextContentBlock
    except ModuleNotFoundError as exc:
        if exc.name == "acp":
            raise AskOogwayError(
                "ACP Python SDK missing: install with "
                "'uv tool install --editable . --with agent-client-protocol==0.12.1'"
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
    async with spawn_agent_process(client, *argv, env=_agent_env(argv)) as (connection, _process):
        await connection.initialize(protocol_version=PROTOCOL_VERSION)
        session = await connection.new_session(cwd=os.getcwd(), mcp_servers=[])
        mode, source, config_id = _safe_mode(session)
        if source == "config":
            await connection.set_config_option(
                config_id=config_id, session_id=session.session_id, value=mode
            )
        else:
            await connection.set_session_mode(
                session_id=session.session_id, mode_id=mode
            )
        result = await connection.prompt(
            session_id=session.session_id,
            prompt=[TextContentBlock(type="text", text=f"{SYSTEM_PROMPT}\n\n{prompt}")],
        )
        if result.stop_reason != "end_turn":
            raise AskOogwayError(
                f"ACP agent did not finish the turn (stop reason: {result.stop_reason})"
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
    except AskOogwayError:
        raise
    except Exception as exc:
        raise AskOogwayError(f"ACP agent request failed: {exc}") from exc
