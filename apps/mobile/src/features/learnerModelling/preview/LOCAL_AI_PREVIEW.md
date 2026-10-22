# Synthetic local AI report preview

This offline bridge is owned by Component 4. It never changes dashboard providers,
contacts Ollama from the phone, or enables production learner reports.

The separate fixed fixture covers 1–31 January 2026 (end exclusive). It is not the
mobile dashboard's October fixture. Dashboard 7/30/90-day controls do not generate
or filter this saved report. The screen states that distinction explicitly.

## Generate on the developer computer

From `apps/backend`, with the loopback Ollama server and local `qwen3:4b` available:

```powershell
$env:APP_ENV = "development"
$env:READBUDDY_SYNTHETIC_OLLAMA_ENABLED = "1"
$env:OLLAMA_REPORT_MODEL = "qwen3:4b"
$env:OLLAMA_REPORT_TIMEOUT_SECONDS = "120"
uv run --frozen python -m app.modules.learner_modelling.local_report_snapshot --allow-ollama-request --write-mobile-snapshot
```

This command explicitly authorizes one synthetic local request, revalidates all
statements against the deterministic learner fixture, and atomically exports
`localReportSnapshot.json` in this directory. A failed generation does not export
anything or alter an older snapshot. Replacing a nonempty snapshot requires adding
`--replace-existing`. Check `written: true` and the generation timestamp; an older
file is never proof that a new generation succeeded.

Only approved statement text, fixed reporting dates and synthetic source metadata
are exported. No learner/session identifiers, prompts, internal references or raw
Ollama envelopes are exported. `syntheticReportDisplayContract.json` is the static
approved display catalogue, not an AI generation. Mobile rejects text outside that
catalogue, missing statements, mismatched roles, extra fields and invalid metadata.
This local check is not cryptographic provenance or authentication; never use this
workflow as a production trust boundary.

## View on iPhone / Android

From `apps/mobile`, run `yarn start:go` (use `--clear` when refreshing bundled JSON).
Open the development app in Expo Go, select the Learner demo, open **AI Progress
Report**, then tap **View saved local AI snapshot**. No public environment variable,
shared configuration change, endpoint or laptop Ollama network exposure is needed.
Only Metro/Expo needs the normal development connection to the phone.

The explicit opt-in is local to this screen visit. The saved view shows
**SYNTHETIC LOCAL AI PREVIEW — NOT REAL LEARNER DATA**, **OFFLINE SNAPSHOT**, source,
model, UTC generation time and all approved statements. It never says the report was
just generated. Return to the deterministic demo with **Return to demo report**.
Missing/invalid snapshots show an unavailable notice and the separately labeled
existing deterministic report. Disable or leave the preview to return to normal.

The opt-in and snapshot reader are gated by `__DEV__`, demo mode and learner role.
Release builds cannot select this snapshot; guardian/educator screens cannot load
it. The artifact contains synthetic data only even if packaged by Metro. Existing
live-provider unavailability and no-live-to-demo fallback are unchanged. There is
no real AI generation button, PDF export, authentication, consent integration or
production learner data access here.
