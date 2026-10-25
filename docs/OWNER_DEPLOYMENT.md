# Railway owner-only deployment

This is a separate opt-in deployment entrypoint. Existing `streamlit_app.py`,
`app.py`, pages and local-profile behavior are unchanged. **Do not expose those
legacy entrypoints publicly as a substitute for this gate.** `owner_server.py`
is always gated: missing/malformed configuration fails closed, not open.

## Deployment prerequisites

- One process, one replica, HTTPS at the hosting edge, private until verified.
- Install `requirements-owner.txt` (includes base requirements and exact
  `streamlit==1.66.1`). This uses the documented `st.App` ASGI middleware extension,
  not a monkey-patch. Earlier Streamlit docs labelled the API experimental;
  upgrades require fresh transport-security review. The entrypoint rejects any
  different Streamlit version rather than silently running unprotected.
- Start from repository root with:

  ```sh
  python -m streamlit run owner_server.py --server.address=0.0.0.0 --server.port="$PORT"
  ```

- Railway health path: `/_owner/health`. It returns only `ok` when auth config is
  valid, otherwise `unavailable`/503. No application page/provider/data operation
  is invoked by this endpoint. Other Streamlit health routes remain protected.
- Persistent application data: fresh `/app/data` volume, not an inherited service
  volume. Owner sessions are deliberately memory-only and do not persist there.
- Keep provider credentials absent/blank. This change does not authorize or
  enable paid API calls or PR #215.

## Required host secret configuration

Set these through the host's secure secret controls; never commit values:

| Variable | Required format |
| --- | --- |
| `ABA_OWNER_USERNAME` | 1–128 ASCII letters/digits or `_.@-`; owner only |
| `ABA_OWNER_PASSWORD_HASH` | `pbkdf2_sha256$600000$<32 lowercase hex salt>$<64 lowercase hex digest>` |
| `ABA_OWNER_ORIGIN` | Exact public HTTPS origin, e.g. `https://your-host.example`; no trailing slash/path/query/userinfo |

The actual deployment origin and owner credentials are **not** supplied by this
repository or test fixtures. Test credentials are clearly synthetic and must
never be deployed. The origin must be set to the final approved hostname; no
forwarded-host/proto/user headers are trusted. If the hosting proxy does not
preserve that Host, requests fail closed and deployment must be corrected—not
worked around by trusting arbitrary forwarding headers.

Use a unique password-manager-generated password of at least 20 characters
(minimum accepted length 16). Produce its hash locally with a trusted Python
interpreter and `getpass`, a fresh `secrets.token_bytes(16)` salt, and
`hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 600000)`. Transfer only the
formatted hash into the host secret variable. Do not put a password in a shell
argument/history, tool transcript, URL, repo, CSV or log. Credential creation and
secure transfer require the owner/operator; no production credential is generated
by the validation scripts.

## Login, logout and rotation

Open `/_owner/login`. The form uses an expiring, one-use HMAC-signed nonce and exact Origin
validation. GET challenges allocate no per-request server state; anonymous GET
floods cannot evict another browser's pending login form. Only admitted POST
challenge digests are retained for replay prevention, with an explicit bounded
cap and expiry pruning (never eviction of still-valid consumed challenges). Login produces a random 256-bit server-side session identifier in a
`__Host-` cookie with Secure, HttpOnly, SameSite=Strict and Path=/ attributes.
Sessions expire after one hour, with at most eight sessions per process.
There are no client/demo roles or default passwords.

To sign out, open `/_owner/logout` and submit the confirmation form. Logout is
POST-only with a session-bound CSRF token; visiting the page alone does not log
out. The server removes that session and closes its open WebSockets. Other owner
sessions remain independent. Browser refresh/reconnect cannot restore a revoked
session. Restart revokes all sessions. Changing username, hash or origin revokes
all old sessions when configuration is observed; host-variable changes normally
require a deployment/restart. Rotating environment values without actually
updating/restarting the process does not rotate the running configuration.

## Protection boundary

The ASGI middleware runs before all Streamlit handlers: direct/legacy pages,
static assets, media/downloads, uploads, components and WebSocket handshake.
Unauthenticated requests do not reach those handlers. Protected HTTP responses
are no-store. Authentication is rechecked before forwarding incoming/outgoing
WebSocket messages; a 250ms watcher also closes idle revoked/expired sockets.
HTTP request/response forwarding is checked too. Already authorized operations
that began before revocation cannot be undone. Downloaded files/screenshots and
bytes already sent to a browser cannot be erased by logout.

Only the minimal health endpoint and the login UI are unauthenticated. Login and
logout bodies are limited to 4KiB, 64 chunks and a five-second total read budget.
There is no redirect destination supplied by the client; successful login goes
to `/`, logout to the fixed login path. No OAuth scopes or external identity
services are introduced. CORS/XSRF protections are not disabled.

## Availability limitation — explicit deployment decision required

The single-process login throttle permits at most five password attempts per
minute globally. This bounds password-hash CPU use and prevents reconnecting from
bypassing the throttle, without guessing a trusted proxy/IP chain. **Anonymous
traffic can consume this budget and prevent the rightful owner from signing in.**
The stateless signed CSRF design prevents a separate trivial GET-based challenge
eviction attack, but does not remove the password-attempt availability tradeoff.
This is denial of service, not unauthorized access. Do not call the deployment
fully abuse-resistant. Before public exposure, the operator must explicitly
accept this limitation or provide a reviewed trusted edge access/rate control.
Do not weaken the throttle or trust spoofable forwarding headers as a shortcut.
There is no credential recovery/reset endpoint.

## Verification and release gates

Local tests use synthetic secrets and deny external networking. They cover
missing/malformed config, wrong credentials, exact origin/CSRF, duplicate headers,
body/session/nonce/rate limits, all-path denial, expiry/rotation/logout, session
isolation, outgoing data revocation, restart and actual HTTP/WebSocket/download
transport. Local transport tests simulate the HTTPS edge over loopback; deployed
TLS, Secure-cookie behavior, hostname/proxy forwarding and origin must be checked
separately. Local HTTP health alone is not UI/security qualification.

Existing runtime startup hooks may initialize a default local profile before
serving requests. Tests distinguish that startup initialization from additional
unauthenticated request-triggered changes. It is not an authenticated account.
The app's legacy local profile selectors are not this access boundary.

Retain private deployment until independent review, full regression tests, fresh
on-host auth/media/WebSocket tests, origin/credential setup and the explicit
availability decision are complete. Do not use this gate to claim other service
URLs or the original Streamlit Cloud deployment have become authenticated.

References:
- https://docs.streamlit.io/1.65.0/develop/api-reference/server/st.app
- https://starlette.dev/middleware/
