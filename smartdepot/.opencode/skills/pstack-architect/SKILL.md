---
name: pstack-architect
description: "Design module ownership, APIs, tools, identity and state boundaries before substantial app changes."
---

# Pstack architect

Adapted from pstack's architect workflow.

Read the relevant source, then start from the caller's usage and acceptance example. Identify who owns identity, business state, model access, tool side effects and persistence. Keep external representations and validation at boundaries.

For a meaningful architectural choice, compare plausible structures and choose based on the actual requirements. Prefer one owner per rule and fewer concepts for the caller. Walk through the common path, retry, partial failure and concurrent access when relevant.

Write a proportional design showing usage, interfaces, ownership, flow and the material tradeoff. In this starter, the browser owns transient conversation state; the backend owns model credentials; oauth2-proxy owns login; the platform owns gateway, DNS and TLS. Adding durable user data requires a real identity key and a tenant-aware storage design. If implementation is requested, carry the chosen design through code and verification.
