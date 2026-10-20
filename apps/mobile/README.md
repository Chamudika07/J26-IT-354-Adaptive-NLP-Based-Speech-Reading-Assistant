# ReadBuddy mobile — Component 2

The current Expo/React Native screen supports text simplification, vocabulary
explanations, and the four reading-feedback signals through the shared FastAPI
backend under `/api/v1`. Contracts and transport live in `packages/api-client`.

From the repository root, run `pnpm typecheck`. From `apps/mobile`, run:

```sh
pnpm start
pnpm test
pnpm exec expo-doctor
```

`pnpm test` runs offline transport and App callback regression tests with synthetic
data and a lightweight hook harness. It does not render native controls or replace
device testing. For an offline bundle check without loading local dotenv files:

```sh
EXPO_NO_DOTENV=1 pnpm exec expo export --platform ios --platform android --output-dir /tmp/readbuddy-component2-export
```

Set only the public backend address in `EXPO_PUBLIC_API_BASE_URL` (see
`.env.example`). Physical devices need a reachable host address; localhost refers
to the device itself. Enter an authorized learner UUID and access token through
**Configure Session**. Enter both tokens returned by `/api/v1/auth/login`. The
short-lived access token stays in memory. The rotating refresh token, learner UUID,
and backend address are saved with Expo SecureStore so the app can renew access
after five minutes and after an app reload. Never put credentials in
`EXPO_PUBLIC_*` variables; those values enter the bundle. Clearing the session
removes the stored refresh session.

The shared API client refreshes only a `401 authentication_required` response,
coordinates concurrent requests behind one refresh, stores a rotated refresh token,
and retries the original Component 2 request once. If refresh or that retry fails,
the app clears the session and asks for sign-in again.

The disabled backend provider returns 503 for simplification and explanation.
Shared consent evaluation and an approved synthetic account/learner setup remain
dependencies for an authenticated demo. Do not enable Gemini or send learner data
to work around those dependencies. See the [integration audit](../../docs/component-2-integration-audit.md).
