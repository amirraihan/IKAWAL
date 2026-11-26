---
name: pstack-debug
description: "Reproduce and trace app, LiteLLM, Windows setup or PCAI deployment failures to their cause."
---

# Pstack debug

Adapted from pstack's fix-root-causes principle.

Reproduce the reported failure with the smallest relevant input. Identify which boundary failed before changing code: Windows prerequisites, local app, VPN/DNS, TLS, LiteLLM key/model, registry pull, Kubernetes scheduling, gateway route, or Keycloak discovery/callback/group claim.

Inspect the real error while keeping credentials and gateway bodies out of output. Form a specific explanation and check it. Fix the cause at its owner; avoid disabling TLS, authentication, group checks or policy as a workaround.

Run the failing path again and a focused adjacent check. Keep configuration changes repeatable, preserve existing keys and cookie secrets, and state when a fix is only locally verified. Use docs/acceptance.md for platform failure examples.
