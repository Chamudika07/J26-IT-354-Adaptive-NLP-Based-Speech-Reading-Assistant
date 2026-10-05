# Contributing

Read AGENTS.md and docs/foundation.md before changing shared infrastructure.

## Branches and reviews

- Keep main releasable and develop as the shared integration branch.
- Branch from develop using short-lived feat/, fix/, or chore/ branches.
- Open a focused pull request; include behavior, validation results, and risks.
- Require review for database/migration, configuration, security, and API changes.
- Do not force-push shared branches or commit someone else's unrelated work.
- Configure branch protection in GitHub; repository files alone cannot enforce it.
- Replace CODEOWNERS placeholders with actual maintainers before relying on ownership.

## Local checks

Install Python 3.13 and uv 0.12.23, then run from the repository root:

    sh scripts/check_backend.sh

This syncs the locked development environment and runs Ruff, formatting checks, mypy,
and pytest with coverage. The database integration check skips unless an explicit
TEST_DATABASE_URL names a disposable PostgreSQL database ending in _test. CI provides
that database and runs the migration upgrade/drift checks and Docker image build.

Backend dependency changes go through uv add / uv add --dev from apps/backend.
Commit both pyproject.toml and uv.lock. Do not hand-edit dependency resolutions.

## Module and data rules

Keep HTTP handling, Pydantic schemas, business rules, and SQLAlchemy persistence
separate. A module owns its writes. Changes to shared contracts must be coordinated
with consumers. New backend logic needs meaningful tests, including failure paths.

Every schema change needs a reviewed Alembic migration. Coordinate revisions before
merging; maintain one head and never rewrite migrations already applied elsewhere.

Use synthetic data. No real learner records, credentials, voice recordings, database
dumps, model checkpoints, or sensitive notebook outputs belong in pull requests.
Do not implement diagnosis. Keep research dependencies and code out of production.

## Scope of the current foundation

Do not scaffold React Native or implement feature behavior as incidental cleanup.
The seven modules, mobile, research, and API-client locations are reserved only.
