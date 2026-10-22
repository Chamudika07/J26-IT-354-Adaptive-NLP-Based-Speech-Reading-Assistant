# Developer synthetic Reading Session Test

This is not a production persistence service or an authoritative Speech DTO adapter.
Only the Learner demo in development builds exposes the feature. No storage is read
on startup, role entry or live-provider entry. Re-entering requires explicit Load.

Open Try a Reading Session, enter made-up raw counts and durations, then Save. Save
appends a new UUID and verifies read-back before confirming success. Exact UUID retries are idempotent; conflicting edits are rejected. No correction/upsert policy is invented.
Load validates the entire file, never dropping invalid rows. Clear deletes only the
namespaced file and verifies absence. Reset input restores form examples, not storage.
The default UUID is an example; change its final digits for each additional session.

Inputs mirror existing ReadingSessionIngest scalar invariants: UUID, aware UTC start
and end, task/difficulty/support context, attempted/correct/target words, active/total
milliseconds, optional hesitation/pause/replay counts and optional total pause milliseconds.
Completion choices are Finished (completed), Stopped early (abandoned) and Interrupted. No
learner/document identity is accepted; these records are NOT ingestion API payloads.
The simulator requires canonical UTC ISO timestamps with milliseconds (e.g.
2026-10-20T10:00:00.000Z), nonnegative safe integers capped at one billion, and at most
100 records. Hesitation blank is missing, not zero. Future/out-of-window records may
be stored but do not appear in the selected reporting window.

Formula sources: Component 4 analytics.py calculate_reading_accuracy,
calculate_words_per_minute and calculate_hesitation_frequency. Accuracy is correct /
attempted (missing for zero attempts); WPM uses attempted words and active minutes
(missing below 1000 ms); hesitation is events / attempted word (missing for absent
count or zero attempts). These mobile display calculations are not verified backend
telemetry or recommendation evidence. Contexts are shown per session, never pooled
into a trend. The 7/30/90-day window ends at successful Load/Save time, end exclusive;
selection and sorting are deterministic by UTC start then UUID.

Save/Load selects separate Home/Progress displays. Suggestions explicitly report
unavailable rather than reusing frontend demo recommendations. Other feature areas
remain clearly separate demos and pinned snapshots; saved AI reports do not update.
Return to dashboard demo deselects test evidence without deleting it. Role switch,
live mode, failure state or feature unmount removes in-memory selection, not the
synthetic file. Temporary support/feedback drafts use their own independent store.

Storage uses the already installed expo-file-system 57.0.7 (Expo's dependency), via
its native legacy API, without adding dependencies. The single app-private Documents
file is readbuddy-component4-developer-synthetic-v1.json. It contains a versioned,
synthetic:true, verifiedTelemetry:false envelope. Reads reject oversized files,
unknown/extra fields, malformed values and duplicate identities as a whole. No
prompts, personal text or real learner data belong here. Storage errors are sanitized;
Save confirmation requires exact validated read-back. A failed/interrupted write may
require Clear to recover. No crash-atomic or multi-process transaction guarantee is
claimed. Expo Go/project sandbox changes, app uninstall or app-data clearing can
remove records. This is not a permanent learner store or a backup/export service.

On iPhone: open the development Expo Go project, Learner, Reading Session Test. Save,
check Home and Progress, fully close/reopen the same project, open the test screen and
Load. Verify the same metrics. Switch roles and back: no automatic Load. Clear and
reopen/Load to verify zero records. Repeat with a new UUID for another context.
Unit tests simulate restart with persistent mocked native storage across unmount/new
store instances, and test native iOS/Android paths. Physical-device restart/storage
behavior has not been verified by the implementation agent.

Real integration still requires finalized Speech/Adaptive Reading measurements,
approved authorization/consent and learner/session binding, production persistence
and API contracts, and backend validation/recommendation processing. This developer
file must never become a live-provider fallback.


## Expanded telemetry demonstration

The screen now uses "Try a Reading Session" and "Demo Mode — Sample Reading Data".
UUID and UTC start/end fields are under Show developer details; existing IDs are not
silently changed or overwritten. Blank optional hesitation/pause/replay values are
null, while 0 records an observed simulated zero. Pause duration is milliseconds and
must not exceed total duration. No additional pause-count/duration relationship is
invented beyond existing backend contract invariants.

Files now write envelope version 2 using the same namespaced file and storage adapter.
Version-1 records remain supported: their documented completed state is preserved,
and newly supported measurements are explicitly missing. Load upgrades only the
in-memory shape and does not rewrite stored records. The next explicit Save writes
version 2. Unknown versions, malformed fields and duplicate IDs still fail closed.

Home/Progress synthetic previews show completion, pause/replay values and a developer
experimental engagement diagnostic. It mirrors analytics.py's default versioned
formula: completion weight .50, active-time weight .30, pause-efficiency weight .20.
Interrupted completion uses half the attempted/target fraction; abandoned uses that
fraction; completed uses 1. Missing pause duration or nonpositive target/total duration
prevents a score. Pause/replay counts are recorded but do not enter this formula.
The display calls the diagnostic an unvalidated research heuristic, not attention,
ability, health or effectiveness. It is not added to ordinary role dashboards, report
snapshots or recommendation decisions. Backend ingestion remains disconnected.

To demonstrate engagement on iPhone, use 100 attempted/90 correct/100 target words,
40000 active ms, 50000 total ms, 10000 pause ms, and Finished completion. Save, then
open Progress: the experimental score should be .84. Blank pause duration instead
must show unavailable. Use a new UUID in developer details for another record.
Save/Load/Clear/Reset semantics and production/live/role gates remain unchanged.


## Connected standalone offline round trip (STEP 184)

1. In the development Learner demo, open Try a Reading Session. Save sample records
   with distinct UUIDs (Show developer details), consistent context and explicit
   completion states. Only stored records are exported, never unsaved form edits.
2. Tap Export saved sample sessions. In the native share sheet use Save to Files or
   a local transfer to your computer. Closing sharing does not confirm a saved copy.
3. From apps/backend run the opt-in command below. Replace --input and the explicit
   UTC reporting window/context with those matching your exported data. No server,
   database, Speech service or AI model is invoked.

```powershell
uv run --frozen python -m app.modules.learner_modelling.connected_demo --development-synthetic-only --input "C:\path\readbuddy-component4-sample-sessions.json" --start 2026-10-01T00:00:00Z --end 2026-11-01T00:00:00Z --task independent_reading --tier intermediate --mode adaptive
```

To reproduce the bundled approved January example instead:

```powershell
uv run --frozen python -m app.modules.learner_modelling.connected_demo --development-synthetic-only --input ../mobile/src/features/learnerModelling/preview/connectedSessionExample.json --start 2026-01-01T00:00:00Z --end 2026-01-31T00:00:00Z --task independent_reading --tier intermediate --mode adaptive
```

4. The explicit command writes only connectedSessionInput.json (synthetic source
   sidecar for backend reproducibility, not imported by the UI),
   connectedSessionPreview.json (minimized learner projection) and
   connectedSessionContract.json (build-time fixture pin). It leaves the independent
   Qwen3 and recommendation snapshots unchanged. JSON fields are closed; all records
   must validate, including excluded records. Unknown schema versions, invalid units,
   naive timestamps, inconsistent counts/durations and duplicate identities reject
   the entire import. The envelope accepts no learner identity; mapping uses a fixed
   synthetic learner UUID internally and never exports that UUID.
5. Reload the Expo project (restart Metro with yarn start:go --clear if necessary),
   open Try a Reading Session, and tap Select connected backend preview. Selection
   is opt-in after each role change/restart. It does not compare against or replace
   your device store; the displayed dates/context/counts identify the imported file.
6. Home, Progress, Suggestions and Profile now use exactly one artifact's period,
   generation timestamp, context, analytics and advisory recommendation. Global
   dashboard filters do not regenerate that artifact; import a different explicit
   window/context to change it. Return to independent demo deselects the artifact.

Both analytics and recommendations use the same completed sessions in the selected
[start, end) UTC window and exact task/tier/mode context. Other/incomplete sessions
are explicitly counted as excluded. Longitudinal calculations, missing-evidence
handling, recommendation composition and minimized presentation reuse actual backend
code. Support preferences come from the existing approved synthetic scenario, with
explicit context mode/tier; they are not inferred authoritative device preferences.
Insufficient or empty evidence emits no proposed recommendation. No settings are
applied. Editing/saving/loading/clearing device sessions invalidates the in-memory
connected selection; export/import/select again to refresh backend results.

Mobile accepts only the generated artifact matching the build-time pin. This is an
offline synthetic fixture contract, not authentication, cryptographic provenance or
a production JSON import API. Backend tests recalculate the artifact from its source
sidecar and metadata. Regeneration deliberately replaces these three connected-demo
files and should be reviewed. The source sidecar is synthetic test material only.
No arbitrary file picker or HTTP endpoint is added; the current workflow requires a
computer and Expo reload. Keep personal information out of all input files.

Settings/Feedback remain their own temporary sample previews. Guardian/Educator
cannot access this learner artifact and retain separate existing demo data. The
saved Qwen3 report and PDF remain independent; they are not derived from these
entered sessions and no AI generation occurs in this round trip. Production/live
providers cannot select the artifact or export developer storage. Native file/share
operations and iPhone rendering still require physical-device verification.


## Interactive connected demonstration (current behavior)

Use **Start prepared sample replay** for an immediate, explicitly labelled offline
fixture demonstration. The CLI now emits a validated backend result for every
completed-session prefix, including zero sessions. **Add next prepared sample
session** advances through that prepared file. It never calculates or substitutes
form inputs. The UI shows session counts, backend metric evidence, session history,
transparent advisory suggestions and deterministic report preparation from the same
selected prefix. Use the Reading Session / Analytics / Progress / Suggestions /
Report actions to follow the flow. Dates are readable; raw timestamps, digest,
prepared source statements and experimental diagnostics sit behind calculation
details. The primary interface does not expose UUIDs.

Custom form inputs use the existing Save / Export / computer import / reload /
Select connected backend preview path. Raw saved views now explicitly say backend
calculation is pending; they do not run the frontend metric/engagement helpers or
show unrelated profile/report fixtures. There is no approved in-process Python
engine or HTTP endpoint, so arbitrary form edits cannot instantly recalculate the
backend. This limitation is visible in the form.

Exact saved-session retries return the existing file without adding an observation
or writing again. Conflicting UUID payloads and invalid form values preserve prior
valid results. Malformed/unavailable storage still fails closed with no stale
calculated result. Reset sample replay selects the zero-session backend artifact.
Reset connected demo clears the saved developer file and in-memory selection, never
an independent AI snapshot or PDF. The old Clear action remains available. Reload or
role changes require explicit selection again.

Connected artifact schema v2 adds chronological, identifier-free session history
and factual report preparation via the existing backend report evidence builder.
Experimental engagement is calculated by the actual backend and shown only as a
synthetic developer diagnostic in expanded history details; this does not modify
approved role dashboard projections. Report preparation is deterministic, not AI
output, and offers no current-session PDF. Its explicit Open independent saved AI
report and PDF action preserves the January Qwen3 snapshot and existing PDF gates.

The CLI also writes connectedSessionReplay.json and its separate build-time contract
pin. Both are derived from the validated source sidecar and same explicit reporting
window/context and generation timestamp. Re-running the documented command refreshes
full and prefix artifacts together. There is no phone-to-backend or AI network call.
The initial bundled replay has the approved six comparable January sample sessions;
after importing another sample file, replay represents that file's eligible subset.

iPhone walkthrough: Learner > Try a Reading Session > Start prepared sample replay >
Home > Add next prepared sample session. Open Progress and Profile to see the one
session; Suggestions must remain unavailable with insufficient evidence. Add more
prepared sessions until the backend allows a comparable trend/recommendation. Open
Report for the same prefix's deterministic facts; opening the independent AI report
must explicitly show that it is not derived from these samples. Reset and repeat.
No physical-device verification is claimed for these new replay controls.


## STEP 248: custom sample calculation workflow

Immediate Python calculation on iPhone is not available: no approved execution
bridge or HTTP endpoint exists. No endpoint or authorization bypass was added.
The primary Calculate My Results action validates and saves the current
sample, then exports saved samples through native sharing only if saving succeeds.
Invalid or conflicting input does not export older records as new results. The UI
states computer calculation is required. New sample session chooses a fresh demo
UUID; Save/exact retries still reuse the storage contract and do not inflate counts.

1. In Learner demo, open Try a Reading Session and enter sample raw counts/durations.
   Durations remain milliseconds; blank optional counts mean missing, not zero.
2. Tap Calculate My Results. Save the exported JSON locally through the share
   sheet and transfer it to your development computer. No server upload is performed
   by the app. Use New sample session before entering another distinct observation.
3. From apps/backend, calculate with the real Component 4 services:

```powershell
uv run --frozen python -m app.modules.learner_modelling.connected_demo --development-synthetic-only --input "C:\path\readbuddy-component4-sample-sessions.json" --derive-window-context
```

The explicit flag derives the window from earliest input start through latest end
plus 1 millisecond (end-exclusive), and requires one shared task/tier/mode. It uses
validated input timestamps, not the current clock. Empty/mixed-context files require
the existing explicit --start/--end/--task/--tier/--mode workflow. Combining explicit
filters with derivation is rejected. Existing CLI opt-in and input validation remain.

4. Reload Expo, open Developer Details in Try a Reading Session and explicitly select
   connected backend preview. Home, Progress, Profile, Suggestions and deterministic
   report preparation now select that same calculated artifact. Prepared replay is
   refreshed from the imported file too; it no longer represents the old example.
5. Verify measured values and period before presenting. Use Clear to delete stored
   phone inputs; reset/reselect demonstration results explicitly. No saved Qwen3
   report/PDF is regenerated and no Guardian/Educator fixtures are replaced.

Backend reuse: ReadingSessionIngest validation, analytics formulas, longitudinal
observations, project_learner_progress, recommendation composition/presentation,
and deterministic report evidence. No frontend recommendation rules were added.
No physical-device or instantaneous custom-processing verification is claimed.


## STEP 252: customer view and explicit developer interface

Normal Learner navigation opens Reading Session with the prepared sample journey
only. Custom input, export/import, calculation commands, artifact selection and
Developer Details are hidden by default. The connected reading summary has its own
Read reading summary control, so facts do not require opening developer tooling.
The separate saved Qwen3 report/PDF remains available with its own source/period.

To explicitly enable the existing Learner developer interface, from apps/mobile:

```powershell
$env:EXPO_PUBLIC_COMPONENT4_DEVELOPER_TOOLS = "1"
yarn start:go
```

Restart Metro/reload the app after changing this build-time flag. This flag is not
a secret or authentication mechanism. It is checked together with __DEV__, and
existing Learner/demo provider gates still apply. It never enables production APIs
or a developer route. Role switching alone cannot enable it. Guardian/Educator do
not expose the Learner tools. Role/provider changes retain existing draft/selection
clearing behavior. Tools are normal-flow controls, not floating overlays.

For customer-facing demonstration, remove the flag and restart Metro:

```powershell
Remove-Item Env:EXPO_PUBLIC_COMPONENT4_DEVELOPER_TOOLS -ErrorAction SilentlyContinue
yarn start:go
```

No new storage, network calls or dependencies are introduced. Raw error/provider
bodies are never displayed. Custom input calculations still require the separate
computer workflow; the prepared journey is not a calculation of user-entered data.


## STEP 269: custom-input lecturer flow

Trusted phone-to-laptop HTTPS and restricted LAN access are not verified. No network
endpoint is enabled. Calculate My Results validates and saves inputs, then opens
native JSON sharing; the app does not calculate Python results on iPhone.

1. Enable the development tools flag above and open Learner > Reading Session.
2. Enter sample counts, milliseconds and context. Use New sample session for each
   additional session, then Calculate My Results. Save/share the JSON to the laptop.
3. Run the connected_demo command above with that exported file. Keep one context
   for automatic window derivation. The importer validates before writing artifacts.
4. Reload Expo, return to Reading Session, then Open calculated sample results.
   Until the laptop import/reload, this button selects the separate bundled example.
5. Home, Profile, Progress, Suggestions and Reading Progress Summary now share the
   selected artifact. The selected artifact is restored only while its stored digest
   matches the bundled validated result; replacement artifacts require re-selection.
6. Reset Demo Data clears demo choices and result selection, not the separate custom
   input file. Clear on Reading Session removes that input file. Neither regenerates
   the saved Qwen3 report or changes its PDF.

Sharing cancellation is not an export confirmation. Storage/export failures stay
visible and no successful calculation is claimed. Guardian/Educator remain separate.
