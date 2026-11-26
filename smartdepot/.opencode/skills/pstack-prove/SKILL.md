---
name: pstack-prove
description: "Verify working behavior and reusable artifacts before reporting an app or deployment task complete."
---

# Pstack prove

Adapted from pstack's prove-it-works principle.

Ask what observation would establish the requested outcome. Run the actual feature or inspect the actual saved artifact. Syntax, file timestamps, a successful build and a ready pod are intermediate evidence.

Use scripts/validate.py for repeatable local checks, then the task-specific user flow. For browser work, check the visible success/error state and download contents. For PCAI, verify the full login-to-model path and denied access, not only pod health.

Inspect the final diff and sharing archive. Ensure .local, .venv, tokens, kubeconfig, private keys and generated secret material are excluded. State which checks ran, which used mocks and which require the actual platform. Never claim deployment from a rendered chart.
