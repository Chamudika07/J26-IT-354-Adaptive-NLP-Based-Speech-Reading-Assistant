# Component 4 PP1 migration reconciliation — approval draft

## Scope and verified history

Current branch ends at 0006_learner_reading_sessions. Available origin/develop is
021362555b7b57e462a04d8823171ccf9eaa24ff and ends at 0008_pdf_text_extraction.
0001–0005 migration contents match. No team source or migrations were changed.
The combined review is staged in pytest temporary directories, not the working
migration directory. No branch merge, revision rewrite, database connection or seed
was performed. The actual branch still has its original migration head.

Proposed graph (revision names require team reservation):

    0005_auth_sessions
      |-- 0006_learner_reading_sessions --------------------|
      |-- 0006_reading_assessments                         |
           -> 0007_reading_material_processing             |
           -> 0008_pdf_text_extraction --------------------|
                         -> 0009_c4_merge (no operations)
                         -> 0010_c4_pp1_demo (one new table)

A merge revision is NOT a replacement for obtaining the three missing team revision
files and model registrations through the team's reviewed integration process.
Do not put these drafts in active alembic/versions while their parents are missing.
Never stamp the database to pretend parent migrations have executed.

## Compatibility evidence and limits

The static review imports the fetched assessment, reading-material and PDF models
alongside current shared metadata in an isolated test fixture. All FK targets
resolve and PostgreSQL table DDL compiles. The combined migration chain renders
PostgreSQL upgrade SQL without executing it. Table-name coverage and duplicate
CREATE TABLE checks compare the combined migration output to combined metadata.
This does NOT prove PostgreSQL trigger execution, downgrade behavior, runtime
permissions, every column alteration or migration-to-model equality on a server.
Those require the gated disposable PostgreSQL tests. No incompatibility has been
confirmed by the static checks; database compatibility remains UNVERIFIED.

Keep current Component 4 models: develop has a placeholder learner_modelling/models.py.
Blindly replacing that file would lose the two existing Component 4 model definitions.
Preserve all model-registry imports from both histories, then register Pp1DemoDataset
only when its migration is activated. No teammate model changes are proposed.

## Proposed table

Model: app/modules/learner_modelling/pp1_models.py (not registered at runtime yet).
Draft DDL: docs/component-4-migration-drafts/0010_c4_pp1_demo.py.

component4_pp1_demo_datasets: UUID id, unique fixed dataset_key, fixture_version=1,
64-character SHA256 source_digest, JSONB source_payload, JSONB provenance,
created_at TIMESTAMPTZ DEFAULT now(). No foreign keys or real learner identities.

Database checks require synthetic=true, verifiedTelemetry=false, envelope version=2,
exactly six records, and explicit fictional provenance. The seed/service must also
validate the full existing session contract, unique identities, times, units and
pinned canonical digest. Database checks alone do not certify valid telemetry.
The provenance is synthetic=true, fixture=pp1_fixture.json,
generator=component4-python-engines-v1. Do not label this as real learner consent.

Upgrade creates only this table. Downgrade removes only this table. Neither seeds
anything, changes production reading tables nor installs consent/authentication
exceptions. The schema can exist empty in other environments; service access is
restricted to explicitly enabled development. Runtime role should receive SELECT
only for this table; a separately approved seed identity needs INSERT. This requires
review against existing default privileges, not automatic blanket grants.

## Read-only/static commands (safe now)

From repository root:

    uv run --frozen --project apps/backend python -m pytest apps/backend/tests/unit/test_pp1_migration_drafts.py -q

The two static checks run; three PostgreSQL cases skip unless separately enabled.

## Proposed disposable PostgreSQL commands — NOT EXECUTED

The existing test fixture's suffix check alone is insufficient. The new gated tests
require the exact host 127.0.0.1, port 5432, database readbuddy_component4_test, role
readbuddy_component4_tester, actual identity verification, a non-superuser tester,
and no other connections. TEST_DATABASE_URL must already be privately configured
in that terminal; do not print it, use DATABASE_URL, or load a development .env.

These tests downgrade the WHOLE disposable schema to base and run migrations from
empty, Component 4 head, and develop head. This exceeds earlier approval to reset
only the two Component 4 tables. Obtain NEW full-schema disposable-test approval
and re-confirm exclusive use before enabling these flags. Adequate migration-object
ownership/permissions must be confirmed; do not elevate the tester to superuser.

After that approval, from repository root in PowerShell:

    if (-not $env:TEST_DATABASE_URL) { throw 'Configure the approved test URL privately first.' }
    try {
        $env:ALLOW_TEST_DATABASE_RESET = '1'
        $env:READBUDDY_PP1_FULL_SCHEMA_RESET = 'APPROVED_DISPOSABLE_ONLY'
        uv run --frozen --project apps/backend python -m pytest apps/backend/tests/unit/test_pp1_migration_drafts.py -q
        if ($LASTEXITCODE -ne 0) { throw 'Disposable migration review failed. STOP.' }
    }
    finally {
        Remove-Item Env:ALLOW_TEST_DATABASE_RESET -ErrorAction SilentlyContinue
        Remove-Item Env:READBUDDY_PP1_FULL_SCHEMA_RESET -ErrorAction SilentlyContinue
    }

The runner stages missing revisions from origin/develop plus the two draft files
in a temporary directory, injects only its verified connection into Alembic, and
does not change the working migration tree or readbuddy_dev. Each test transaction
rolls back on failure; successful cases leave the disposable database at the draft
head with no demo records. Do not use it with an already incompatible/unknown revision.
Record real PostgreSQL results before approving application integration.

## Team integration commands — proposals only

After the team's approved integration supplies the missing revisions and model
registrations (no branch merge is performed by this task):

    Set-Location apps/backend
    uv run --frozen alembic heads
    uv run --frozen alembic merge -m "Preserve Component 4 and shared develop histories" --rev-id 0009_c4_merge 0006_learner_reading_sessions 0008_pdf_text_extraction

Use the reviewed 0010 draft as the next revision after that merge; do not also run
merge generation if the team has already supplied an equivalent merge. Confirm
one head and rerun migration/model comparisons on disposable PostgreSQL. Do not
apply either revision to readbuddy_dev without separate approval. Seeding,
privilege changes and iPhone testing remain separate steps.
