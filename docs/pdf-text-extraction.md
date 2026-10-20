# Phase 2A: private machine-readable PDF extraction

The reading_materials module accepts instructor-uploaded PDFs with embedded text.
It runs pypdf 6.21.0 in a killable child process. python-multipart 0.0.32 parses the
bounded upload envelope. Both are locked in apps/backend/uv.lock. There is no OCR,
image upload, PDF editing, preview, binary download, layout reconstruction, speech,
LLM, simplification, or automatic text-profile generation.

All storage and evidence remain within the shared application architecture: one
FastAPI backend, one PostgreSQL application database, one Alembic history. The PDF
subpackage belongs to reading_materials; it does not activate documents or import
research code.

## Configuration and private storage

For host development, export PDF_STORAGE_ROOT to an absolute directory outside the
repository and any web root. The backend creates its final directory with mode 0700;
existing directories must be owned by the runtime user and deny group/other access.
The setting defaults to unavailable: text endpoints still work, but PDF work returns
a sanitized 503 until configured. No real .env is needed.

For Docker, use an externally provisioned private bind mount or volume outside /app,
owned by UID 10001 with mode 0700, and pass PDF_STORAGE_ROOT to the backend container.
Do not use a public/static mount. The default Compose setup does not provision this
optional mount. Runtime keys/files must never enter the image or Git.

Objects use random UUID hex keys, never filenames or content-addressed paths.
Original multipart filenames are ignored and never persisted. A separate bounded
title is required. Files are created exclusively with mode 0600, symlink-safe opens,
fsync of file/directory, and exact byte SHA-256 metadata. Database rows contain
opaque keys, not binaries. Public responses omit keys, backend identifiers, hashes,
and actors. No client path or URL is accepted; the server fetches no external URLs.

The filesystem is not transactional with PostgreSQL. The object is durable before
its reference commits. A failed/uncertain commit leaves a possible orphan; the API
does not blindly delete it. An exclusive file lock is held through registration.
Idempotent upload retries can also leave harmless unreferenced objects.

Internal development cleanup, from apps/backend with the intended local database
and PDF_STORAGE_ROOT explicitly configured:

```sh
uv run --locked python -m app.modules.reading_materials.pdf.cleanup
```

Cleanup examines only generated keys older than 24 hours, takes a nonblocking file
lock, checks PostgreSQL for a reference, and deletes only unreferenced regular files.
It skips locked/new/referenced files and fails closed when the database is unavailable.
It prints only a count. No HTTP cleanup/delete endpoint exists. Production object
storage will need equivalent staging/finalization, grace periods, reference checks,
reconciliation, and deletion governance; it is not implemented here.

## API and authorization

All paths are beneath /api/v1/learners/{learner_id}/reading-materials:

| Operation | Contract |
| --- | --- |
| POST /pdf | multipart: title, language_tag=en, upload_request_id UUID, one file |
| GET /pdf-sources | Authorized summaries; cursor pagination, default 25/max 100 |
| GET /pdf-sources/{source_id} | Source metadata, material reference, latest extraction |
| POST /pdf-sources/{source_id}/extraction-runs | Empty JSON or row_version for bound material |
| GET /pdf-sources/{source_id}/extraction-runs | Paginated immutable attempt history |
| GET /pdf-sources/{source_id}/extraction-runs/{run_id} | Status/provenance/counts; include_evidence=true adds bounded text/pages |
| POST /pdf-sources/{source_id}/archive | Expected source row_version |

The static PDF routes precede generic material-ID routes. Existing text routes retain
their JSON limits. Upload authorization precedes body reception; no Form/File
parameter causes FastAPI to pre-parse an unauthorized body. Actual streamed bytes
are bounded before multipart parsing. Temporary multipart files close on success
and validation errors. All successful and sanitized error responses use no-store.

Learner self, guardian viewer/manager, and educator viewer may read authorized
sources, statuses, and text. Only educator instructors may upload/extract/archive.
Administrator alone has no access. Dedicated learner actions use the public learner
authorization service; the PDF subpackage never queries private relationship tables.
Creator identity grants no continuing access. Revoked/expired grants and archived
learners block access. A linked archived material also blocks source access/work.
Source archive blocks further source reads/extraction without deleting prior revisions.

The upload request ID is unique per learner/uploader. Reusing it with different
bytes/title/language returns 409. A terminal original upload result is reused with
200, including a recorded failed outcome. Use the explicit extraction endpoint to
retry a failed attempt. A newly completed attempt returns 201; that HTTP status does
not imply text was accepted. No profile is automatically generated.

## Limits and isolation

- PDF: at most 10 MiB; multipart body: 10 MiB + 64 KiB.
- Exactly one file part and three metadata fields; metadata parts at most 1 KiB.
- Exact application/pdf part type and leading %PDF- bytes are required.
- 1–25 pages; assembled output at most 50,000 Unicode code points.
- Extraction lease: 90 seconds; wall timeout: 30 seconds.
- POSIX child CPU: 15 seconds; output-file limit: 1 MiB; core dumps disabled.
- Linux child address-space limit: 512 MiB. macOS has no claimed hard memory bound.
- Two parser processes at most per backend process; this is not a distributed quota.
- Object graph inspection: 10,000 visits/depth 32; content inspection: 100,000
  operations per page and form recursion depth 16. Uncertain recursive content is
  classified for review. Parser/library allocation happens within the child limits.

These are technical resource bounds, not educational thresholds. The process receives
only an opened source stream on stdin, an empty environment, and no DB connections or
credentials. It uses Python isolated mode, disables parser logging, discards stderr,
and returns a bounded JSON result. The parent verifies size/digest before parsing and
validates the child result before publication. Timeouts kill and reap the child.

Python socket audit hooks deny network operations. This is defense in depth, not an
OS sandbox against arbitrary code execution. The child runs under the runtime UID
and can load application/dependency files. Production requires an OS/container
sandbox with restricted filesystem/network and aggregate resource budgets. Local
storage uses POSIX flock/O_NOFOLLOW and supports Linux/macOS; Windows is not supported.
Do not claim macOS enforces Linux address-space limits. Request ingress rate/body-time
limits and host-wide disk/concurrency quotas remain deployment responsibilities.

## PDF security policy

Use strict pypdf parsing; reject encrypted PDFs even with an empty password. Reject
malformed/zero-page/excess-page documents and detected JavaScript, embedded files,
launch/additional actions, forms/XFA, external stream references, and unsupported
active actions. Rejecting known feature structures is not antivirus certification.
No action is executed and no hyperlink is followed. Unused image resources do not
alone imply painted content. Image pixels are never decoded or rendered.

Parser exception messages, metadata, stdout, and stderr are not application logs or
public errors. Runtime/backend failures use fixed codes and sanitized 503 errors.
Wrong MIME/magic is 415; oversized upload is 413; invalid metadata is 422; inaccessible
resources are 404; absent authentication is 401. Live claims and stale/archived state
use the appropriate 409 code. Claimed normal document rejection returns a failed
extraction resource, not a parser stack trace.

## Exact text and page provenance

Extract plain text in PDF page order with orientations 0/90/180/270 and space_width
200. Preserve returned strings exactly. Assemble T1 + "\n\n" + ... + "\n\n" + Tn,
including empty pages, with no final added separator. SHA-256 hashes exact UTF-8.
Do not trim, reorder columns, remove headers/footers/page numbers, reconstruct tables,
join hyphenation, or rewrite punctuation. Extractor order may differ from reading order.

Page rows store offsets and measurements, not duplicate page text. Offsets are zero-based
Unicode code-point positions with exclusive ends. Empty pages have start=end. Separators
belong to no page. Slicing assembled_text[start:end] reproduces the exact page string.
Accepted revision.original_text duplicates the bounded assembled text to preserve the
existing independent revision contract; deferred database guards enforce equality.
Sentence source offsets then refer to that revision string, not binary PDF offsets.

## Factual quality outcomes

For each page, Ci=len(Ti), Wi=number of tokens from reading-word-tokenization-v1.
P is total pages; L counts Wi>0; E counts Ci=0; N counts Wi=0.
Persist P,L,E,N,sum(Ci),sum(Wi), and len(assembled_text)=sum(Ci)+2(P-1).
lexical_page_coverage=L/P uses Decimal with two-place ROUND_HALF_UP display rounding.
It is not accuracy, completeness, an OCR score, or a learner suitability measure.

- extracted: validated bounded text with lexical words and no unresolved warning.
- ocr_required: painted raster image on a page with no lexical words. No revision.
- needs_review: image/text ambiguity, painted vector content, uncertain inspection,
  or replacement characters. No revision and no manual acceptance bypass this sprint.
- failed: invalid/security/resource failure, unsupported text characters, or blank/
  wordless unusable document. No revision or partial published page evidence.

All pages are inspected before classification. OCR-required evidence takes precedence
over review warnings. Text-plus-image includes harmless logos: conservative review
is intentional. Counts cannot detect all incomplete or scrambled embedded text, and
an existing OCR text layer is not verified. There is no percentage cutoff. Consumers
must display partial review/OCR evidence as such and render all text as plain text.

## Versioned lifecycle and integrity

pdf-extraction-v1, pdf-validation-v1, pdf-assembly-v1, and pdf-quality-v1 are persisted
with installed pypdf, Python, Unicode, and tokenizer versions. The canonical sorted
ASCII JSON manifest includes limits, extraction settings, separator, rejection and
warning policies; SHA-256 yields extraction_fingerprint. No fabricated build digest.
Changed versions/settings create new history. Historical GETs never rerun extraction.

Claim transactions protect current auth, learner/instructor relationship, existing
material, source, then attempt. Learner locking serializes source binding and upload
idempotency. Claims commit before child parsing. Publication re-resolves auth and
rechecks relationship/session expiry after lock waits, source/material archival,
material version, run ownership/version/fingerprint, and lease. It publishes pages,
terminal outcome, source binding, and accepted revision atomically.

One live running and one extracted result per source/fingerprint. Expired attempts
become failed/extraction_interrupted before a new attempt. A late publisher cannot
replace newer evidence. Bound-source new extraction requires expected material version;
a concurrent manual revision causes publication conflict. Completed identical outcomes
are reused. Unauthorized/interrupted publication leaves a recoverable lease, not a
partially accepted revision. Accepted text can be processed separately through the
existing versioned text-normalization/profile API; vocabulary remains not_evaluated.

Migration 0008_pdf_text_extraction adds sources, extraction runs, and extraction pages,
plus a unique nullable revision extraction FK and source-kind provenance check. Seven
new PostgreSQL triggers enforce source identity/binding, terminal immutability, page
publication/aggregates, and revision/evidence equality. Foreign keys RESTRICT deletion.
Downgrade refuses when PDF revisions exist; it never relabels or deletes their history.
Migrations 0001–0007 remain unchanged.

## Governance, testing, and future work

No public binary access, global search/deduplication, research exports, automatic research
reuse, copyrighted textbook seeds, or real learner fixtures. Archive is not deletion.
Copyright/licensing, retention, privileged purge, and backup deletion require separate
governance before real-child deployment. Private storage must be backed up consistently
with database references. Reproduction needs the original object and pinned environment.

Tests generate original PDFs in memory and temporary private directories. They cover
API authorization, real subprocess extraction, malicious/ambiguous structures, offsets,
leases, independent connections, immutable database evidence, idempotency, migration
round trips, and orphan safety. Use exclusive disposable PostgreSQL only.

Phase 2B evaluates extraction quality/reading order and rejection rates on a separately
governed benchmark. Phase 3 evaluates OCR engines and scanned-document support; no OCR
engine, credentials, worker queue, or image upload exists in this implementation.
