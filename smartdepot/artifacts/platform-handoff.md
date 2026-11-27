# PCAI platform handoff

Give these values to the team running Configure PCAI.cmd. No API key or client secret belongs in this document.

| Item | Confirmed value / owner |
|---|---|
| PCAI project and namespace | |
| Authorized kubectl context and operator | |
| App image repository / immutable tag | |
| Existing image-pull Secret, if needed | |
| App hostname / DNS owner | |
| HTTPS gateway certificate covers this hostname | |
| Istio gateway or ingress class | |
| Gateway/controller namespace | |
| Keycloak issuer URL and client ID | |
| Exact callback URL | |
| Audience mapper and groups mapper configured | |
| Allowed group and allowed/denied test users | |
| Keycloak private CA ConfigMap, if different | |
| App-scoped LiteLLM key owner, models and budget | |
| CNI NetworkPolicy enforcement confirmed | |
| Mandatory mesh/admission policies reviewed | |
| UI-managed or CLI-managed release owner | |

Observed during preparation: the portal import screen showed `project-genai-platform`. This is a starting value, not a grant of deployment permission. The Keycloak issuer, client, image registry and app hostname still come from the platform owner.
