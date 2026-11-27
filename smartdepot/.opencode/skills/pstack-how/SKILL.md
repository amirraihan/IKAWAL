---
name: pstack-how
description: "Trace how the current app, tool loop, configuration or deployment works from inspected source."
---

# Pstack how

Adapted from pstack's how workflow.

Start at the concrete trigger: a click, HTTP request, tool call or deployment command. Trace the source to its inputs, owner, state, external calls and observable result. Cite actual files and symbols. For this pack, start with app/main.py, app/agent.py, scripts/workshop.py and deploy/chart/templates as applicable.

Explain the path in the order it executes. Separate inspected code from an observed runtime result. When behavior depends on Keycloak, a gateway, CNI or LiteLLM, identify that dependency instead of assuming it works. Do not change code when the user only asks for an explanation.
