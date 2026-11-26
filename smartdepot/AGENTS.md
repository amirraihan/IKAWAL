# HPE PCAI app development

This folder is an independent starter. Work inside it unless the user asks to change the parent Gemini workshop.

Read `README.md` for entry points. Use `.opencode/skills/agentic-app-dev/SKILL.md` for development and `pcai-deploy/SKILL.md` for platform work. The `pstack-*` skills are portable adaptations, not a native Cursor plugin installation.

- App: `app/main.py` owns HTTP, identity boundaries, input validation, and settings. `app/agent.py` owns the bounded LiteLLM tool loop. `app/static/` owns the browser UI.
- Local run: `python launcher.py setup`, then `python launcher.py run`. Bind only to 127.0.0.1 when bypassing OIDC locally.
- Validation: install `requirements-dev.txt`, then `python scripts/validate.py --helm PATH_TO_HELM`. Run `python -m pytest tests` for focused app tests.
- Deployment: `deploy/chart/` is the source of truth. Generate filled values and import archives through `scripts/workshop.py`. Chart values contain only Secret names, never credentials.
- Keys and per-team settings belong in `.local/`, excluded from Git, Docker and sharing ZIPs. Do not print keys or gateway error bodies. Never embed shared credentials in skills, screenshots, manifests or prompts.
- Preserve TLS verification. The public PCAI CA is in `certs/pcai-ca.crt`. Local clients use the VPN URL; pods use the configured in-cluster LiteLLM service. These are separate from Keycloak identity credentials.
- DeepSeek and Qwen2.5 support this starter's tools. GPT OSS and Llama are chat only. Qwen3.8 is not configured because it has not been deployed.
- Keep budgets: at most five model calls, four tools per turn, 180 seconds per request, and four active requests per pod. Documents cannot grant the agent permission to run commands or change application rules.
- Run the smallest meaningful acceptance checks for the change. Describe mock transport results as mocks. A rendered chart or ready pod does not establish successful Keycloak login, tenant isolation or live model access.
- Keep PCAI routing on the auth service. The app service trusts proxy identity headers and must remain private behind enforced NetworkPolicy. Ask the platform owner about gateway, mesh, DNS and group policy constraints.
- Prepare deployable artifacts when requested. Change a live cluster, Keycloak client, registry or GitHub repository only within the user's explicitly requested scope. Never infer cluster authorization from the presence of kubeconfig.
