# J26-IT-354-Adaptive-NLP-Based-Speech-Reading-Assistant

Adaptive NLP-Based Speech & Reading Assistant for Children with Dyslexia.

This repository contains the project foundation, Database Sprint 1, and the
Authentication & Authorization Foundation, and Learner Profile & Preferences API:
identity and learner storage, login/session management, scoped profile reads, and
versioned accessibility preference updates. It does not implement diagnosis, OCR,
simplification, speech recognition, learner analytics, or numeracy algorithms.
Use synthetic data only.

## Repository layout

| Path | Purpose |
| --- | --- |
| apps/backend | One FastAPI modular monolith, SQLAlchemy, Alembic, tests |
| apps/mobile | React Native + TypeScript placeholder; not scaffolded |
| packages/api-client | Future generated TypeScript API client placeholder |
| research | Isolated experiment workspace; no production imports |
| docs | Architecture, configuration, and data-protection decisions |
| scripts | Shared development checks |
| .github | CI, pull-request template, CODEOWNERS placeholder |

The backend reserves auth, learners, documents, simplification, speech,
learner_modelling, and numeracy modules. Auth and learners own the nine Sprint 1 tables;
auth additionally owns two session tables. The other modules remain empty. Health,
authentication, and the four approved learner/profile/preference endpoints are exposed.

## Requirements

- Docker with Compose v2 or newer and a running Docker daemon.
- For host development/checks: Python 3.13 and uv 0.12.23.
- No Node/React Native setup is needed yet.

## Run locally with Docker

From the repository root, export your own URL-safe local password. The following
value is a placeholder: replace it, and keep the same password for an existing volume.
No .env file needs to be created.

```sh
export POSTGRES_PASSWORD='replace_with_your_own_url_safe_password'
export JWT_SIGNING_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
docker compose up --build -d --wait
docker compose exec backend alembic upgrade head
curl http://127.0.0.1:8000/api/v1/health
curl http://127.0.0.1:8000/api/v1/health/ready
```

Expected responses are {"status":"ok"} and {"status":"ready"}. Development API
documentation is at http://127.0.0.1:8000/docs. All REST endpoints use /api/v1.
The unchanged Alembic baseline adds no application tables. Three subsequent Sprint 1
revisions add nine tables and seed only four role definitions. Revision
0005_auth_sessions adds two auth session tables without seeding credentials. Migrations
are explicit. No account provisioning endpoint is included.

```sh
docker compose logs backend
docker compose down
```

The named PostgreSQL volume survives down. Do not add -v unless intentionally deleting
all local database data. Initialization variables do not reset an existing password.
Ports bind to 127.0.0.1. This is a local development setup, not a production deployment.

## Run the backend on the host

Start only the same Compose database, then run the API outside Docker. Do not also
run the Compose backend on port 8000.

```sh
export POSTGRES_PASSWORD='replace_with_your_own_url_safe_password'
export JWT_SIGNING_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
docker compose up -d --wait db
cd apps/backend
uv sync --locked
export DATABASE_URL="postgresql+psycopg://adaptive:${POSTGRES_PASSWORD}@127.0.0.1:5432/adaptive"
uv run --locked alembic upgrade head
uv run --locked uvicorn app.main:create_app --factory --reload --no-access-log
```

The root and backend .env.example files document their respective variables; they
contain placeholders only. Host commands use apps/backend as the working directory.
Database URLs require URL-encoded credentials; the Compose shortcut assumes a URL-safe
password and default database/user names.

## Run checks

From the repository root:

```sh
sh scripts/check_backend.sh
```

Ordinary tests use synthetic settings and do not need PostgreSQL. PostgreSQL tests
require TEST_DATABASE_URL pointing to an exclusive disposable database ending in _test
and ALLOW_TEST_DATABASE_RESET=1. Migration tests drop and recreate application tables.
Tests never fall back to DATABASE_URL. CI supplies its own isolated PostgreSQL service,
runs the full suite, applies migrations, checks schema drift, and builds the image.

To include integration tests locally, provision a disposable database ending in _test
in an isolated test environment, export TEST_DATABASE_URL and ALLOW_TEST_DATABASE_RESET=1,
and rerun the check script. See the Sprint 1 guide for complete local commands.
Never point tests or migration experiments at shared or production data.

## Team rules and documentation

- [Contribution workflow](CONTRIBUTING.md)
- [Engineering rules](AGENTS.md)
- [Architecture, environment variables, migration strategy, and limits](docs/foundation.md)
- [Database Sprint 1 schema, constraints, indexes, and test commands](docs/database-sprint-1.md)
- [Authentication, session lifecycle, authorization policies, and limits](docs/auth-authorization-foundation.md)
- [Learner Profile & Preferences API and concurrency contract](docs/learner-profile-api.md)
- [Mobile setup reserved for later](apps/mobile/README.md)
- [Research separation and governance](research/README.md)

Commit dependency lockfiles and reviewed migrations when you commit your work. Configure
branch protections and real CODEOWNERS in GitHub before relying on review enforcement.
