# Configure Keycloak for the app

This task belongs to the realm administrator. Use an existing PCAI Keycloak realm. The pack does not deploy Keycloak or reuse PCAI administrator credentials.

## Register the client

1. Create an **OpenID Connect** client with a unique client ID.
2. Turn **Client authentication** on and enable **Standard flow**.
3. Disable **Direct access grants**, implicit flow and service-account access unless your separate design requires them.
4. Set the exact valid redirect URI to `https://APP_HOSTNAME/oauth2/callback`, using the hostname collected by **Configure PCAI.cmd**. Do not use a wildcard callback.
5. Set the client home/root URL to the app origin and configure S256 PKCE support. The proxy sends an S256 challenge.
6. Copy the client secret into the hidden setup prompt. It is stored separately from chart values.

`APP_HOSTNAME` above describes the value the wizard prints; it is not text the attendee needs to replace in a configuration file.

## Include the required claims

In the client's dedicated scope, add an **Audience** mapper with the app's client ID as the included client audience. Include it in ID and access tokens. oauth2-proxy validates the audience against its configured client ID.

Add a **Group Membership** mapper named `groups`. Include it in ID/access tokens and UserInfo. Use full group paths consistently, such as `/pcai-workshop`, and supply the exact allowed group in setup. Add intended users to that group. Test a user outside the group as well.

Users need an email claim and a verified email address. The proxy does not disable email verification or issuer/audience validation. Keep token claims small: unnecessary roles/groups can make cookie sessions exceed browser cookie limits. For large claims, move session storage to a separately designed Redis-backed deployment rather than weakening checks.

## Supply the issuer and trust

Use the realm's HTTPS issuer from its discovery document, ending in `/realms/REALM`. The browser and proxy pod must both reach that issuer, and discovery must advertise the correct external endpoints. A portal hostname alone is not the issuer URL.

The proxy uses the bundled public PCAI CA in addition to system trust. If Keycloak uses a different private CA, an operator can set `auth.caConfigMap` to an existing ConfigMap in the project namespace with a `ca.crt` key containing the approved CA chain. Never supply a server private key or disable TLS verification.

## Understand the proxy boundary

This chart runs one application-owned oauth2-proxy with Keycloak OIDC, secure HTTP-only cookies and an allowed-group filter. The gateway routes all app paths to that proxy. The app trusts identity headers only because the app's NetworkPolicy restricts inbound access to those proxy pods.

HPE also documents integration with a **shared** authorization proxy through Istio `AuthorizationPolicy` with action `CUSTOM`. That is an alternative platform integration, not an extra policy this pack silently installs. The platform owner must decide how shared SSO, identity headers and this application-owned proxy interact. Avoid duplicate login layers and redirect loops.

Do not create a gateway-wide policy from an attendee account. If your PCAI installation requires shared-proxy integration, have the platform team adapt the route/auth boundary and repeat all acceptance tests. A shared proxy that only permits a request does not automatically guarantee the identity header this app expects.

References: [oauth2-proxy Keycloak OIDC](https://oauth2-proxy.github.io/oauth2-proxy/configuration/providers/keycloak_oidc/), [Keycloak administration](https://www.keycloak.org/docs/latest/server_admin/index.html), and [HPE imported-framework SSO](https://docs.ezmeral.hpe.com/unified-analytics/15/ManageClusters/sso-support-for-imported-apps.html).
