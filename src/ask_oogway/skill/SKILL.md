---
name: ask-oogway
description: Consult a stronger external model for a hard question or an important decision, when you're genuinely unsure and don't want to guess. Use before making a costly or hard-to-reverse call you lack confidence in.
---

# ask-oogway

Run:

    ask-oogway -m "<your question, as ONE quoted argument>"

The question must be a single quoted string. Read the answer from stdout.
ask-oogway has no memory between calls, so include whatever context the
question needs in the message itself.

If you'd answer confidently without help, don't use it.

ask-oogway is read-only: it can search and read, but it cannot write files,
run commands, or change anything. It only ever answers.
