# ReadBuddy - Component 4

**Project J26-IT-354:** Adaptive NLP-Based Speech & Reading Assistant for Children with Dyslexia

**Component 4:** Transparent Learner Model & Adaptive Learning Analytics

ReadBuddy is a four-member university research project. This feature branch presents
Component 4's individual contribution within the shared mobile and backend application.
It does not claim the other members' speech, document-processing or simplification work.

> Research prototype using fictional demonstration data. It is not a diagnostic tool,
> a clinically validated intervention, or evidence of improved reading outcomes.

## Overview

Component 4 helps children aged 9-12, guardians and educators understand recorded
reading performance and the evidence behind reading-support suggestions.

It combines a learner profile, deterministic analytics, explainable rule-based
recommendations and separate progress-reporting features. Reading settings remain
under human control; recommendations do not change them automatically.

## Research problem and proposed solution

Reading performance can vary between sessions. A single accuracy or speed value
cannot explain a learner's history, and sessions with different tasks, difficulty
or support conditions should not be treated as equivalent.

The proposed solution provides:

- Progress views based on comparable recorded sessions.
- Explicit missing-data and insufficient-evidence explanations.
- Reading tips supported by identifiable rules and available measurements.
- Understandable summaries for learners, guardians and educators.
- Separate, constrained AI reporting rather than AI-generated support decisions.

## Individual contribution

Component 4 contributes the following cross-stack implementation:

1. Validated reading-session and support-preference contracts.
2. Deterministic session and longitudinal analytics.
3. Advisory recommendations with rule reasons and decision evidence.
4. Learner, guardian and educator interfaces and report exports.
5. An isolated fictional-session persistence demonstration using PostgreSQL.
6. Evidence-constrained local AI report generation and related automated tests.

Shared authentication, learner relationships and consent are dependencies reused
from the project. Their ownership and approval remain with the shared-service team.

## Inputs and outputs

| Inputs | Outputs |
| --- | --- |
| Attempted/correct word counts | Reading accuracy, displayed as a percentage |
| Active reading duration in milliseconds | Reading speed in words per minute (WPM) |
| Available hesitation counts | Hesitations per 100 attempted words where supported |
| Session history and reading context | Descriptive comparisons and supported trends |
| Reading preferences and observed support | Profile information and explainable reading tips |
| Validated progress evidence | Deterministic summaries and optional validated AI reports |

Missing measurements remain unavailable; they are not replaced with zeros.
Component 4 consumes measurements. The sample journey does not measure a child's
spoken reading or implement speech recognition.

## Simple system workflow

```text
Validated session measurements and reading context
                      |
           Deterministic Python analytics
                      |
             Validated progress evidence
               /                 \
     Rule-based reading tips     Progress reporting
               |                 |             \
       Reasons and evidence   Current summary   Optional local AI
               |                               |
               |                      Factual output validation
               \_________________  _____________/
                                 \/
                      UI review and PDF export
                                 |
                     Human-controlled settings
```

Recommendations and reporting are separate processes that may share evidence.
The AI model does not calculate the core metrics or decide the reading tips.

## Main features

| Feature | What the prototype provides |
| --- | --- |
| Learner Home | Compact session, accuracy and WPM summaries |
| Reading Results | Before Reading / Samples 1-6, metrics and progress actions |
| Learner Profile | Reading history, preferences and analytics navigation |
| Reading Analytics | Context-aware trends, missingness and evidence limitations |
| My Reading Tips | Existing recommendation, available evidence and explanations |
| Reading Settings | Font size, spacing, highlighting and an audio preference |
| My Reading Report | Current summary and a separately labelled saved AI report |
| Guardian Dashboard | Fictional progress summaries and Guardian report export |
| Teacher Dashboard | Separate fictional student histories and class/student reports |

Native exports use PDF generation and sharing. Browser exports open a dedicated
report window with Print / Save as PDF. Export does not make another AI request.
The audio preference does not imply that playback is connected.

## Technology stack and architecture

- **Mobile/web:** React Native, Expo SDK 57 and TypeScript.
- **Backend:** Python 3.13, FastAPI and Pydantic.
- **Persistence:** PostgreSQL, SQLAlchemy, psycopg and Alembic.
- **Local AI:** Ollama with the configured Qwen3:4B model allowlist.
- **Reports:** Expo Print/Sharing and browser HTML printing.
- **Checks:** pytest, Jest, TypeScript, ESLint, Ruff and mypy.

Component 4 uses one shared FastAPI backend and shared database infrastructure.
Its [mobile navigation](apps/mobile/src/features/learnerModelling/navigation/LearnerNavigation.tsx) and
[backend router](apps/backend/app/modules/learner_modelling/router.py) form one cross-stack feature.
Production session storage and synthetic PP1 storage remain separate.

## Rule-based recommendations versus GenAI reporting

**Reading Tips are deterministic and rule-based.** Decisions use available accuracy,
pace, hesitation and contextual evidence, with sufficient-session and override checks.
Rules expose reasons and versioned research thresholds; they are not clinical cutoffs.
No automatic support or difficulty changes are applied.

Low/Medium/High support classification is not implemented. Existing support modes
and difficulty tiers must not be presented as diagnoses or validated support levels.

**GenAI reporting is separate.** The local transport can call Ollama using `qwen3:4b`.
The current factual validator requires the approved statement catalogue unchanged;
it rejects unsupported additions, altered values, omissions and mismatched evidence.
This is constrained reporting, not unrestricted educational or medical advice.

The current deterministic summary, bundled saved AI snapshot and optional newly
generated synthetic report are distinct. Demo Mode does not automatically invoke AI.
A saved snapshot's model metadata does not prove a fresh model execution.
Experimental cloud utilities are not presented here as application integrations.

## Demonstration modes

| Mode | Data and access boundary |
| --- | --- |
| Offline Demo | Fictional bundled scenarios; ordinary screens need no backend |
| Connected PP1 | Authenticated, allowlisted fictional account and isolated PostgreSQL sample storage |
| Protected Live | Authorized learner access; production consent remains deny-by-default |
| Optional synthetic AI | Explicit development opt-in; fixed fictional report fixture and local Ollama |

Connected PP1 supports **Save Sample Progress -> commit synthetic rows -> refresh
analytics**. Retries must not duplicate sample sessions. It does not write fictional
measurements to production `reading_sessions` or fabricate consent events.
Guardian and educator demonstrations retain their offline fictional-data boundary.
A connected request failure must not silently switch to offline data.

## Setup and demonstration

Run these commands from the repository root using the existing Yarn lockfile:

```powershell
yarn --cwd .\apps\mobile install --frozen-lockfile
yarn --cwd .\apps\mobile start:go
```

For Expo Web, use `yarn --cwd .\apps\mobile start --web` instead.
Use a compatible Expo Go installation and a reachable local network for iPhone testing.

Start with Demo Mode: open Reading Results, compare selected fictional samples,
update local progress, then review Profile, Analytics, Tips and Reports.
Do not describe local demo updates as PostgreSQL saves.

Connected PP1 requires the separately approved database, runtime role, fictional
account, schema and fixture. Follow the existing
[standalone setup guide](docs/component-4-standalone-pp1-setup.md) and
[saved-progress guide](docs/component-4-pp1-saved-progress.md).
Do not rerun provisioning, migrations or seeding against an existing environment.

The backend requires private `DATABASE_URL` and `JWT_SIGNING_KEY` configuration.
Use a non-superuser runtime role and trusted HTTPS; never commit credentials or
bypass certificate validation. The mobile API address must end in `/api/v1`.
Successful login is not permission to access consent-protected learner analytics.

Optional synthetic generation also requires explicit development flags, an already
available local Ollama model and the fixed-fixture reporting configuration.
Real model availability and successful generation were not verified in this README review.

## Testing and validation

```powershell
uv run --frozen --project .\apps\backend python -B -m pytest apps/backend/tests/unit -q -p no:cacheprovider
yarn --cwd .\apps\mobile test
yarn --cwd .\apps\mobile typecheck
yarn --cwd .\apps\mobile lint
git diff --check
```

Backend work also uses Ruff, formatting and mypy checks. See the
[backend tool configuration](apps/backend/pyproject.toml) and
[mobile scripts](apps/mobile/package.json).

Database integration/migration tests require explicit approval and an exclusively
disposable test database. Never run reset tests against development or PP1 demo data.
No test suite was rerun for this documentation change, and no new pass count is claimed.
Mocked tests do not establish real model execution, device usability or specialist validation.

## Limitations and future work

- Demonstration data is synthetic; no real-child evaluation or clinical validation is claimed.
- Shared production consent evaluation is incomplete and remains fail-closed.
- Recommendation thresholds and experimental engagement estimates need specialist review.
- Engagement estimates must not be described as validated attention or ability scores.
- Real reading measurement capture and team-wide integration remain separate dependencies.
- Device networking, accessibility, certificate trust and report sharing need manual checks.
- Participant research requires approved ethics, consent and withdrawal procedures.
