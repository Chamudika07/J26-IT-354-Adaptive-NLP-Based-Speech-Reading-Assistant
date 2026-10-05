# J26-IT-354-Adaptive-NLP-Based-Speech-Reading-Assistant

Adaptive NLP-Based Speech & Reading Assistant for Children with Dyslexia.

This repository currently contains only the initial project foundation. It does not
implement diagnosis, authentication, OCR, simplification, speech recognition, learner
analytics, or numeracy algorithms. Use synthetic data only.

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
learner_modelling, and numeracy modules. They expose no business endpoints or tables.

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
docker compose up --build -d --wait
docker compose exec backend alembic upgrade head
curl http://127.0.0.1:8000/api/v1/health
curl http://127.0.0.1:8000/api/v1/health/ready
```

Expected responses are {"status":"ok"} and {"status":"ready"}. Development API
documentation is at http://127.0.0.1:8000/docs. All REST endpoints use /api/v1.
Alembic's baseline adds no application tables. Migrations are always an explicit step.

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

Ordinary tests use synthetic settings and do not need PostgreSQL. The integration
test skips unless TEST_DATABASE_URL points to a disposable PostgreSQL database with
a name ending in _test. It never falls back to DATABASE_URL. CI supplies its own
isolated PostgreSQL service, runs the integration check, applies migrations, checks
schema drift, and builds the backend image.

To include integration tests locally, provision a disposable database ending in _test
in an isolated test environment, export TEST_DATABASE_URL, and rerun the check script.
Never point tests or migration experiments at shared or production data.

## Team rules and documentation

- [Contribution workflow](CONTRIBUTING.md)
- [Engineering rules](AGENTS.md)
- [Architecture, environment variables, migration strategy, and limits](docs/foundation.md)
- [Mobile setup reserved for later](apps/mobile/README.md)
- [Research separation and governance](research/README.md)

Commit dependency lockfiles and reviewed migrations when you commit your work. Configure
branch protections and real CODEOWNERS in GitHub before relying on review enforcement.
