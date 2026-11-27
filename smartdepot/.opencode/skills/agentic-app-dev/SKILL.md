---
name: agentic-app-dev
description: "Build and extend the HPE PCAI starter app: plan a feature, implement it, test the user flow, and prepare reusable artifacts."
---

# Agentic app dev

Build one useful user flow from request to working app. Read the selected project's AGENTS.md and affected source before editing. The installed plugin is reference material; do not modify its installed files. Use pcai_scaffold to create a new app when needed.

1. State the user outcome and acceptance example. For a substantial feature, use pstack-architect to decide ownership, data flow and persistence before implementation.
2. Keep model calls behind the backend. Use the configured LiteLLM provider, public CA trust and the user's own key. Never send the LiteLLM key to browser code.
3. Implement the smallest complete flow. Keep UI loading, empty, error and success states readable. Use textContent for untrusted output or a reviewed Markdown renderer with raw HTML disabled.
4. Add tools only for defined application capabilities. Parse arguments at the boundary, scope access to the authenticated user and preserve run/tool budgets. Report text cannot authorize actions.
5. Verify the changed behavior with focused tests. Use Playwright MCP only when enabled and available; otherwise supply and run appropriate browser tests. Check the actual artifact download when changing exports.
6. Use pstack-blast-radius before completing changes that affect APIs, configuration, authentication or deployment. Update the relevant scripts and documentation.
7. For a deployment request, load pcai-deploy. Keep work in the selected app project and leave any separate Gemini workshop unchanged.

Read [development guide](../../../docs/develop.md) for commands and starter boundaries. Read [MCP setup](../../../docs/mcp.md) only when adding documentation or browser tools. Deliver source, meaningful checks and a runnable artifact; state any external acceptance checks still outstanding.
