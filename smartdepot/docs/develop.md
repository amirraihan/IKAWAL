# Develop an app with this pack

Start with a visible user outcome: a document comparison, a ticket triage screen, a report generator or another small flow. Define what the user enters, what they see, what the app saves and what counts as success.

## Use the skills

Open the HPE-PCAI folder in OpenCode and use these prompts:

- “Use pstack-how to explain how a message reaches LiteLLM and how the report tools run.”
- “Use agentic-app-dev to add a report filter and verify the browser flow.”
- “Use pstack-architect to design persistent conversations per signed-in user before adding a database.”
- “Use pstack-blast-radius to review this authentication change.”
- “Use pcai-deploy to prepare this app for the PCAI import wizard.”

Skills guide work; they do not supply external tools or automatically run inside the app's model loop. `AGENTS.md` supplies repository instructions. The MCP servers extend OpenCode, not the deployed app.

## Run commands

Windows users can use the CMD launchers. From any supported shell:

```text
python launcher.py setup
python launcher.py run
python launcher.py doctor
```

For development checks, create a separate Python environment or use the existing one:

```text
python -m pip install -r requirements-dev.txt
python -m pytest tests
python scripts/validate.py --helm helm
```

`validate.py` checks the app, skills, public certificate, OpenCode configuration and both Helm routing modes. It also verifies that the chart rejects credentials in values and routes only through authentication. It does not contact the cluster or model service.

## Follow the code

| File | Responsibility |
|---|---|
| `app/main.py` | HTTP boundaries, request size, identity headers, origin checks, settings and TLS trust. |
| `app/agent.py` | LiteLLM request, message history and bounded read-only report and UC-2 case tools. |
| `app/reman.py` | UC-2 rule engine: countdown, risk score, label, recommended action, name masking (no I/O). |
| `app/store.py` | Locate the reman register and build scored cases, cached by file mtime. |
| `app/xlsx.py` | Standard-library, read-only `.xlsx` reader plus a small `.xlsx` writer for exports. |
| `app/pdf.py` | Standard-library PDF table writer (base-14 Helvetica) for the worklist export. |
| `app/static/` | Browser messages, the UC-2 priority worklist, loading/errors and Markdown export. No build tool required. |
| `scripts/workshop.py` | Setup wizard, private settings, image build, Secret creation and chart preparation. |
| `deploy/chart/` | Resources, auth proxy, route and pod network boundaries. |

The model sees at most four recent browser messages by default. The server accepts at most eight. Messages sent by the browser can only have user or assistant roles. The backend supplies its own system instructions and tool definitions.

The response is shown after the bounded model loop finishes; this starter does not stream tokens. DeepSeek and Qwen2.5 get report tools. GPT OSS and Llama use ordinary chat because earlier gateway checks found their streamed tool descriptions incompatible with coding-tool use.

## Extend deliberately

- For a new tool, give it a narrow schema and a real implementation. Test invalid input and access to another user's records before adding persisted user data.
- For uploads, define size/type limits, parsing and user ownership. Do not treat document text as instructions.
- For persistence, use a database and object store with an authenticated subject key. Do not use preferred username as a stable identity key.
- For a React frontend, add a separate build stage and preserve same-origin API routing. The current static UI keeps the initial setup small.
- For streaming, add a documented event contract and check ingress/proxy timeouts, disconnects and cancellation.
- For Qwen image generation or embeddings, add separate APIs and tests. This pack configures chat only; image and embedding aliases are not chat models.

Use `artifacts/feature-brief.md`, `architecture-decision.md` and `release-check.md` as working artifacts. Keep them proportional to the feature.
