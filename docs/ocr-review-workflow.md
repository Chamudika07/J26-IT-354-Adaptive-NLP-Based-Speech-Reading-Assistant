# OCR review workflow — Phase 1

Production OCR is review-first. The research conclusion is that neither evaluated
engine supports automatic acceptance. OCR output is candidate evidence, not trusted
reading material. This workflow makes no medical or dyslexia diagnostic claims.

Phase 1 adds database and domain foundations only. It includes no OCR engine,
rasterizer, worker, HTTP OCR endpoint, or runtime enablement. Production OCR remains
disabled until Linux qualification and the subsequent implementation phases pass.
Research artifacts and dependencies are unchanged.

## Routing and state transitions

Direct PDF extraction always runs first. An OCR request must reference an immutable
terminal `embedded_pdf` run for the same source:

| Direct status / outcome | OCR request mode |
| --- | --- |
| `ocr_required` / `image_without_text` | `eligible` |
| `needs_review` / `ambiguous_content` | Explicit `review_comparison`, with a nonblank reason |
| Any failed outcome, running run, or extracted run | Ineligible |

Encrypted, malformed, unsupported, page, integrity, and resource failures never
become OCR parents. An OCR run cannot parent another OCR run.

Future OCR runs transition from `running` to `failed` or `review_required`. Success
must atomically publish immutable page evidence and exactly one `pending` review.
It creates zero revisions automatically. Pending reviews can be submitted or
rejected. Submitted reviews can be resubmitted, explicitly accepted, or rejected.
Accepted and rejected reviews, including their page records, are immutable.

Explicit instructor acceptance will create exactly one immutable `ocr_reviewed`
revision in the same transaction as the decision and source/material binding.
No acceptance service or endpoint is implemented in this phase.

## Storage and provenance

Migration `0009_ocr_review_workflow` follows `0008_pdf_text_extraction` in the existing
single PostgreSQL migration history. Models use the shared SQLAlchemy Base, UUID
keys, timezone-aware timestamps, and existing version conventions.

* `reading_material_extraction_runs`: adds `extraction_method`,
  `parent_extraction_run_id`, `request_id`, `request_sha256`, `request_mode`,
  `request_reason`, `execution_manifest`, and `execution_manifest_sha256`.
  Existing rows default to `embedded_pdf`; OCR-only fields must be null on direct
  runs. OCR requires a bounded, hashed manifest naming engine/version, model
  revision/hash, configuration version, and preprocessing recipe/parameters.
* `reading_material_extraction_pages`: adds rendered dimensions/DPI,
  renderer name/version, rendered/preprocessed pixel hashes, native storage
  backend/key/hash/byte count/format/schema version, unit count, named confidence
  scale, and factual warning codes. OCR pages require all these fields; direct
  pages prohibit them. Images are bounded to 6000 per dimension and 12 million
  pixels; native evidence is bounded to 4 MiB per page. Native TSV/JSON lives behind
  an opaque private storage reference, not inline in API-facing tables.
* `reading_material_extraction_reviews`: one aggregate per OCR run, with status,
  row version, reviewed text/hash, submission identity/time, decision identity/time
  and request fingerprint, accepted revision, rejection reason, and expected
  material version. Text is bounded to 50,000 characters. Rejection requires a
  reason and cannot own a revision.
* `reading_material_extraction_review_pages`: unique review/page records containing
  reviewed text offsets and acknowledgment. Submission requires complete ordered
  source-page coverage, no dropped pages, contiguous spans separated by two
  newlines, and every page acknowledged. Offsets count PostgreSQL text characters,
  not UTF-8 bytes; they are zero-based with an exclusive end.

Raw OCR text remains immutable extraction evidence. Reviewed text is separate and
may differ from raw OCR. An accepted revision must match **reviewed** text/hash,
the deciding actor, source title/language, and the source/material/learner/run
relationships. The existing unique extraction-run revision link limits publication
to one revision. Existing PDF detail/history/attempt queries select only
`embedded_pdf` rows so they cannot expose raw OCR evidence through broad PDF access.
Accepted revision summaries recognize `ocr_reviewed` provenance.

## Database enforcement

Method-specific checks retain direct-PDF state/output rules and validate OCR scope
and state. Unique keys cover OCR request identity, completed run fingerprint,
review/run, accepted revision, decision request identity, and review/page.

Six new triggers enforce parent eligibility, bounded page metadata, review and page
mutation rules, and deferred aggregate consistency. Existing 0008 triggers remain
installed; five function bodies receive narrow method-specific branches for source
binding, terminal run guarding, aggregate consistency, page publication, and revision
evidence. Publication and acceptance are checked at transaction boundaries so their
interdependent rows can be written atomically. Terminal raw evidence cannot be
rewritten or deleted.

The manifest hash is SHA-256 of PostgreSQL `execution_manifest::text` encoded as
UTF-8. Future writers must use that exact JSONB representation, not Python JSON
serialization. Text hashes use UTF-8 text directly. Request fingerprints are stored
and syntax-checked; their semantic payload canonicalization belongs to the future
service contract.

Downgrade restores the previous function bodies and direct schema only when no OCR
history exists. Any OCR run (including running or failed), review, or reviewed
revision causes an explicit refusal; history is never silently discarded or
relabeled.

## Remaining implementation boundaries

The database validates actor foreign keys and relational consistency, not instructor
authorization. Future services must enforce learner-level instructor access, request
fingerprint comparison/idempotency, expected material version and row-version checks,
transaction locking, private evidence file integrity, and cleanup. The expected
material version is stored and bounded here; optimistic material-version enforcement
requires the acceptance service. Confidence scales are explicitly named provenance,
not accuracy guarantees or acceptance thresholds.

Tests use synthetic rows and disposable PostgreSQL, with no OCR execution. Coverage
includes direct SQL bypass attempts, every direct failure outcome, immutable terminal
evidence/decisions, reviewed-text publication, page coverage, migration backfill,
schema parity, safe downgrade, and refusal to downgrade OCR history. Existing PDF
tests remain part of the full backend suite.
