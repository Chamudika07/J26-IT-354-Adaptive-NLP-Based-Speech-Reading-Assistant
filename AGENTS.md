# Repository engineering rules

These rules apply throughout this repository, subject to explicit user instructions.

- Preserve existing work; inspect the working tree before edits. Never commit or push
  automatically unless explicitly requested.
- Maintain one shared FastAPI backend at apps/backend and one PostgreSQL application
  database per environment. No per-module backends, database engines, or persistent
  application databases. Disposable test environments use the same architecture.
- Use a modular monolith and /api/v1 for REST endpoints.
- Use UUID primary keys, UUID foreign keys, and timezone-aware UTC timestamps.
- Keep Pydantic request/response schemas separate from SQLAlchemy models.
- Use the shared SQLAlchemy Base, engine/session infrastructure, and model registry.
- Alembic is required for every schema change. Maintain one migration history and one
  head; never create tables automatically at application startup.
- Modules must not directly write another module's tables. Use its public service
  interface and coordinate shared transaction boundaries.
- Never implement medical diagnosis logic or present educational scores as diagnoses.
- Collect the minimum necessary child/learner data. Future data endpoints must enforce
  learner-level authorization. Do not use real learner data in tests or development.
- Never commit secrets, real .env files, recordings, datasets, database dumps, or model
  checkpoints. Do not log credentials, tokens, learner content, or complete settings.
- Research code must not be imported by production code. Keep research dependencies
  separate; promotion requires review, tests, and documented provenance.
- Tests are required for new backend logic, including meaningful failure-path coverage.
  Use disposable PostgreSQL for integration tests, never production data or URLs.
- Run the relevant tests, Ruff checks, formatting checks, and mypy after backend edits.
  Report unavailable checks and failures honestly.
- Use uv and pyproject.toml for backend dependencies; keep uv.lock in sync.
- Keep mobile as a documented placeholder until scaffolding is explicitly requested.
- Do not add OCR, simplification, speech, analytics, numeracy, or other business features
  during foundation-only work.
