# Foundation architecture

One React Native client (reserved), one FastAPI modular monolith, and one PostgreSQL
application database per environment. Local development and disposable CI databases
are isolated environments of the same design, not additional application databases.

## Backend boundaries

The app factory is app.main:create_app. All REST endpoints use /api/v1. Each module
reserves router.py, schemas.py, models.py, service.py, and repository.py. No module
has content-processing endpoints. Auth exposes login, refresh, logout, and me; see
[the authentication foundation](auth-authorization-foundation.md). Learners exposes
scoped list/detail reads and preference reads/updates; see [the API contract](learner-profile-api.md).
Database Sprint 1
adds nine auth/learner tables; see
[the current database specification](database-sprint-1.md).

Requests will flow through routers, services, and module-owned repositories. Modules
may call another module's public service interface but must not directly write its
tables. Shared infrastructure must not accumulate feature-specific business logic.
Pydantic input/output schemas remain separate from SQLAlchemy models.

The database engine is created during application lifespan without connecting until
needed. Synchronous database work uses synchronous endpoints. Each request gets its
own session; closing rolls back unfinished transactions. Services will own explicit
transaction/commit boundaries. Never share sessions across concurrent tasks.

GET /api/v1/health is liveness and works without a database connection.
GET /api/v1/health/ready performs SELECT 1; unavailable databases return a sanitized
503 response. It does not assert schema compatibility or run migrations.

## Data conventions and migrations

- One declarative Base, model registry, and Alembic versions directory.
- UUIDPrimaryKeyMixin uses UUIDv4 values and native PostgreSQL UUID columns.
- TimestampMixin uses timezone-aware created_at and updated_at columns.
- Connections use UTC. PostgreSQL stores timestamp instants; format API dates in UTC.
- updated_at is maintained by SQLAlchemy updates, not a database trigger. Raw SQL
  updates must explicitly update it when future work requires them.
- Name check constraints explicitly to satisfy the shared naming convention.
- The baseline migration is deliberately empty. Applying it creates only Alembic's
  version tracking table; there is no application schema yet.
- Sprint 1 preserves that baseline and adds 0002_auth_identity, 0003_learner_foundation,
  and 0004_consent_evidence sequentially. Revision 0005_auth_sessions adds two session
  tables; the current head has eleven application tables.
- Never run Base.metadata.create_all or automatic migrations at application startup.

Schema-change workflow, from apps/backend:

1. Update the owning module's models and register any new model modules.
2. Run uv run alembic revision --autogenerate -m "describe change" against local data.
3. Review generated SQL, constraints, backfills, and downgrade/data-loss implications.
4. Test empty-to-head and previous-version-to-head upgrades using disposable data.
5. Coordinate concurrent migrations; merge compatible heads explicitly. Never edit
   a revision already applied to shared environments.
6. Run uv run alembic upgrade head, then uv run alembic check.

CI checks for one root/head, applies the baseline to disposable PostgreSQL, and checks
metadata drift. Future schema migrations require corresponding upgrade tests.
Deployments must execute migrations once before rolling out dependent application
changes. Destructive changes require a backup and recovery plan.

## Configuration

| Variable | Scope | Requirement |
| --- | --- | --- |
| POSTGRES_DB | Compose | Defaults to adaptive |
| POSTGRES_USER | Compose | Defaults to adaptive |
| POSTGRES_PASSWORD | Compose | Required, URL-safe local secret; examples are placeholders |
| POSTGRES_PORT | Compose | Defaults to 5432; bound only to loopback |
| API_PORT | Compose | Defaults to 8000; bound only to loopback |
| APP_ENV | Backend | development, test, staging, or production; default development |
| LOG_LEVEL | Backend | DEBUG, INFO, WARNING, ERROR, CRITICAL; default INFO |
| JWT_SIGNING_KEY | Backend | Required random secret, at least 32 bytes; example rejected |
| JWT_ISSUER / JWT_AUDIENCE | Backend | Exact token identifiers; see auth foundation |
| ACCESS_TOKEN_TTL_SECONDS | Backend | Default 300, maximum 300 |
| REFRESH_ABSOLUTE_TTL_SECONDS | Backend | Default/maximum 604800 |
| REFRESH_IDLE_TTL_SECONDS | Backend | Default/maximum 86400 |
| JWT_CLOCK_TOLERANCE_SECONDS | Backend | Default/maximum 30 |
| DATABASE_URL | Backend | Required postgresql+psycopg URL |
| MIGRATION_DATABASE_URL | Alembic | Optional privileged role targeting the same database |
| TEST_DATABASE_URL | Integration tests | Explicit disposable database ending in _test |
| ALLOW_TEST_DATABASE_RESET | Integration/migration tests | Must be 1 to permit destructive migration tests |

Compose constructs DATABASE_URL using the db hostname. A backend run on the host
uses 127.0.0.1 and the published PostgreSQL port instead. Alembic reads the optional
migration URL directly, so URL-encoded percent characters are not interpolated
through alembic.ini. Never use the migration URL for another database.

Settings can read an optional .env relative to the process working directory; shell
variables take precedence. Run host backend commands from apps/backend. No real .env
is supplied or needed. Root .env.example describes Compose; the backend example
describes host backend settings. Settings conceal credentials in representations and
validation error strings. Do not log complete settings or validation error objects.

## Docker and local data

Compose runs db and backend, with a persistent postgres_data volume. PostgreSQL
readiness gates backend startup; the backend has a readiness health check. The
backend image runs as a non-root user and installs only locked runtime dependencies.
Its build context is apps/backend and its allowlist excludes tests, secrets, and
research. Access logs are disabled to avoid retaining identifiers in request URLs.

The local Compose PostgreSQL role is a bootstrap/superuser role for developer
convenience only. Before deployment, provision a least-privilege application role and
a separate migration role in the same database; add HTTPS, secret management,
encrypted storage/backups, resource limits, and restore testing. This Compose setup
is local development infrastructure, not a production deployment configuration.

PostgreSQL initialization variables only apply to an empty volume. Keep the same
local password after restarting. Changing the shell variable does not change an
existing database password. docker compose down preserves the volume; adding -v
deletes it and must be an intentional local reset.

## Child-data protection and current limits

Authentication/session flows and learner authorization policies are implemented.
Consent policy enforcement, file storage, retention jobs, and general audit trails
are not implemented. Sprint 1 adds consent evidence
storage and access-grant history. Health, authentication, and approved learner-profile
read/preference-update endpoints are exposed. Do not add real child or learner data to this foundation.

Future endpoints must enforce learner-level permissions, collect minimum necessary
attributes, use controlled private storage, and define deletion/retention behavior.
UUID identifiers do not grant access. Keep passwords, tokens, document text, audio,
and identifiable learner records out of logs, exceptions, fixtures, and Git. Consent
for research reuse is separate from access to the learning assistant. No medical
diagnosis logic, diagnostic labels, or clinical claims are permitted.

## Toolchain and deferred work

Python 3.13, uv 0.12.23, PostgreSQL 17, SQLAlchemy 2.x, Pydantic 2.x. Python packages
are resolved in uv.lock; Docker uses minor/major-maintained Python/PostgreSQL image
tags, so those base images are not immutable digest pins. Pin deployment images by
digest when establishing a release process.

Mobile, generated TypeScript client, account provisioning/recovery/administration,
file processing, ML inference, workers, and educational processing are deferred. No ML/OCR/LLM/speech
libraries or additional backend/database services are introduced.

## References

- [FastAPI modular applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [SQLAlchemy sessions](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)
- [Alembic migration review](https://alembic.sqlalchemy.org/en/latest/autogenerate.html)
- [uv in Docker](https://docs.astral.sh/uv/guides/integration/docker/)
- [Compose startup order](https://docs.docker.com/compose/how-tos/startup-order/)
