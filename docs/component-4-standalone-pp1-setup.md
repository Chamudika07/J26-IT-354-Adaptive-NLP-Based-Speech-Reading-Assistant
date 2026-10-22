# Standalone Component 4 PP1 environment

## Active branch history

0001 -> ... -> 0006_learner_reading_sessions -> 0007_c4_pp1_demo -> 0008_c4_pp1_saved.
The new 0007 uses the corrected JSONB expressions from the reviewed inactive 0010.
It creates one empty fictional dataset table, with no account or fixture seed.
No other team's revisions are required. The old 0009/0010 files remain inactive
proposals and are not part of the active Alembic history. Future integration must
reconcile the NEW Component 4 head rather than activate the old proposal unchanged.
Shared Base registration includes Pp1DemoDataset and Pp1SavedSession. Revision 0008
adds individually identifiable synthetic saved sessions; neither migration seeds
records. No tables are created at startup.

## Commands prepared for later approval (DO NOT run during code preparation)

Create a new native PostgreSQL database named readbuddy_component4_pp1_demo,
with a non-superuser migration owner and a separate least-privilege runtime role.
No use of readbuddy_dev or readbuddy_component4_test is authorized by this plan.
Use one shared FastAPI instance and one database for this temporary environment.

After database/role creation and separate migration execution approval:
configure terminal-only APP_ENV=development and the private DATABASE_URL and
MIGRATION_DATABASE_URL for this NEW environment, then from apps/backend:

    uv run --frozen alembic upgrade 0007_c4_pp1_demo

Never run this against an unverified environment. The Alembic command itself is
shared and NOT hardwired to the new database: verify both configured URLs privately
and current_database/current_user before migration. Do not edit .env.

For the prepared provisioning commands, privately configure terminal-only
READBUDDY_PP1_DATABASE_URL with the approved non-superuser seed/operator credentials.
The commands allow only postgresql+psycopg, 127.0.0.1:5432,
readbuddy_component4_pp1_demo, no URL options, APP_ENV=development; they recheck
actual database identity, non-superuser status and exact 0007 head before writing.
They never fall back to DATABASE_URL or load .env.

After separate fixture insertion approval, from apps/backend:

    uv run --frozen python -m app.modules.learner_modelling.pp1_seed --development-synthetic-only

Exactly six pinned sessions are validated with the existing contract and canonical
digest before SQL. First execution inserts and reads back the dataset in one
transaction. Re-execution verifies an exact match without updating it. Conflicting
payload/version/provenance fails and rolls back. No production session or consent
table is written. No credentials or raw exceptions are printed.

## Fictional account bootstrap preparation

There is no shared public account/profile creation service in this branch. Therefore
this is a one-time operator tool, NOT a new Component 4 runtime service or API.
Its execution requires specific approval for the three records and self-referencing
audit fields, as used in the earlier reviewed bootstrap. Shared owners must approve
this provisioning exception; it must not be promoted into production provisioning.

Prepared command (only after that approval), from apps/backend:

    uv run --frozen python -m tools.component4_pp1_bootstrap --approve-three-fictional-records-and-self-audit

It prompts privately twice for a new password and delegates to the existing Auth
Argon2id helper. It requires no existing users, the active learner role, no unexpected
insert/delete triggers or rewrite rules, and inserts one c4_demo_learner user,
one learner grant, and one linked Fictional PP1 Learner in one transaction.
Audit grantor/creator references point only to the new fictional user. Existing
accounts cause a safe refusal; passwords are never reset or overwritten. No admin,
guardian/educator relationships, consent or reading sessions are created.
It prints only the newly generated nonsecret account UUID for explicit server
allowlisting. The bootstrap does not itself enable endpoint access.

## Runtime boundaries

Keep existing authenticated session handling, deny-by-default consent on production
routes, HTTPS and READBUDDY_PP1_ENABLED/READBUDDY_PP1_ACCOUNT_IDS guards unchanged.
Configure the NEW runtime database credentials and signing key privately in its
terminal. Use the generated fictional account UUID, never an invented learner grant.
The iPhone flow and explicit offline fallback are already wired; trusted HTTPS and
physical-device verification remain outstanding. Saved AI/PDF artifacts are separate.

## Provisioning order and saved-session storage

For a NEW empty environment only: separately approve database/roles, migrate to
0007, bootstrap the fictional account and seed the pinned six-session dataset,
then apply 0008. The existing bootstrap/seed tools require exactly 0007; do not run
them after 0008 or weaken their guard. An already provisioned environment at 0008
must NOT repeat bootstrap, seeding or migrations. This guide is not approval to
change a database. Existing operator approvals remain separate from source setup.

From repository root, after migration approval and only when at 0007:

```powershell
uv run --frozen --project .\apps\backend python -m app.modules.learner_modelling.pp1_saved_setup --approve-pp1-saved-storage
```

This command privately prompts for the owner password, checks the exact database,
owner and active head, upgrades only to 0008, and verifies one new empty table.
Never activate the inactive 0009/0010 drafts. See
[saved progress](component-4-pp1-saved-progress.md) for the full guarded grant
transaction. Its ONLY additional runtime grant is:

```sql
GRANT SELECT, INSERT ON public.component4_pp1_saved_sessions
TO readbuddy_c4_pp1_runtime;
```

Execute only inside that guide's target/owner/revision-guarded transaction after
approval. No UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER or schema CREATE grant
is needed. UUID keys are supplied by the application; there is no sequence grant.
Existing reviewed authentication/session and read-only dataset grants remain
unchanged. This is not a replacement for those grants or a blanket table grant.

Expected application records: one fictional user, one learner-role grant and one
linked profile; one dataset row containing six fixture records; initially zero
saved-session rows. Save Sample N appends missing sessions 1..N for that account.
Retrying is idempotent; selecting an earlier sample does not delete history.
Production reading_sessions and consent tables receive no synthetic measurements.

Read-back in an authenticated PP1 psql/pgAdmin session (no personal data):

```sql
BEGIN READ ONLY;
SELECT current_database(), current_user, host(inet_server_addr()), inet_server_port();
-- STOP unless target is readbuddy_component4_pp1_demo at 127.0.0.1:5432.
SELECT version_num FROM public.alembic_version; -- exactly 0008_c4_pp1_saved
SELECT dataset_key, fixture_version,
       jsonb_array_length(source_payload->'records') AS sessions,
       source_payload->>'synthetic' AS synthetic,
       source_payload->>'verifiedTelemetry' AS verified_telemetry
FROM public.component4_pp1_demo_datasets;
SELECT sequence, sample_session_id, fixture_version, created_at
FROM public.component4_pp1_saved_sessions ORDER BY sequence;
COMMIT;
```

Save Sample Progress confirms only committed saves. Refresh Saved Progress reads
actual saved rows and runs the Python engines. Check Profile, Analytics, Tips and
factual Summary, then restart/sign in and refresh again. Failures require explicit
retry or Use offline examples; there is no silent fallback. Saved AI reports remain
separate. This cleanup does not claim a new physical-device verification.

## Reproducible trusted HTTPS runtime startup

Use the existing provisioned database and approved runtime grants. This starts the
same shared FastAPI app. It never migrates, seeds or changes certificate trust.
Stop the existing backend normally before launching another instance. No process
termination or firewall changes are performed here.

Prerequisites: uv, native PostgreSQL and an approved development server certificate,
private key and public CA outside the repository. The certificate SAN must include
the currently assigned laptop IPv4 address. Transfer ONLY the public CA to iPhone
and enable trust through the approved procedure; keep both private keys on laptop.
If the IP changes, obtain a matching certificate. Never disable TLS validation.

From repository root, paste the complete block into visible PowerShell. It uses
foreground private database-password entry, a fresh process-only signing key, and
an explicit fictional-account UUID verified against the existing account. No .env
is read or written. Do not put any password or token into this block.

```powershell
$ErrorActionPreference = 'Stop'
$pp1Start = @'
import getpass
import ipaddress
import os
import secrets
import socket
import ssl
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path("apps/backend").resolve(strict=True)))
import uvicorn
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.engine import URL
from app.core.config import Settings
from app.db.session import create_db_engine
from app.main import create_app

engine = None
try:
    bind = str(ipaddress.IPv4Address(input("Verified laptop IPv4 (or 127.0.0.1): ").strip()))
    address = ipaddress.IPv4Address(bind)
    if not (address.is_private or address.is_loopback) or address.is_unspecified or address.is_multicast or address.is_link_local:
        raise ValueError("Nonlocal address")
    paths = []
    for label in ("Server certificate", "Server private key", "Public CA certificate"):
        raw = Path(input(label + " absolute path: ").strip())
        if not raw.is_absolute():
            raise ValueError("Absolute path required")
        path = raw.resolve(strict=True)
        if not path.is_file() or path.is_relative_to(Path.cwd().resolve()):
            raise ValueError("Certificates must be outside repository")
        paths.append(str(path))
    cert, key, ca = paths
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(cert, key)
    ssl.create_default_context(cafile=ca)
    # Binding verifies address assignment and port availability; no listener starts.
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        probe.bind((bind, 8443))
    account = str(UUID(input("Approved fictional ACCOUNT UUID (not profile UUID): ").strip()))
    password = getpass.getpass("PP1 runtime database password (hidden): ")
    url = URL.create("postgresql+psycopg", username="readbuddy_c4_pp1_runtime",
        password=password, host="127.0.0.1", port=5432, database="readbuddy_component4_pp1_demo")
    del password
    database = SecretStr(url.render_as_string(hide_password=False))
    engine = create_db_engine(database)
    with engine.connect() as db:
        db.execute(text("SET TRANSACTION READ ONLY"))
        identity = tuple(db.execute(text("SELECT current_database(),current_user,host(inet_server_addr()),inet_server_port()")).one())
        if identity != ("readbuddy_component4_pp1_demo", "readbuddy_c4_pp1_runtime", "127.0.0.1", 5432):
            raise ValueError("Wrong database identity")
        if db.execute(text("SELECT version_num FROM public.alembic_version")).scalars().all() != ["0008_c4_pp1_saved"]:
            raise ValueError("Wrong revision")
        active = db.execute(text("SELECT count(*) FROM users u JOIN user_roles ur ON ur.user_id=u.id JOIN roles r ON r.id=ur.role_id WHERE u.id=:id AND u.login_handle='c4_demo_learner' AND u.status='active' AND u.deleted_at IS NULL AND ur.revoked_at IS NULL AND r.code='learner' AND r.is_active"), {"id": UUID(account)}).scalar_one()
        if active != 1:
            raise ValueError("Fictional account not authorized")
    engine.dispose()
    engine = None
    os.environ["READBUDDY_PP1_ENABLED"] = "1"
    os.environ["READBUDDY_PP1_ACCOUNT_IDS"] = account
    settings = Settings(_env_file=None, app_env="development", database_url=database,
        jwt_signing_key=SecretStr(secrets.token_urlsafe(48)), log_level="WARNING")
    print("Verified PP1 database. Starting HTTPS on selected address, port 8443.")
    uvicorn.run(create_app(settings), host=bind, port=8443, ssl_certfile=cert,
        ssl_keyfile=key, access_log=False, log_level="warning", proxy_headers=False)
except KeyboardInterrupt:
    pass
except Exception:
    print("STOP: PP1 startup failed. No credentials displayed; review before retrying.")
    raise SystemExit(1) from None
finally:
    if engine is not None:
        engine.dispose()
    for name in ("READBUDDY_PP1_ENABLED", "READBUDDY_PP1_ACCOUNT_IDS"):
        os.environ.pop(name, None)
'@
# Encode public source only to preserve quoting on Windows PowerShell 5.1.
$pp1Encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($pp1Start))
uv run --frozen --project .\apps\backend python -c "import base64; exec(base64.b64decode('$pp1Encoded'))"
if ($LASTEXITCODE -ne 0) { throw 'PP1 HTTPS startup stopped. Review before retrying.' }
Remove-Variable pp1Start, pp1Encoded
```

APP_ENV, DATABASE_URL and JWT_SIGNING_KEY are explicit process-only Settings values;
dotenv is disabled. No private settings are printed. The signing key changes on
server restart, invalidating old access JWTs; sign in again if restoration fails.
No reload, multiple workers or proxy-header trust is enabled. Authentication and
production consent restrictions remain unchanged.

In a second terminal, validate chain, validity and IP/SAN with the public CA before
entering any account credentials. Do not use curl -k or accept certificate warnings:

```powershell
$pp1Host = Read-Host 'Same verified laptop IPv4'
$pp1Ca = Read-Host 'Public CA certificate absolute path'
curl.exe --fail --silent --show-error --cacert "$pp1Ca" "https://${pp1Host}:8443/api/v1/health/ready"
if ($LASTEXITCODE -ne 0) { throw 'HTTPS verification failed. Stop before login.' }
```

Expected response: HTTP 200 with status ready. This is not an authentication smoke
test. On iPhone verify the same HTTPS readiness URL without warnings, then use
https://<selected-ip>:8443/api/v1 in Expo Go and privately sign in. Select the
authorized learner and Connected sample (laptop). Preview is distinct from saving;
use Save Sample Progress, Refresh Saved Progress and the read-only row query above.
Production analytics must remain consent_required when evaluation is unavailable.
Guardian/Educator remain offline for PP1. Do not publish tokens or substitute
offline results for failed live requests.
