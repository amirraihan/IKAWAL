---
name: pcai-deploy
description: "Prepare, import, deploy, diagnose and roll back this app on HPE PCAI using Helm, Istio or Ingress, Keycloak OIDC and Kubernetes Secrets."
---

# Pcai deploy

Work in the selected app project; installed plugin files are reusable references. Read [deployment guide](../../../docs/deploy.md), [Keycloak setup](../../../docs/keycloak.md) and the chart before changing platform artifacts.

- Confirm the target context, project namespace, image repository/tag, app hostname, gateway or ingress class, Keycloak issuer/client/group, and image-pull access. Collect values through Configure PCAI.cmd; do not require users to replace text in files.
- Use Prepare PCAI Import.cmd to render and package a chart for the HPE Import Framework workflow. Import requires the icon and the chart. Existing Secrets must be provisioned in the SAME namespace before the release starts.
- Use Build Image.cmd for a Linux amd64 image. Only push when requested. For restricted environments, use approved mirrored base images and oauth2-proxy images.
- Route HTTPS traffic to oauth2-proxy, then to the private app service. Keep the allowed-group check, audience mapper, exact callback, secure cookies, TLS verification and enforced NetworkPolicy. Do not bypass login to fix a deployment error.
- The chart uses application-owned oauth2-proxy. PCAI can also use a shared authorization proxy; do not add a gateway AuthorizationPolicy or a second auth layer without checking the platform owner's integration model. No shared gateway or Keycloak resource is automatically changed by this pack.
- Run chart validation and inspect the rendered route/Secret references. Lint does not prove CRD support or cluster compatibility. Use server-side dry-run when the user has authorized cluster checks.
- Deploy only to the explicitly authorized target. After rollout, exercise unauthenticated redirect, allowed and denied groups, a real LiteLLM reply, tool use and Markdown download. Use [acceptance checks](../../../docs/acceptance.md).
- Record the release/image version and evidence. Helm rollback restores Helm resources, not separately updated Secrets or the Keycloak client. Reconcile those deliberately.

Preserve the generated cookie secret on reruns. Keep keys out of chart values, archives, shell arguments and logs. Separate prepared artifacts, local test evidence and a live accepted deployment in the report.
