## Change

Describe the problem, resulting behavior, and affected modules.

## Validation

List commands run and results. Explain skipped or unavailable checks.

## Review checklist

- [ ] Scope stays within the requested work; no unrelated features.
- [ ] New backend logic has meaningful tests.
- [ ] One shared backend, database, metadata collection, and migration history remain.
- [ ] Schema changes have a reviewed Alembic revision and one resulting head (or not applicable).
- [ ] No module writes another module's tables directly.
- [ ] API schemas are separate from ORM models; identifiers use UUIDs.
- [ ] No secrets, real learner data, recordings, datasets, or notebook outputs are included.
- [ ] No medical diagnosis logic or production imports from research are introduced.
- [ ] Configuration examples and documentation reflect the change.
