# Deploy through the PCAI import workflow

Use the PCAI project assigned by the platform team. This procedure creates an app release and two app-scoped Secrets. It does not create namespaces, registry accounts, Keycloak clients, shared gateway policies or DNS/TLS resources.

## Collect platform values

Ask the platform owner for the authorized kubectl context, project namespace, image repository, image-pull Secret if needed, app hostname, gateway and Keycloak issuer/client/group. The app hostname must resolve to the PCAI gateway and be covered by its TLS certificate.

The default namespace comes from the observed portal selection, `project-genai-platform`. Confirm it for each team. The default Istio gateway, `istio-system/ezaf-gateway`, follows HPE's published example and still requires confirmation on the target installation.

Local app requests use the VPN HTTPS LiteLLM URL. Pod requests default to `http://litellm.litellm.svc.cluster.local:4000/v1`, provided by the environment owner. Use the HTTPS endpoint instead if cluster policy requires encrypted service-to-service traffic. The app's key must allow the selected chat model.

## Prepare the release

1. Run **Configure PCAI.cmd**. Enter the values supplied by IT. The prompts collect credentials with hidden input and print the exact Keycloak callback URL.
2. Have the realm administrator complete [Keycloak configuration](keycloak.md).
3. Log in to the approved registry with Docker or your organization's credential helper. Run **Build Image.cmd** and push when prompted. Use a new immutable tag for each build; do not replace an already deployed tag.
4. Run **Prepare PCAI Secrets.cmd**. Verify the displayed context/namespace before applying. The namespace must already exist, and your account needs Secret permissions there.
5. Run **Prepare PCAI Import.cmd**. It renders manifests and writes `.local/pcai-app-0.1.0.tgz`. The chart has filled non-secret settings and references the two existing Secrets.

The cookie secret is generated once and kept on reruns. The LiteLLM key, OIDC client secret and cookie secret are never chart values or command-line arguments. Kubernetes Secret storage still depends on the platform's RBAC and encryption-at-rest settings.

For an offline or restricted registry, mirror the app base image and oauth2-proxy image through approved channels. The pinned default proxy image is `quay.io/oauth2-proxy/oauth2-proxy:v7.15.6`. An operator can change its repository/tag in the generated non-secret values when a mirror is required. The Docker build downloads locked Python packages; prepare an approved package mirror/wheelhouse for disconnected builds.

## Import in the portal

1. Open [Import Framework](https://home.htp-ai-ai-application.awanheitech.local/frameworks/import).
2. Select **assets/app-icon.png** as the icon.
3. Select **Upload New Chart** and upload `.local/pcai-app-0.1.0.tgz`.
4. Select the same project/namespace where you prepared the Secrets.
5. Continue through **Edit Chart**, **Review Config**, then **Review and Deploy**. Check the image, hostname, auth issuer/client/group and Secret references before deploying.
6. Open the new app URL and complete [acceptance checks](acceptance.md).

These step names were read from the live import screen on 23 November 2026. Importing and deployment have not been performed during pack preparation.

HPE's import documentation uses Helm archives and an Istio VirtualService. The chart adds the documented `hpe-ezua/type: vendor-service` label directly to its pod templates. It does not create the example cluster-wide Kyverno mutation policy; ask the platform team whether the installed import mechanism requires additional admission integration.

## Use Helm directly instead

Run **Deploy PCAI.cmd** only for a release managed through the CLI. It uses the configured context/namespace and Helm 3 `upgrade --install --atomic --wait`. It renders first and shows the target before making changes.

Do not mix UI and CLI ownership for the same release. To inspect a CLI release, use the platform-assigned context and namespace with `helm status`, `kubectl get pods` and `kubectl logs`. Do not paste full Secret output into support chats.

## Route and isolate the app

The default `routing.mode=istio` creates a VirtualService to the auth service on port 4180. The gateway owns HTTPS certificates. `routing.mode=ingress` instead creates an Ingress using an existing TLS Secret; configure the controller namespace and its request timeout.

NetworkPolicy allows gateway-namespace traffic to auth pods and auth-pod traffic to app pods. Egress remains governed by the platform; this starter does not add an egress allowlist. Confirm the installed CNI enforces ingress policies and supports this gateway traffic path. If traffic is blocked, adapt selectors with the platform owner instead of exposing the backend.

Pod templates disable sidecar injection and use restricted container settings. Clusters with mandatory sidecars, strict mesh mTLS, custom UID restrictions or service-specific admission policies need an operator-reviewed profile before deployment. This pack does not alter those platform controls.

## Upgrade and roll back

Build and push a new immutable image tag, rerun configuration and regenerate the import chart. Use the portal's supported update workflow for UI-managed releases. For a CLI-managed release, inspect `helm history` and use `helm rollback RELEASE REVISION --kube-context CONTEXT --namespace NAMESPACE --wait` with your actual target values.

Helm rollback does not restore separately managed Secret values, external Keycloak client settings or application data. Keep the cookie secret stable unless rotation is intended; after rotation, users must sign in again. Readiness checks key presence, not upstream model authorization, so always test a real answer after an upgrade.

Reference: [HPE importing frameworks](https://docs.ezmeral.hpe.com/unified-analytics/15/ManageClusters/importing-applications.html).
