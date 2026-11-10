# Project status and ChatGPT handoff

Prepared on 5 November 2026 from the local repository at commit `39496b5`.
This is a source review with local checks, not a production readiness audit.

Copy the following text into ChatGPT:

---

Act as a senior software engineer and research engineering mentor. Help me continue
my existing project from the verified state below. Start with a gap assessment and
a small, prioritized next sprint with acceptance criteria. Do not assume missing
features already exist or recommend rebuilding the implemented foundation.

## Project and current stage

My university research project is **Adaptive NLP-Based Speech & Reading Assistant
for Children with Dyslexia**, project ID **J26-IT-354**, student ID **IT22081766**.

The current stage is a backend prototype with several implemented educational
reading workflows and separate PDF/OCR research evaluations. There is no mobile
application yet. Speech assistance, text simplification, and automated learner
adaptation remain future work. There is no demonstrated clinical effectiveness
or learner-outcome validation in this status review.

## Architecture and stack

- One FastAPI modular monolith at `apps/backend`, with REST APIs under `/api/v1`.
- One PostgreSQL application database per environment, shared SQLAlchemy Base,
  engine/session infrastructure, and model registry.
- Python 3.13, Pydantic, SQLAlchemy 2, Psycopg, Alembic, JWT, Argon2, and pypdf.
- Backend dependencies use `uv`, `pyproject.toml`, and `uv.lock`.
- UUID keys and timezone-aware UTC timestamps; separate API schemas and ORM models.
- Nine migrations in a single source history ending at `0009_ocr_review_workflow`.
  The currently running database revision was not checked during this review.
- Docker Compose for local backend/PostgreSQL; GitHub Actions configures tests,
  static checks, migration/schema checks, Compose validation, and image building.
- Planned React Native/TypeScript mobile app and generated TypeScript API client
  are documented placeholders only.

## Implemented application capabilities

| Area | Current scope |
| --- | --- |
| Authentication | Login, refresh, logout, current-user lookup, roles and session lifecycle |
| Learners | Authorized learner listing/profile reads and preference reads/updates, with role-specific access |
| Identity and consent | Database/service foundations for identities, relationships, grants and consent evidence; not a complete public onboarding interface |
| Reading assessments | Instructor-observed sessions, completion/abandonment/history, reading speed, accuracy and optional comprehension metrics |
| English reading materials | Pasted text, immutable revisions, explicit deterministic normalization/segmentation/processing, stored measurements and profiles |
| PDF extraction | Private upload, embedded-text extraction, extraction evidence/provenance, bounded execution and publication workflow |
| OCR review | Schema and internal instructor review/submission/acceptance/rejection services with transaction and concurrency protections |

Text profiles describe text characteristics. They do not establish suitability
for an individual learner. Reading scores are educational observations, not diagnoses.
Assessments do not currently transcribe or score recorded speech automatically.

OCR has no public endpoint or enabled production engine. Accepted reviewed OCR text
can become an immutable revision through internal services; this does not constitute
an operational end-to-end OCR feature. PDF `ocr_required` means OCR is needed,
not that OCR has occurred. PDF operations need private storage/runtime configuration
beyond the default Compose setup.

## Research progress and limitations

Research is isolated under `research/` with separate dependencies. These are
historical repository reports, not experiments rerun for this status review:

- PDF evaluation reports 22 development and 44 held-out fixtures. Held-out raw
  character error rate was 4.9223%, and word error rate was 5.4115%. Four accepted
  two-column documents had reading-order errors. Correct routing status does not
  prove correct reading order or complete visible-text extraction.
- OCR evaluation reports 48 held-out cases per engine, comparing Tesseract and
  PaddleOCR. Reported character/word error rates were 12.1174%/13.0901% for
  Tesseract and 9.5196%/13.6266% for Paddle. Neither engine was recommended for
  automatic production acceptance; future integration should require review.
- These small, specific evaluation corpora do not establish universal accuracy.
  Preserve frozen held-out results; do not tune against them or rerun them casually.

## Missing or incomplete

- Mobile UI and generated API client.
- Public account registration/administration and a complete user onboarding flow.
- Production OCR execution, public review APIs/UI, and runtime qualification.
- Speech recording/recognition/assistance, simplification, learner modelling,
  automated adaptation and numeracy business functionality.
- End-to-end client usability/accessibility validation and evidence of learning benefit.
- Production deployment and operational readiness have not been established here.

The generic documents, speech, simplification, learner-modelling and numeracy
module directories contain placeholders. Existing PDF functionality lives under
reading materials; a directory or mounted empty router is not a finished feature.

## Verification on 5 November 2026

Using the existing local backend virtual environment:

- Ruff lint: passed.
- Ruff formatting: passed, 154 files already formatted.
- Strict mypy: passed, 97 source files.
- pytest: 358 passed, 856 skipped, one Starlette/httpx deprecation warning.
- Test database environment variables were explicitly removed for this run to
  avoid touching an existing database. Database-dependent tests were skipped.
- Full disposable-PostgreSQL integration tests, migration execution/schema drift,
  live API workflows, Docker build and remote CI status were not verified here.
- Dependency lock synchronization and research artifact hashes were not rechecked.

The presentation guide records earlier successful synthetic login, learner lookup,
material creation and processing demos. Those are historical observations, not
proof that the current services or demo grants are still usable. The guide says
the instructor grant lasts seven days; check its validity before the next demo.

## Recommended next work

1. Establish a fresh baseline: run the complete suite against disposable PostgreSQL,
   verify migration head/schema drift, and repeat the synthetic authenticated demo.
   Acceptance: checks pass and actual results/limitations are recorded.
2. Choose one next deliverable: a usable client for existing reading workflows,
   or the next bounded OCR integration phase. Avoid starting all future modules.
3. If client work is explicitly approved, build one flow: login → authorized learner
   selection → pasted reading material → processed text profile. Generate API types
   from OpenAPI and validate access errors, session expiry and accessible controls.
4. If OCR is prioritized, retain explicit instructor review, define engine/runtime
   boundaries and public contracts, and qualify execution before enabling deployment.
5. Treat PDF column-order errors as a known quality gap and define review/routing
   acceptance criteria before claiming dependable multi-column support.
6. Evaluate speech, simplification and adaptation as separate research questions
   with explicit metrics and promotion criteria before production integration.

These are recommendations, not authorization to scaffold mobile or add features.

## Engineering constraints

Preserve existing work; do not commit or push automatically. Keep one backend and
one application database. Use Alembic for schema changes with one migration head.
Modules must use public service interfaces rather than write another module's tables.
Use synthetic learner data, enforce learner-level authorization, minimize child data,
and never commit secrets, recordings, datasets, dumps or model checkpoints.
Do not import research code into production. New backend logic needs meaningful
tests including failure paths, plus Ruff, formatting and mypy checks. Keep mobile
as a placeholder until explicitly requested. Do not add business features during
foundation-only work. Never implement diagnosis logic or label scores as diagnoses.

Please distinguish implemented code, historical evidence, newly verified behavior,
and proposed work. Do not invent a completion percentage without a defined scope.

---

## Repository evidence and working-tree notes

- [Project overview](../IT22081766_README.md)
- [Presentation/demo guide](presentation-demo.md)
- [API composition](../apps/backend/app/api/router.py)
- [OCR review service scope](ocr-review-workflow.md)
- [PDF evaluation report](../research/pdf_extraction/EVALUATION.md)
- [OCR held-out report](../research/ocr_evaluation/HELDOUT_RESULTS.md)
- [CI configuration](../.github/workflows/ci.yml)
- [Engineering rules](../AGENTS.md)

Before this review, Git showed `README.md` deleted and `IT22081766_README.md` and
`docs/presentation-demo.md` untracked. Those changes were preserved. Decide whether
the root README removal/rename is intentional before preparing a commit; some
existing documentation may still assume a root README. This handoff document is
the only source/documentation addition made for this review.
