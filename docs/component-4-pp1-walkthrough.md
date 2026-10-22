# Component 4 PP1 demonstration

## Start and rehearse

From the repository root in PowerShell:

```powershell
Set-Location .\apps\mobile
Remove-Item Env:EXPO_PUBLIC_COMPONENT4_DEVELOPER_TOOLS -ErrorAction SilentlyContinue
yarn start:go --lan
```

Open the QR code in Expo Go on the same trusted Wi-Fi. Keep Metro running for the
development bundle. No FastAPI server, PostgreSQL connection, Ollama, Gemini or
production consent evaluator is needed for the demo. Do not choose Sign In for
Live Mode during PP1. That separate path can remain consent-blocked.

Use an Expo Go build compatible with the installed Expo SDK. Doctor on 22 October
2026 reports patch updates available: expo 57.0.30 -> ~57.0.31 and expo-sharing
57.0.23 -> ~57.0.24. Dependencies were not changed or warnings hidden. Rehearse on
the actual phone before deciding on an approved dependency update.

The prepared PP1 source is
`apps/mobile/src/features/learnerModelling/preview/pp1ReadingSessions.json`.
It is fictional, explicitly not verified Speech telemetry, and contains six completed
sessions in one comparable context. The original `connectedSessionExample.json`
reference fixture, independent role examples and Qwen3 report remain unchanged.

Generated artifacts and their integrity pins were regenerated with the existing
Component 4 Python analytics, longitudinal, recommendation and role-projector code.
No frontend analytical rules or recommendation thresholds were added. The six
readings intentionally demonstrate a visible descriptive change:

| Session | Correct / attempted | Active time | Accuracy | WPM | Hesitations per 100 words |
| --- | --- | --- | --- | --- | --- |
| 1 | 93 / 100 | 70 seconds | 93% | 85.71 | 5 |
| 2 | 94 / 100 | 65 seconds | 94% | 92.31 | 4 |
| 3 | 95 / 100 | 62 seconds | 95% | 96.77 | 3 |
| 4 | 96 / 100 | 60 seconds | 96% | 100 | 2 |
| 5 | 96 / 100 | 60 seconds | 96% | 100 | 2 |
| 6 | 96 / 100 | 60 seconds | 96% | 100 | 2 |

These are designed examples, not measured research results or proof that support
caused improvement. Sample N selects the first N sessions; it does not add N copies.
Selecting a scenario replaces the selected prefix. Recommendations remain advisory.

If a device saved an older artifact digest, the existing storage validator rejects
that stale journey. It does not silently apply a different dataset. Re-select a
current scenario and re-enter demo choices if the restore warning appears; rehearse
and save the intended profile/settings before presenting. No device data was changed
by this preparation. Reset Journey resets session selection, not authoritative data.

## Four-minute walkthrough

| Time | Actions | Suggested explanation |
| --- | --- | --- |
| 0:00-0:20 | Open Learner Home; point out Sample Data | "This is my standalone Component 4 prototype. All displayed learners and reading sessions are fictional." |
| 0:20-1:00 | Profile -> Edit Profile; select avatar; Reading Settings; change font/spacing/highlight; briefly show Feedback | "Profile and reading preferences are interactive local demo choices. Feedback stays separate from measured performance; no answers are submitted to a real session." |
| 1:00-1:30 | Home -> Reading Results; choose Sample 2 -> Update My Progress | "Component 4 receives reading measurements. This demonstration selects validated prepared scenarios, rather than pretending arbitrary phone inputs are instantly processed." |
| 1:30-2:10 | Profile -> Next: My Analytics; note two sessions and insufficient history; Add Next Sample until six (or return to Reading Results and select Sample 6) | "The same selected history drives the profile and charts. Comparisons use compatible sessions. Missing time/pause/replay measurements stay unavailable." |
| 2:10-2:40 | View Reading Tips -> Why This Tip? | "The Python engine proposes a harder reading level from the configured evidence rules. This is advisory and explains its evidence; it does not change another component's settings." |
| 2:40-3:15 | Next: My Reading Report -> Read Current Summary -> Open Saved AI Report | "The current summary is factual and not AI-written. The separate saved Qwen3 report was generated earlier from different sample evidence and locally validated. Opening it generates nothing new." |
| 3:15-3:35 | Download AI Report PDF -> iOS Save to Files | "This PDF exports the saved report on-device. It does not call a model or upload reading data." |
| 3:35-4:20 | Guardian tab, then Educator tab -> Alex Storybook | "Each role receives its own allowed projection. Alex follows this selection. Robin and Jamie are independent fictional examples. These views exclude Learner-only recommendations and engagement estimates." |
| 4:20-4:50 | Download Student Report; Back to My Students -> Download Class Report | "These Educator PDFs are evidence-grounded analytics reports, not AI-generated reports. Class statistics do not pool incompatible performance measurements." |

For a three-minute slot, show one PDF share sheet and explain the other exports.
Open and save the example PDFs before the presentation as a backup. Do not spend
the presentation signing in or configuring the backend. Keep Developer Details
collapsed. Show Sample 0/Reset Journey only if asked about missing evidence.

## Panel answers

- **What goes in and comes out?** Reading-session counts, durations, context,
  completion and available interaction counters go into the existing ingestion
  contract. Component 4 produces validated performance observations, comparable
  historical progress, explained advisory support decisions and factual report
  evidence. The demo replays prepared backend outputs without a live service.
- **Algorithms:** Accuracy is correct/attempted words; WPM uses attempted words and
  active duration; hesitation frequency uses the existing backend rate with display
  conversion to per-100 words. Missing denominators/measurements are not zero.
  Longitudinal comparisons keep task, difficulty and support contexts separate.
  The existing early/late comparison requires adequate evidence (six comparable
  valid observations); recommendation rules have their own three-session minimum.
  Fixed baseline and manual override/global lock take precedence. No rule is a
  clinical diagnosis or proven optimal personalization policy.
- **Engagement:** The displayed score, where available, is a versioned experimental
  research heuristic, not a scientifically validated attention/ability measure.
  It does not prove learning effectiveness or user acceptance. Actual research
  evaluation and usability/user-acceptance studies remain future work.
- **Database:** `reading_sessions` (28 columns) and
  `learner_reading_support_settings` (18 columns) use the shared SQLAlchemy Base,
  UUID keys, UTC timestamps and Alembic revision 0006. Native PostgreSQL integration
  and migration verification previously passed; no database operations are needed
  for this walkthrough. Demo preferences are not authoritative persisted settings.
- **Endpoints:** Authenticated GET progress, Guardian summary and Educator analytics,
  plus POST reading-sessions, exist under `/api/v1/learner-modelling`. Authentication,
  learner selection, refresh and logout were previously verified over real local
  HTTP. These are distinct from this offline presentation and its mocked UI tests.
- **Consent and integration:** Live analytics correctly deny access until the shared
  owner supplies approved learning-support consent evaluation and withdrawal
  semantics. Speech/Adaptive Reading telemetry mapping and full team integration
  remain pending. PP1 does not require or bypass those protections.
- **AI:** The saved report is genuine previously generated Qwen3 sample output that
  passed local factual validation. No fresh AI generation is claimed. Educator
  analytics PDFs and the current reading summary are deterministic. No new AI or
  class AI report is generated during the walkthrough.
- **FR01-FR14:** All eight proposal feature areas have demonstrable UI coverage;
  demo coverage is not production completion. Authoritative profile/support writes,
  feedback-to-real-session association, approved consent, full telemetry integration
  and research evaluation remain separate work.

## Verification and device limits

The PP1 offline regression disables fetch and traverses six-session learner results,
explanations, current/saved reports, Guardian and Educator views and PDF HTML builders.
Existing tests exercise profile/settings/feedback persistence, role isolation, native
print/share success and failure handling, reporting periods and safe pagination CSS.
Native print/share calls are mocked in automated tests. No new physical-device PDF
pagination or save confirmation is claimed. Inspect short student PDFs, the class
report and saved AI PDF on iPhone before PP1. PDF generation/sharing can require
multiple pages and OS-specific behavior even when HTML keep-together rules pass.

Regenerate prepared PP1 files only when intentionally changing the synthetic source:

```powershell
Set-Location .\apps\backend
uv run --frozen python -m app.modules.learner_modelling.connected_demo --development-synthetic-only --input ../mobile/src/features/learnerModelling/preview/pp1ReadingSessions.json --start 2026-01-01T00:00:00Z --end 2026-01-31T00:00:00Z --task independent_reading --tier intermediate --mode adaptive
uv run --frozen python -m app.modules.learner_modelling.role_scenarios --development-synthetic-only
```

These commands read/write only synthetic files; they do not access PostgreSQL or
an AI/network provider. Existing separate examples and saved AI snapshots are not
regenerated by them.
