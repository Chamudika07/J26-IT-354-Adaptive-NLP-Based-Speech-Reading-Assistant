# Learner-only connected PP1 implementation slice

No migration, table creation, seed or development database change is included.

## Route

GET /api/v1/learner-modelling/pp1-demo/scenarios/{count}, count 0–6.
No query parameters, arbitrary telemetry or learner identifiers are accepted.
Response: DemoResult (pp1-demo-result-v1), learner-only ConnectedPreview payload.
The outer source denotes PostgreSQL-backed execution; the inner source preserves
its existing pure-calculator contract, not a separate database or API request.
Only the validated response establishes a successful calculation.

Registration requires explicit process environment APP_ENV=development and
READBUDDY_PP1_ENABLED=1 before backend import/startup. Runtime guards also check
the configured application environment, enabled flag, active authenticated learner
role and membership in READBUDDY_PP1_ACCOUNT_IDS (comma-separated UUIDs, no defaults).
An unset/invalid allowlist denies access. Configure only approved fictional accounts.
HTTPS is mandatory; do not enable untrusted forwarded-header handling.
Production routes and consent dependencies are unchanged.

The repository query is SELECT-only, expecting the previously proposed
component4_pp1_demo_datasets table. Until approved migration and seeding, the route
returns sanitized 503; it never reads production reading_sessions or returns offline
fixtures as database success. The packaged fixture is a validation reference only.
Source payload must contain exactly six sessions and match the pinned canonical
SampleFile SHA256. Changed fixture versions require explicit code and test review.

## Mobile

createPp1Client accepts existing authenticated session and HTTPS API root. It returns
only validated learner evidence matching the pinned prepared prefix, except the
fresh generation timestamp. Errors never choose offline examples. The UI wiring,
source labels (Sample Data / Calculated on laptop), explicit offline choice and
connected-source restart behavior are deferred until storage is approved and ready.
Guardian/Educator remain offline; the endpoint has no role selector.

## Migration gate (fresh fetch during implementation)

origin/develop 021362555b7b57e462a04d8823171ccf9eaa24ff ends at
0008_pdf_text_extraction, through 0007_reading_material_processing and
0006_reading_assessments. Current Component 4 ends at
0006_learner_reading_sessions. Both descend from 0005_auth_sessions.
No demo migration was created: reconcile shared history to one head first.
No team migrations were changed or merged.

Next: agree migration reconciliation, implement reviewed shared-Base model and
migration, verify against disposable PostgreSQL with approval, then separately
approve application of that migration and fixture seed to readbuddy_dev. Complete
trusted local HTTPS, configure fictional-account allowlist privately, wire and test
mobile controls, and perform physical iPhone verification. No device success claimed.
