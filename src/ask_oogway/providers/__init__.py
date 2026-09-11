from . import chatgpt, claude

# Provider contract: ask(prompt, *, timeout=None, quiet=False) -> str.
# timeout caps the call in seconds (0 disables the ceiling); quiet
# suppresses stderr status, never errors. Literal order is detection priority.
REGISTRY = {
    "claude": claude.ask,
    "chatgpt": chatgpt.ask,
}
