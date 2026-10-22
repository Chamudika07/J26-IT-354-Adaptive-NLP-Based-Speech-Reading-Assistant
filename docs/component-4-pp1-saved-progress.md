# PP1 synthetic session persistence — code ready, execution awaiting approval

## Flow

Existing signed-in learner journey -> Connected sample (laptop) -> choose a fixed
sample -> Save Sample Progress -> POST /api/v1/learner-modelling/pp1-demo/saved-progress/{count}
-> transaction INSERTs missing rows -> committed receipt -> GET saved-progress
-> validated shared Profile, Analytics, Tips and factual Summary.

Save Sample N appends approved samples 1..N that are not already present. It does
not replace or delete previously saved rows. Selecting an earlier sample cannot
reduce saved history. Refresh Saved Progress reloads the database after restart;
no device cache is treated as confirmation of persistence. Cancellation/timeout
may occur after commit: retry the same sample safely, then refresh. Network failure
never switches sources. Offline examples retain their existing scenario workflow.
Guardian/Educator remain offline and do not receive these learner-only records.
Saved Qwen3 AI reports and PDFs remain independent.

## Data/contract

New table component4_pp1_saved_sessions: UUID id, account_id FK users.id,
sequence 1..6, sample_session_id UUID, fixture_version=1, source_digest,
measurements JSONB containing ONE fictional session, created_at TIMESTAMPTZ.
Unique (account_id,sequence) and (account_id,sample_session_id) ensure retry safety.
The endpoint accepts no measurements, learner IDs or telemetry body: only a fixed
prefix count. Every stored object must match the validated approved fixture,
including identities, timestamps, context, counts, durations and units. The existing
SampleFile/ReadingSessionIngest contracts validate all six before selecting any.
Saved reads validate a contiguous approved prefix and calculate from the actual
measurement objects read from the new table, never from claimed client metrics.

POST returns synthetic=true, sourceDigest, savedSessionCount, createdSessionCount
only AFTER commit. A failed or uncertain commit produces no confirmed receipt.
GET returns existing strict DemoResult, with selectedSessionCount reflecting actual
saved rows. There is no saved-data delete/reset API. No synthetic values are written
to production reading_sessions, support settings or consent tables.

Both endpoints require existing authenticated active learner, explicit account UUID
allowlist, development opt-in, trusted HTTPS and exact database identity
readbuddy_component4_pp1_demo at 127.0.0.1:5432. Missing/unapplied storage returns
sanitized 503 without sample fallback. Production consent routes are unchanged.

## Minimal approval requested (not executed)

1. Apply ONLY new revision 0008_c4_pp1_saved, parent 0007_c4_pp1_demo, to the
existing isolated readbuddy_component4_pp1_demo database. No other database,
old 0009/0010 proposal, seeding or bootstrap is involved.
2. Grant only SELECT and INSERT on this one new table to readbuddy_c4_pp1_runtime.
3. Separately authorize one real save/read-back check with the existing fictional
account, then verify its synthetic rows in pgAdmin. No PostgreSQL writes occurred
in this code-preparation step; current tests use mocked persistence/HTTP.

After approval for item 1, from repository root:

    uv run --frozen --project apps/backend python -m app.modules.learner_modelling.pp1_saved_setup --approve-pp1-saved-storage

This command prompts privately for the PP1 owner password, fixes target and owner,
checks actual host/database/role and starting revision 0007, then upgrades only to
0008 in a transaction. It verifies exactly one additional empty table. It does not
read .env, grant privileges, create accounts or seed records. If it stops, review
before retrying. Do not rerun the earlier empty-database setup runner.

For item 2, in an authenticated owner/administrator psql session connected to the
new PP1 database only (execute only AFTER approval and successful migration):

    BEGIN;
    DO $guard$
    BEGIN
      IF current_database() <> 'readbuddy_component4_pp1_demo'
         OR host(inet_server_addr()) IS DISTINCT FROM '127.0.0.1'
         OR inet_server_port() IS DISTINCT FROM 5432 THEN
        RAISE EXCEPTION 'Wrong PP1 target';
      END IF;
      IF (SELECT count(*) FROM public.alembic_version) <> 1
         OR NOT EXISTS (SELECT 1 FROM public.alembic_version WHERE version_num='0008_c4_pp1_saved') THEN
        RAISE EXCEPTION 'Wrong PP1 revision';
      END IF;
      IF NOT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
          WHERE n.nspname='public' AND c.relname='component4_pp1_saved_sessions'
          AND c.relkind='r' AND pg_get_userbyid(c.relowner)='readbuddy_c4_pp1_owner') THEN
        RAISE EXCEPTION 'Wrong storage owner';
      END IF;
      IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='readbuddy_c4_pp1_runtime'
          AND rolcanlogin AND NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole
          AND NOT rolbypassrls AND NOT rolreplication) THEN
        RAISE EXCEPTION 'Wrong runtime attributes';
      END IF;
    END $guard$;
    GRANT SELECT, INSERT ON public.component4_pp1_saved_sessions TO readbuddy_c4_pp1_runtime;
    DO $verify$
    DECLARE p text;
    BEGIN
      FOREACH p IN ARRAY ARRAY['SELECT','INSERT'] LOOP
        IF NOT has_table_privilege('readbuddy_c4_pp1_runtime','public.component4_pp1_saved_sessions',p) THEN
          RAISE EXCEPTION 'Missing approved privilege';
        END IF;
      END LOOP;
      FOREACH p IN ARRAY ARRAY['UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER'] LOOP
        IF has_table_privilege('readbuddy_c4_pp1_runtime','public.component4_pp1_saved_sessions',p) THEN
          RAISE EXCEPTION 'Unexpected privilege';
        END IF;
      END LOOP;
    END $verify$;
    COMMIT;

Use ON_ERROR_STOP; any error requires ROLLBACK, never broader grants. Existing
runtime grants remain unchanged. No sequence grant is necessary (UUID keys).
Existing consent_required behavior is not a request to grant production table writes.

## Verification limits

Static/unit tests exercise SQL construction, mocked save/read-back, retries,
corrupt fixture/records, environment/identity guards, commit failure and mobile
save-then-refresh/navigation. PostgreSQL execution, real commit failure recovery,
physical app restart and iPhone persistence verification remain pending approval.

## Files changed for this implementation

Backend:
- apps/backend/alembic/versions/0008_c4_pp1_saved.py
- apps/backend/app/modules/learner_modelling/pp1_models.py
- apps/backend/app/modules/learner_modelling/pp1_saved.py
- apps/backend/app/modules/learner_modelling/pp1_saved_setup.py
- apps/backend/app/modules/learner_modelling/router.py
- apps/backend/tests/unit/test_pp1_saved.py
- apps/backend/tests/unit/test_pp1_migration_drafts.py
- apps/backend/tests/unit/test_pp1_standalone.py
- apps/backend/tests/unit/test_db_conventions.py
- apps/backend/tests/migrations/test_history.py

Mobile (under apps/mobile/src/features/learnerModelling/):
- data/pp1Client.ts
- preview/DeveloperTestSession.tsx
- components/ReadingResultsScenarios.tsx
- components/ConnectedLearnerJourney.tsx
- navigation/LearnerNavigation.tsx
- __tests__/pp1Client.test.ts
- __tests__/pp1Journey.test.tsx
- __tests__/accountBoundary.test.tsx

Documentation: docs/component-4-pp1-saved-progress.md
