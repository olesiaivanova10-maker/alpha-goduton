# Shared demo proxy access

The shared demo uses HTTPS and HTTP Basic Auth at the outer nginx proxy. For this
specific team demo, the proxy may pass a separate `X-Demo-Proxy-Key` to the
backend. Set `DEMO_PROXY_KEY` to a random value of at least 32 characters in the
server-only `.env`. The backend maps that key to a non-administrative principal.
It still grants access to all demo companies, so use it only for synthetic or
team-approved data. It is not a replacement for per-user company scopes in a
production gateway.

The outer proxy must overwrite incoming `X-Demo-Proxy-Key`, `X-Admin-Key` and
`X-Auth-*` headers. It must send `X-Demo-Proxy-Key` only after Basic Auth succeeds
and must never send `X-Admin-Key` on ordinary user requests. Keep the backend
port bound to loopback. Restrict the nginx configuration and `.env` to root.

Administrative operations use `ADMIN_API_KEY` only from a separate internal
maintenance path. Rotate that key if it was ever injected into general traffic.
After a proxy change, verify that an unauthenticated HTTPS request is rejected,
an authenticated demo request can read an allowed profile, and an authenticated
demo request to `/api/developer` receives HTTP 403. Never print credentials in
diagnostic output or commit them to Git.
