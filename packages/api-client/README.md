# Shared generated API contract

`openapi.json` is the audited source/live FastAPI snapshot (37 operations).
`src/schema.ts` is generated, never hand-edited. `src/index.ts` supplies the typed
`openapi-fetch` factory and sanitized errors; it contains no backend logic.

After an intentional backend contract change, from the repository root:

```sh
curl --fail --silent --show-error http://127.0.0.1:8000/openapi.json -o packages/api-client/openapi.json
npm run api:generate
npm run typecheck
```

Review the snapshot diff and update `docs/mobile-api-coverage.md` rather than
rescanning the repository. API client base URLs may end in `/api/v1`; that suffix
is normalized because generated operation paths already include it.

UI Zod schemas validate form input only. Request/response types come from the
generated `components` and `paths` types. Backend authorization is authoritative.
