# Component 2 API client

The current package contains handwritten TypeScript contracts and fetch transport
for simplification, vocabulary explanation, and reading feedback. It is not an
OpenAPI-generated client. Backend Pydantic schemas remain authoritative; decimal
response scores are JSON strings.

Use `createSimplificationClient` with a backend base URL and a runtime token
provider. All endpoints use `/api/v1`; learner IDs belong in URL paths. Vocabulary
requests optionally carry a simplification session ID, and feedback uses that
session ID in its URL. This ID is distinct from the authentication session ID.

Applications may provide `refreshAccessToken` and `onAuthenticationFailure`. The
client invokes refresh only for the backend's `401 authentication_required` error,
shares one in-flight refresh across concurrent requests, and retries each rejected
request once. Token persistence and the `/auth/refresh` request remain application
responsibilities so this transport package never stores credentials.

From the repository root, run `pnpm typecheck:api-client`. Offline transport
regressions run with `pnpm --filter @readbuddy/mobile test`.
Keep credentials, business logic, and database access out of this package.
OpenAPI generation remains follow-up work to prevent contract drift.
