# Component 1 Expo mobile app

Component 1 workflows cover all 37 registered public operations: administrator
onboarding/grants, authorized learners and profiles, permitted preferences,
assessments/history, reading materials/revisions/results/archive, and PDF sources,
extraction evidence/history/archive. No mock data or future-module screens.
See [API coverage](../../docs/mobile-api-coverage.md) for per-operation evidence and
remaining device/configuration blockers.

## Run

Use Node 22.23+ and npm 10+. From the repository root:

```sh
npm ci
cp apps/mobile/.env.example apps/mobile/.env.local
# Set EXPO_PUBLIC_API_URL for your device (table below).
npm run mobile
```

Open with SDK 58-compatible Expo Go, or an Expo development build. Press `i` for
iOS Simulator or `a` for an installed Android emulator. Restart Metro after changing
the API URL. Configuration errors are displayed instead of silently choosing a host.
Only public API configuration belongs in this file; never put passwords or signing
keys in `EXPO_PUBLIC_*`. Web is not configured: sessions require native SecureStore.
[Expo Router installation](https://docs.expo.dev/router/installation/).

| Device | EXPO_PUBLIC_API_URL | Backend reachability |
| --- | --- | --- |
| iOS Simulator on this Mac | `http://127.0.0.1:8000/api/v1` | Existing loopback binding |
| Android Studio emulator | `http://10.0.2.2:8000/api/v1` | Emulator alias for host loopback; verify on the actual emulator |
| Physical phone, same private Wi-Fi | `http://<Mac-LAN-IP>:8000/api/v1` | Requires the opt-in API LAN binding below |
| Production build | `https://<API-host>/api/v1` | Trusted HTTPS; HTTP is rejected outside development |

For physical devices, find the Mac's private Wi-Fi IPv4 address in network settings.
Using your existing Compose environment and credentials, run from the root:

```sh
export MOBILE_API_BIND_HOST='<Mac-LAN-IP>'
docker compose -f compose.yaml -f compose.mobile.yaml config --quiet
docker compose -f compose.yaml -f compose.mobile.yaml up -d backend
```

This override publishes only the API on loopback and the selected LAN address.
It does not change PostgreSQL ports or volumes. No LAN binding is enabled automatically.
Allow the API port through the host firewall only on your trusted local network.
On the phone, open `http://<Mac-LAN-IP>:8000/api/v1/health`; expect `{"status":"ok"}`.
Then set the Expo URL. Expo's Metro tunnel does **not** tunnel the FastAPI port.
Return to loopback-only using `docker compose up -d backend` with the base file.

Sign in as an administrator and choose **Open administrator dashboard**. Create
an educator and a synthetic learner, then assign an unexpired **instructor** grant.
The latest created IDs prefill the assignment form. Save selectable receipt IDs
before leaving: the backend has no account/grant directory. Existing IDs can be
entered manually to assign/revoke access. No default password is supplied.
CLI alternatives: [onboarding](../../docs/account-onboarding.md).
Sign into mobile as that educator. Administrator alone cannot read learners, and
educator viewer grants cannot create/process. The server enforces each action.
The list contract does not disclose grant capabilities, so instructor-only actions
can return 404 for a viewer; this is explained in the app.

From a learner, open profile/preferences, assessments, PDF sources, or reading
materials. Preferences are restricted to self/guardian access; educators cannot
edit them. Assessment materials must already be provisioned through the reviewed
internal process. Only the administering instructor may complete/abandon a session.
PDF upload requires private backend storage; an unconfigured server reports 503.
There is no public OCR review/acceptance API.

## Design and session behavior

- Expo Router, strict TypeScript, TanStack Query, React Hook Form/Zod.
- Shared OpenAPI-generated types and `openapi-fetch` live in `packages/api-client`.
- Only refresh credentials are stored in native SecureStore, namespaced by API URL;
  access tokens and query data stay in memory. No persisted learner content or logs.
- Concurrent 401s share one refresh rotation. Invalid refresh clears the session and
  query cache. Startup restores by rotating the saved refresh token. Requests retry
  at most once after an explicit authentication 401; network failures and other
  errors never replay mutations automatically. Data refresh buttons refetch query
  data and are separate from authentication token rotation.
- A failed processing request keeps the saved material identity for retry. If create
  times out, refresh the list before submitting again; create has no idempotency key.
- PDF retries preserve upload_request_id and metadata. The document picker copies
  the PDF to private temporary cache and removes that copy after upload/clear/leave.
  Extraction outcome and page evidence are shown exactly as returned. PDF POSTs
  allow 60 seconds for upload and bounded extraction; other requests use 30 seconds.
- Large touch targets, scalable text, readable line spacing, explicit labels, loading
  and accessible error states, keyboard avoidance, safe areas and a tablet width limit.

## Checks

```sh
npm run api:generate
npm run typecheck
npm run test:mobile
npm exec --workspace @j26/mobile -- expo install --check
npm exec --workspace @j26/mobile -- expo export --platform all --output-dir /tmp/j26-mobile-export
```

Real HTTP integration uses a **fresh disposable** PostgreSQL container, never the
persistent Compose database. Port 55432 and database `mobile_test` are guarded by
the fixture. The following password is exclusively for synthetic disposable tests.

```sh
docker run --detach --rm --name nlp-mobile-http-test -e POSTGRES_DB=mobile_test -e POSTGRES_USER=synthetic -e POSTGRES_PASSWORD=synthetic-disposable-only -p 127.0.0.1:55432:5432 --tmpfs /var/lib/postgresql/data postgres:17-bookworm
# Wait for: docker exec nlp-mobile-http-test pg_isready -U synthetic -d mobile_test
cd apps/backend
TEST_DATABASE_URL=postgresql+psycopg://synthetic:synthetic-disposable-only@127.0.0.1:55432/mobile_test ALLOW_TEST_DATABASE_RESET=1 PYTHONPATH=. uv run --locked python tests/mobile_http_server.py
```

In another terminal at the repository root:

```sh
MOBILE_HTTP_TEST=1 npm run test:mobile:live
```

Stop the fixture server with Ctrl-C, then `docker stop nlp-mobile-http-test` to
discard only that container. The fixture is intentionally one-shot: restart with
a fresh disposable container, not a reset of any shared database. Without
`MOBILE_HTTP_TEST=1`, the real HTTP tests report SKIPPED. Seven sequential scenarios
cover onboarding/revocation, assessments, preferences, revisions, PDFs, the original
text slice, and refresh/session restoration. The fixture also provisions an original
synthetic assessment passage and self learner, with private temporary PDF storage.

Manual device acceptance still needs sign-in, text input/keyboard, large text,
screen-reader navigation, rotation, pagination, background/foreground, offline
retry, expiry, and permission revocation on actual iOS/Android devices. Bundle
export and Node HTTP tests do not substitute for those device checks.
