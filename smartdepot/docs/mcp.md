# Enable optional MCP tools in OpenCode

The project includes two MCP entries in `opencode.json`, both disabled initially. Skills work without them. MCP servers add tools to the coding assistant; they are not deployed with the application.

## Playwright for browser checks

Install an approved Node.js LTS release. Playwright MCP is pinned to `@playwright/mcp@0.0.86`. The configured Windows command uses `cmd.exe /d /c npx -y @playwright/mcp@0.0.86 --isolated`; it downloads that package when first started and uses a separate browser session.

Double-click **Enable Workshop Tools.cmd**, choose Playwright, then reopen the project in OpenCode. The command selects the Windows invocation automatically. Check `/mcps` or `opencode mcp list`, then ask OpenCode to test the local app. If a browser is not installed, use the server's browser installation tool or have IT install an approved supported browser.

Keep the browser automation on workshop pages and fictional data. Verify Send, error display, New chat and the downloaded Markdown file when changing those features. A screenshot alone does not establish the file's contents.

If Windows cannot start `npx`, ask the coding assistant to resolve the installed `npx.cmd` location or use OpenCode's documented Windows command invocation. Do not copy macOS paths into Windows configuration.

## Context7 for library documentation

Run **Enable Workshop Tools.cmd** and choose Context7 when you want external documentation access. The configured remote endpoint is `https://mcp.context7.com/mcp`.

If OpenCode shows **needs authentication**, open `/mcps`, select Context7 and complete the service's login flow. Each user uses their own account or credential where required. Public external access, service limits and corporate egress policies still apply; a LiteLLM key is not a Context7 credential.

Use it to retrieve framework/library documentation. Do not send confidential prompts or source to an external service unless your organization permits it. The core app and local skill workflows do not depend on this service.

## GitHub and Kubernetes

GitHub MCP is optional for teams working with issues and pull requests. Configure it separately with each user's own authorized account. Local Git commands are sufficient for the first workshop exercise.

This starter does not enable a Kubernetes MCP server. The deploy skill uses Helm and kubectl with an explicit context and namespace. This keeps the first pack small and lets the platform team control credentials and write permissions. A later read-only cluster diagnostics MCP can be added when the access model is defined.

References: [OpenCode v2 MCP configuration](https://opencode.ai/docs/mcp-servers/), [Microsoft Playwright MCP](https://github.com/microsoft/playwright-mcp), [Context7](https://github.com/upstash/context7), [GitHub MCP](https://github.com/github/github-mcp-server).
