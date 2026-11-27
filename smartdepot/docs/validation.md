# Validation record

Prepared on 23 November 2026. This record separates local evidence from platform acceptance.

Patch 0.1.1 adds LiteLLM key-scope guidance and targeted access/model-route errors. Patch 0.1.2 changes the Windows setup to a numbered model chooser, masked key entry and a clearer completion/error message. The updated plugin was installed and active in the local OpenCode v2.3.2 service; the changed `/pcai-check` description is registered. The refreshed ZIP integrity and Drive checksum were verified. A live starter chat and Windows console run remain unverified: this preparation workspace has no private app key configured, cannot resolve the VPN-only gateway from its shell, and is not running Windows.

| Check | Result |
|---|---|
| Python app and setup/package tests | 14 passed on macOS with Python 3.13.7. Model HTTP responses were mocked; no live model call is claimed for this starter. |
| Tool protocol | Tested an assistant tool call, document result, reasoning field preservation and final answer. Also tested bounded looping and unknown/document-path rejection. |
| Identity/error boundaries | Tested missing proxy identity, wrong Origin, oversized requests, injected system-role history, missing key and redacted gateway errors. |
| Setup and sharing | Tested repeated configuration preserving the cookie secret, credentials excluded from values, working-state exclusion and accidental-key detection. |
| Windows dependency resolution | Universal hashed lock resolves all 16 runtime packages with binary wheels for Windows x64 / Python 3.11. This is dependency resolution, not Windows execution. |
| Skills | All seven passed the skill-creator frontmatter/name validator and local-reference checks. |
| Native OpenCode plugin | Installed through the supplied installer into an isolated profile. OpenCode v2.3.2 reported `pcai` active and returned all six commands and seven skills. Global auto-discovery worked without editing a provider/configuration file. |
| Plugin behavior | Six Node tests passed for registration, command forwarding, guides/status, real source scaffolding, denied permissions, existing-folder preservation and unsupported-version rejection. |
| HTML slides | The self-contained 14-slide deck was opened in the browser. Checked navigation, overview, notes, layout bounds and representative cover/installation/auth layouts. No browser warnings or errors were reported. |
| OpenCode configuration | Passed the current official OpenCode v2 JSON schema. MCP entries are supplied disabled; external MCP connections were not exercised. |
| Helm | Helm 3.19.2 strict lint passed with explicit validation values. Istio and Ingress profiles rendered and passed route, Secret-reference, group-policy and network-boundary assertions. |
| Import archive | The actual prepare-import command generated a readable `.tgz` with filled validation values and rendered manifests in a temporary directory. No cluster call was made. |
| OIDC proxy | Every rendered CLI flag was checked against the official oauth2-proxy v7.15.6 binary. Keycloak login was not exercised. |
| Public CA | Certificate bytes match SHA256 `431955c40fbb33012ff7fe8babab41ffc60807531b7de68486f2621f62234e5e`; only the public CA is supplied. |
| Portal inspection | Read the live Import Framework screen: icon, Helm archive, project namespace and the four wizard step names. No upload or deployment was submitted. |

The test run emits a Starlette deprecation notice about its httpx test-client adapter; the assertions pass. Runtime transport is httpx 0.28.1 and is independent of that test adapter.

## Required acceptance on the target environment

- Windows double-click setup and browser workflow.
- Docker image build, registry push/pull and target CPU architecture.
- PCAI chart import, installed CRDs/admission policy, gateway/DNS/TLS and NetworkPolicy enforcement.
- Keycloak discovery, exact redirect, audience/group claims, allowed user and denied user.
- Real LiteLLM answer, tool roundtrip and Markdown download through the deployed URL.
- Upgrade and rollback with a record of Secrets and identity changes outside Helm.

Docker was installed on the preparation machine, but its daemon was not running. No container build or live PCAI deployment is claimed. Use `docs/acceptance.md` and `artifacts/release-check.md` to record those results.

The parent Gemini workshop and previously published GitHub files were left separate. This pack adds the HPE-PCAI folder locally; no GitHub push is part of this preparation.
