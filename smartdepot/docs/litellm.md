# Connect the starter to LiteLLM

The app sends chat requests to LiteLLM from its backend. The browser never receives the API key.

## Expected settings

- VPN endpoint: `https://litellm.htp-ai-ai-application.awanheitech.local/v1`
- Default model alias: `deepseek-ai/deepseek-v4.1-flash`
- Key: each user supplies their own LiteLLM virtual key through **Setup App.cmd**. The prompt is hidden and the key is saved in the private `.local` folder.

The LiteLLM dashboard lists the DeepSeek alias above. Its model page says to create a virtual key without selecting a team to access these models. If an existing key is team-scoped, create a new key without a team or have the administrator allow the exact model on that key.

## Diagnose a failed request

1. Connect to the PCAI VPN.
2. Run **Setup App.cmd** and choose the numbered option for `deepseek-ai/deepseek-v4.1-flash` (usually option 1).
3. Paste a key that is allowed to use this model. The Windows prompt shows one `*` per pasted character; it never displays the key itself. Do not add `Bearer ` before the key.
4. Run **Run App.cmd** and send `Hello`.

After setup reports **SETUP COMPLETE**, run **Run App.cmd**. If the key is not saved yet, Run App starts the same setup flow automatically. The app gives a different message for access denial, a missing model route, and a network/TLS failure. Its server log records only the HTTP status and model alias. It does not log the key or LiteLLM response body.

| Result | Next step |
|---|---|
| HTTP 401/403 | Create a virtual key without selecting a team, or ask the administrator to allow the model. Re-enter the key through setup. |
| HTTP 404 / model not found | Confirm the VPN URL ends in `/v1`, the model alias matches exactly, and the key can use it. |
| Timeout or TLS error | Connect to VPN and check DNS, the PCAI CA certificate and endpoint reachability. |

Never share the key, copy it into a source file, or send authorization headers or unredacted request logs for troubleshooting.
