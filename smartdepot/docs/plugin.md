# Use the PCAI OpenCode plugin

This is a native **server plugin** for OpenCode v2.3.2+. Its ID is `pcai`, its package name is `opencode-pcai`, and its version is `0.1.2`. It registers commands, tools and skills. It does not add a separate desktop panel or deploy software on load.

## Install and update

On Windows, extract the ZIP and run **Install PCAI Plugin.cmd**. Python 3.11+ is the only installer dependency. It installs under `%USERPROFILE%\.config\opencode\plugins\pcai`, or the matching `XDG_CONFIG_HOME` location if configured.

The installer uses OpenCode's global plugin discovery layout. It does not edit your provider configuration, read your LiteLLM key or copy `.local` settings. It replaces only a directory bearing this pack's installation marker; an unrelated existing directory is preserved. Fully quit and reopen OpenCode PCAI after installation or update.

For a CLI check, `opencode api plugin.list` reports plugin state, and `opencode api command.list` reports registered commands. OpenCode reconciles plugins during startup, so allow that startup to complete. `/pcai-help` is the user-facing check in an open project.

## Understand the commands

Commands submit a workflow instruction into the current session. They preserve attached files and the requested queue/steer delivery mode.

- `/pcai-start` uses the app-dev skill and scaffold tool to create a new app folder.
- `/pcai-build` guides implementation and verification in the selected project.
- `/pcai-review` checks effects beyond the immediate diff.
- `/pcai-deploy` prepares deployment artifacts and explains target prerequisites.
- `/pcai-check` diagnoses LiteLLM model access and distinguishes local evidence from real platform acceptance.
- `/pcai-help` explains the pack and first steps.

A command starts a conversation workflow. It does not silently apply Kubernetes manifests, change Keycloak, publish an image or bypass normal OpenCode permissions.

## Understand the tools

| Tool | Behavior |
|---|---|
| `pcai_status` | Reports plugin version, workspace and presence of setup/deployment files. It never returns their credential contents or calls the cluster. |
| `pcai_guide` | Reads one of seven bundled guides from an allowlisted topic, including LiteLLM setup and troubleshooting. |
| `pcai_scaffold` | Creates a new child folder in the current workspace after an edit-permission check. It verifies bundled source hashes and refuses an existing folder. |

The plugin has no shell-execution tool. Development agents can still use OpenCode's normal tools according to the user's permissions. The app-dev and deploy skills point them to the provided scripts and acceptance checks.

## Reuse the starter

`/pcai-start team-app` creates a complete source folder with local setup commands, app code, project instructions, pstack adaptations, guides, a Dockerfile and the Helm chart. It excludes credentials, kubeconfig, virtual environments, caches and generated deployment state.

The scaffold starts with fictional reports and a bounded LiteLLM tool loop. Persistent conversations, uploads, databases and object storage are further app features, not capabilities this starter claims to have implemented.

## Compatibility and evidence

The entry point exports the native v2 structural plugin definition used by `Plugin.define`. It uses Node filesystem APIs available in the OpenCode host, with no external npm dependencies. It intentionally does not use the v1 plugin API.

The plugin was installed into an isolated profile and reported **active** in the real OpenCode v2.3.2 runtime. Six commands and seven skills were read back from that runtime. Node tests exercise the tools, command forwarding, source scaffolding, existing-folder refusal and denied permissions. Windows execution remains a separate acceptance check.

References: [OpenCode plugins](https://opencode.ai/docs/plugins/), [v2 server plugin API](https://opencode.ai/docs/build/plugins/server).
