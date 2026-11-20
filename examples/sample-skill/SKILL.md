---
name: commit-message-writer
description: Write a clear conventional-commit message for staged changes.
---

# Commit Message Writer

When asked to write a commit message:

1. Look at the change summary the user provides.
2. Use the form `type(scope): summary` where type is one of
   feat, fix, docs, refactor, test, chore.
3. Keep the summary under 72 characters, imperative mood.
4. Add a body only when the change needs a "why", not a "what".
