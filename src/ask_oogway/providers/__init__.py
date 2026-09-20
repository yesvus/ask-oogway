from . import chatgpt, claude, openai

# Provider contract: ask(prompt, *, timeout=None, quiet=False) -> str.
# timeout caps the call in seconds (0 disables the ceiling); quiet
# suppresses stderr status, never errors. Literal order is detection priority.
REGISTRY = {
    "claude": claude.ask,
    "chatgpt": chatgpt.ask,
    "openai": openai.ask,
}

# Providers that actually answer. The rest are stubs the wizard warns about.
IMPLEMENTED = {"claude", "openai"}
