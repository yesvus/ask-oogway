from . import chatgpt, claude

REGISTRY = {
    "claude": claude.ask,
    "chatgpt": chatgpt.ask,
}
