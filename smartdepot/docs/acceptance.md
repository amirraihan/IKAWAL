# Verify the app and PCAI deployment

Record the release, immutable image tag, date, operator and results in `artifacts/release-check.md`. Do not put credentials or full tokens in evidence.

## Local app

1. Run **Setup App.cmd**, choose the model by number, paste your key (watch for asterisks), and wait for **SETUP COMPLETE**. Then run **Run App.cmd** to start on 127.0.0.1. If setup has not been completed, Run App starts setup automatically.
2. Send **Hello**. Expect a real answer from the configured model.
3. With DeepSeek or Qwen2.5, ask for a comparison of the fictional reports. Expect successful report tools and citations to `[north]` and `[south]`. The tax/support assumptions differ and should be flagged.
4. Download the answer. Open the `.md` file and compare its contents with the visible answer.
5. Start a new chat. Expect the previous browser conversation to disappear.
6. Try an invalid key in an isolated test profile. Expect a useful access error without credential text or raw gateway response content.

## Platform login and access

1. Open the app URL in a private browser window. Expect Keycloak login; do not accept a public app page before login.
2. Sign in with a verified-email user in the configured allowed group. Expect the app to load and a real model reply.
3. Sign in with a valid realm user outside the allowed group. Expect access denied.
4. Sign out or clear only this app's session cookies. Expect authentication again. Keycloak SSO logout and application-cookie logout have separate behavior; define your production logout requirements explicitly.
5. Confirm the backend Service has no external route. With a platform-owned diagnostic pod outside the permitted source, verify that direct backend access is denied by the CNI. Do not disable NetworkPolicy to make this check pass.
6. Try a POST from an unrelated Origin through the authenticated app. Expect rejection. The app does not enable cross-origin API access.

## Model and rollout

Verify a real chat and report-tool roundtrip through the deployed URL. Pod readiness only confirms that a key is configured. Also verify the image digest/tag, logs without secrets, HTTP error display and download.

For a controlled upgrade, deploy a visible version change and repeat the login/chat path. Roll back with the platform-supported mechanism and verify the previous behavior. Separately track any Secret, Keycloak or data change that Helm cannot roll back.

## Diagnose common failures

| Symptom | Check |
|---|---|
| Local request times out | VPN, DNS, endpoint reachability and private CA trust. |
| `model not found` / HTTP 404 | Use the exact deployed alias `deepseek-ai/deepseek-v4.1-flash`, confirm the LiteLLM VPN URL ends in `/v1`, and create the virtual key without selecting a team (or allow this exact model on the key). Run **Setup App.cmd** again after changing the key. |
| HTTP 401 or 403 | Confirm the key is current and allowed to use the selected model. Create the virtual key without selecting a team, or ask the LiteLLM administrator to add the model to its allowlist. Re-enter it through **Setup App.cmd**; never paste it into a ticket or chat. |
| ImagePullBackOff | Registry access, image tag and namespace image-pull Secret. |
| Proxy CrashLoopBackOff | Issuer discovery, CA chain, client/cookie Secret keys and cookie-key length. |
| Redirect loop | Public callback scheme/host, forwarded headers, cookie policy and duplicate shared/app auth. |
| Audience validation failure | Client audience mapper in ID/access tokens. |
| Allowed user receives 403 | Email verification, group mapper, exact full-path group claim and membership. |
| Gateway returns 503 | VirtualService destination, port 4180, ready proxy pods and enforced NetworkPolicy selectors. |
| App returns 401 after login | Proxy must supply X-Forwarded-User. Do not expose the backend or fabricate headers as a fix. |
| Tool loop fails | Use DeepSeek or Qwen2.5; inspect tool schema compatibility without exposing raw credentials. |

No deployment is accepted solely because Helm lint, template rendering, a health endpoint or a model inventory request succeeds.
