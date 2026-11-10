# Backend presentation demo

## Start before presenting

Open Docker Desktop. From the repository root, run:

```sh
docker compose up -d --wait
docker compose exec backend alembic upgrade head
docker compose ps
```

These commands use the existing local configuration. Keep `.env` and credentials
off the presentation screen. If backend code changes, rebuild with
`docker compose up --build -d --wait` first.

Open <http://127.0.0.1:8000/docs> on this laptop and share that browser window.
This is an interactive API demonstration; the mobile app is still a placeholder.

## Five-minute walkthrough (no account required)

1. Introduce the system: “I implemented a shared FastAPI backend connected to
   PostgreSQL. The API is organized into modules under `/api/v1`, with explicit
   database migrations.”
2. Expand `GET /api/v1/health`. Click **Try it out**, then **Execute**.
   Show HTTP 200 and `{"status":"ok"}`. Explain that the API is running.
3. Execute `GET /api/v1/health/ready`. Show HTTP 200 and
   `{"status":"ready"}`. Explain that PostgreSQL accepts a query. This check
   verifies database connectivity, not every feature or migration.
4. Execute `GET /api/v1/learners` without authorization. Show HTTP 401 and
   `authentication_required`. Explain that learner information requires login;
   authenticated requests also undergo learner-level authorization.
5. Scroll through the auth, learners, reading-assessments, reading-materials,
   and reading-material-pdf endpoint groups. Open request/response schemas to
   explain the implemented API contracts. Distinguish this overview from a
   successful authenticated workflow demonstration.
6. In a terminal, run `docker compose ps` to show the two healthy services and
   `docker compose exec backend alembic current` to show the migration revision.

Closing statement: “This demonstrates the running backend, database connection,
API documentation, and authentication protection. The next integration step is
connecting the client interface to these APIs.”

## Optional authenticated demonstration

Use only a synthetic demo account and synthetic learner records. There is no
registration endpoint or seeded default password. An account and its learner
access must already have been provisioned before this sequence can work.

1. Execute `POST /api/v1/auth/login` with the demo account's `login_handle` and
   password. Avoid projecting passwords or token responses.
2. Copy `access_token`, click **Authorize**, and paste the token alone into the
   HTTP bearer field.
3. Execute `GET /api/v1/auth/me`, then `GET /api/v1/learners`.
4. Use an authorized synthetic learner's UUID to show their profile and
   preferences. Additional writes require the appropriate access role.

Access tokens normally expire after five minutes; sign in again if necessary.
Do not claim that these authenticated workflows were verified merely because
the health checks passed.

## Explain current limits accurately

- Reading assessment scores are educational measurements, not diagnoses.
- Pasted English text processing provides deterministic text measurements.
- PDF extraction endpoints exist, but uploads require private storage and the
  extraction worker setup documented in `docs/pdf-text-extraction.md`. The
  default Compose setup alone does not provide that complete demonstration.
- OCR review has internal database/service foundations. OCR has no public HTTP
  endpoint or enabled engine in this version.
- Speech, simplification, learner analytics, and numeracy remain placeholders.

## Verified during setup

On 23 October 2026, both Compose services were healthy. The database was at
`0009_ocr_review_workflow (head)`. Live checks returned HTTP 200 for Swagger,
HTTP 200 for both health endpoints, and HTTP 401 for unauthenticated learner
access. Authenticated business workflows were not exercised during this setup.

After the presentation, `docker compose stop` stops the services while preserving
the local database. Do not use `docker compose down -v`: it removes database data.

## Prepared Swagger login and text-processing demo

A synthetic educator account and `Synthetic Demo Reader` have now been provisioned
in the local development database. Copy the entire JSON object from
`/private/tmp/nlp-demo-login.json` into Swagger's login request body. That file
contains private credentials and is outside the repository. The instructor grant
lasts seven days from provisioning. No public registration endpoint was added.

1. Execute `POST /api/v1/auth/login` with that JSON. Expect HTTP 200.
2. Copy only the returned `access_token` value, without quotes. At the top of
   Swagger, click **Authorize**, paste it into the bearer field without adding
   `Bearer`, click **Authorize**, then **Close**.
3. Execute `GET /api/v1/auth/me`. Expect HTTP 200 and the educator role.
4. Execute `GET /api/v1/learners`. Expect the synthetic reader. Copy its `id`.
5. Execute `GET /api/v1/learners/{learner_id}` with that UUID.
6. Execute `POST /api/v1/learners/{learner_id}/reading-materials` with:

   ```json
   {
     "title": "Demo story",
     "language_tag": "en",
     "text": "A cat sits on a mat. The sun is warm. The cat runs to a tree."
   }
   ```

   Expect HTTP 201. Save the response's `id` as `material_id` and
   `latest_revision.id` as `revision_id`.
7. Execute `POST /api/v1/learners/{learner_id}/reading-materials/{material_id}/revisions/{revision_id}/processing-runs`
   with those three IDs and request body `{}`. Expect HTTP 201 and
   `status: succeeded` for this new revision. Inspect the returned measurements.

Login, current-user lookup, learner list/profile, material creation, and processing
were verified against the running API. Wrong-password login and unauthenticated
learner listing both returned HTTP 401; logout returned HTTP 204. Preferences are
not part of this educator demo: its preferences read returned HTTP 404 under the
current access policy. No production code was changed.

If an authorized request starts returning HTTP 401 after several minutes, log in
again and replace the token in **Authorize**. Swagger's example `string` values
are placeholders, not real credentials. Keep the credential file available for
the presentation; temporary files may be cleared by the operating system.
