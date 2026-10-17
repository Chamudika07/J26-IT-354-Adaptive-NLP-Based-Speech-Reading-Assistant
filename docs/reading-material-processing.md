# Component 1 v1: reading material processing and transparent text profiling

This component describes the text, not the learner. It accepts pasted JSON text
with language_tag exactly `en`. It has no automatic language detection, so a declared
language tag is not proof that the source is English. There is no diagnosis, severity,
easy/medium/hard band, grade/readability score, vocabulary difficulty, learner
suitability decision, simplification, generative model, speech, or external NLP service.
No heavy NLP dependency, file upload, PDF extraction, OCR, or background queue is added.

## Ownership and architecture

`app/modules/reading_materials` owns four tables and its API. The empty `documents`
placeholder stays inactive. General reading material is separate from controlled
`reading_assessment_materials`; it never changes assessment history. All modules use
the shared backend, PostgreSQL database, SQLAlchemy Base/registry, and migration chain.
Research experiments cannot be imported into production.

Materials belong permanently to one learner. Instructor creation explicitly adds
an educational document to that learner's shared collection; there is no private
creator draft. Creation provenance never grants access independently of current
learner authorization. Hashes are not unique globally, searchable, or exposed.

| Current access path | Reads | Create/revise/process/archive |
| --- | --- | --- |
| Learner self | Yes | No |
| Guardian viewer or manager | Yes | No |
| Educator viewer | Yes | No |
| Educator instructor | Yes | Yes |
| Administrator alone | No | No |

Every path requires its matching active role and valid relationship; archived
learners, revoked relationships, and expired educator grants deny access. Creator
identity cannot bypass those checks. A different authorized instructor can revise
or process existing material. Guardian preference-management rights add no writes.
Learners owns reading_material.read/create/revise/process/archive policy actions;
reading materials uses its public authorization/protected-write contracts, never
private relationship tables. Consent records are not access grants. Research reuse,
exports, and model training are absent and require separate future governance.

## HTTP contract

All routes use `/api/v1/learners/{learner_id}/reading-materials` as the base.
Requests forbid unknown fields; actor identity and processing versions are server-owned.
Responses use explicit Pydantic projections and Cache-Control: no-store.

| Method and suffix | Behavior |
| --- | --- |
| POST base | title, language_tag, text -> material + revision 1, 201 |
| GET base | Active material summaries with latest revision summary |
| GET /{material_id} | Material metadata and latest revision summary |
| POST /{material_id}/revisions | row_version, title, language_tag, text -> new revision, 201 |
| GET /{material_id}/revisions | Immutable revision summaries |
| GET /{material_id}/revisions/{revision_id} | Exact original text and metadata |
| POST /{material_id}/revisions/{revision_id}/processing-runs | No body or empty JSON object; approved synchronous pipeline |
| GET /{material_id}/revisions/{revision_id}/processing-runs | Attempt history; no source/profile payloads |
| GET /{material_id}/revisions/{revision_id}/processing-runs/{run_id} | Status and successful profile; include_sentences=false by default |
| POST /{material_id}/archive | Expected row_version; archive without deleting |

Every nested resource validates the entire learner/material/revision/run chain.
Read collections filter ownership before pagination and expose no total count.
Limits default to 25 and are bounded to 1–100. Material lists order by created_at
DESC, id DESC; run lists by started_at DESC, id DESC. Their cursors are aware
ISO-timestamp|UUID positions. Revisions order by revision_number DESC and use a
positive revision-number cursor. Cursors never grant access or freeze permissions.

Source text is limited to 50,000 Unicode code points. An ASGI boundary buffers at
most 768 KiB of actual request bytes before JSON parsing, checks Content-Length
without trusting it, rejects compressed bodies, and permits only application/json
for nonempty POST bodies. The body limit accommodates JSON-escaped supplementary
Unicode characters. It applies only to this component's POST paths. All limits are
resource limits, not educational thresholds. Titles are nonblank, trimmed, and at
most 200 characters; the source text itself is never trimmed or otherwise altered
at acceptance. Empty/whitespace-only input is rejected. Punctuation/numeric-only
material can be retained, but processing returns 422 without claiming a run.

Material summaries, revision summaries, and run history exclude source text and
content hashes. Run detail includes sentence slices only when explicitly requested.
No actor, relationship, auth-session, source-hash, or fingerprint fields are public.
Consumers must render all text as plain text, never interpret it as HTML.

## Exact normalization and offsets

`reading-normalization-v1` uses Python's standard-library unicodedata:

1. Reject NUL, surrogate code points (category Cs), format controls (Cf), and Cc
   controls except TAB, LF, CR. Reject empty/whitespace-only and oversized source.
2. Convert CRLF and CR to LF. Convert U+2028 LINE SEPARATOR to LF and U+2029
   PARAGRAPH SEPARATOR to two LF characters.
3. Convert TAB and Unicode Zs horizontal spaces to ASCII space and collapse
   consecutive horizontal spaces. Keep leading/trailing spaces and all line breaks.
4. Apply NFC using canonical composition clusters, including Hangul starter
   composition. Retain conservative source ranges for normalized code points.

Case, punctuation, accents, apostrophes, hyphens, and meaningful accepted symbols
remain in analysis text. No spelling correction, accent removal, lowercasing of
display text, line-ending dehyphenation, or rewriting occurs. Exact original text
and exact normalized analysis text are both retained and independently hashed.

All offsets use zero-based Unicode code-point indices with exclusive ends, not
UTF-8 bytes, UTF-16 units, or visible grapheme counts. Source spans can cover multiple
original code points when NFC contracts a sequence. Every sentence has source and
analysis offsets. Original and normalized sentence text is obtained by slicing the
respective retained strings; it is not stored in sentence rows. Clients using UTF-16
indices must convert offsets. Fine-grained word highlighting is not implemented.

## Frozen English segmentation rules

`reading-word-tokenization-v1` starts words at Unicode category L letters and
continues across letters and category M combining marks. Internal U+0027 apostrophe
and U+2019 right single quotation mark are permitted before another letter. Internal
U+002D hyphen-minus, U+2010 hyphen, and U+2011 nonbreaking hyphen are likewise allowed.
Their preceding context must already be a lexical word. En/em dashes separate words.
Leading/trailing connectors, punctuation-only tokens, and standalone numbers do not
count as words. Adjacent letters and numbers are segmented into letter sequences;
this component does not analyze numeracy.

Comparison keys casefold tokens, map U+2019 to U+0027, and map U+2010/U+2011 to U+002D.
The analysis text is NFC before tokenization. Keys never replace display text. Letter
length counts category L code points, excluding marks and internal connectors; it
is not syllable length or perceived grapheme length.

`reading-sentence-segmentation-v1` uses explicit bounded scanning:

- Period, question mark, and exclamation mark are candidate terminators.
- A terminator consumes adjacent .?! punctuation, closing ASCII quotes/apostrophes,
  U+2019/U+201D, closing brackets/parentheses/braces, and following combining marks.
- Periods between digits do not terminate; periods immediately followed by a letter
  do not terminate (including interior abbreviation periods).
- Frozen case-insensitive abbreviations: dr, mr, mrs, ms, prof, sr, jr, e.g, i.e.
  Their final period does not terminate, even at a plausible grammatical boundary.
- Blank lines (including a line of normalized spaces) force boundaries. A single
  newline is preserved inside a segment, not silently joined away.
- A final unterminated lexical fragment is retained. Whitespace around spans is
  excluded; spans with no letters are omitted.

These are English heuristics, not a grammatical parser or a claim of universal
Unicode segmentation conformance. Headings may be fragments; unusual abbreviations,
initials, URLs, and dialogue may have imperfect linguistic boundaries. Results remain
deterministic under the recorded rule versions. User-declared en does not detect or
validate the actual language of every word.

## Features and manifest

Versions are reading-features-v1, reading-profile-v1, reading-pipeline-v1, plus the
normalization and segmentation versions above. unicode_version records the actual
unicodedata.unidata_version. No implementation_artifact_digest is invented.

The pipeline fingerprint is SHA-256 of canonical server-owned manifest JSON:
ensure_ascii=True, sort_keys=True, separators=(',', ':'). It includes processing and
profile versions, Unicode version, en language scope, source limit, accepted controls,
connector/abbreviation/closing-punctuation sets, normalization settings, comparison
key policy, offset convention, vocabulary_mode=none, and rounding specification.
Versioned source/rules must remain available in reviewed releases. Any output-affecting
rule change requires a new version/fingerprint; no unversioned remote assets exist.

Stored document measurements are normalized character_count (including whitespace),
word_count, unique_word_count, sentence_count, total_word_letter_count,
max_word_letter_count, and max_sentence_word_count. Sentence rows preserve ordinal,
dual offsets, word_count, total_word_letter_count, and max_word_letter_count. Successful
profiles require at least one lexical word and sentence. Stable counts use explicit
columns; no JSONB, per-word database rows, or redundant ratio columns are introduced.

The public profile exposes:

- length_load: character_count, word_count, sentence_count.
- word_form_characteristics: unique_word_count, average_word_length,
  maximum_word_length, lexical_diversity.
- sentence_structure: average_sentence_length, maximum_sentence_length.
- vocabulary.status: not_evaluated, never a fabricated zero difficulty count.
- Material/revision/run identities, en, pipeline/profile versions, completion time.

Average word length is total_word_letter_count / word_count. Average sentence length
is word_count / sentence_count. Lexical diversity is unique_word_count / word_count.
Ratios use local Decimal precision 40, final two-place ROUND_HALF_UP rounding, and
string serialization consistent with assessment/preference APIs. Zero denominators
are invalid successful evidence. Raw integers retain calculation precision.

Word length is not decoding difficulty; sentence length is not syntactic complexity;
lexical diversity depends strongly on text length. None measures dyslexia or the
suitability of material for a particular learner. Vocabulary evaluation is unavailable.
A later adaptation component must bind an exact revision/run and independently
obtain authorized learner evidence rather than treating this vector as a diagnosis.

## Database, transactions, and recovery

Migration 0007_reading_material_processing follows 0006 without changing earlier
revisions. It creates reading_materials, reading_material_revisions,
reading_material_processing_runs, and reading_material_sentence_features.
All PK/FKs use UUID, foreign keys use RESTRICT, and timestamps are timezone-aware UTC.
Materials and runs use the shared optimistic row_version infrastructure.

Material identity and ownership never change; archive is terminal. Revisions are
insert-only and unique by material/revision_number. Source SHA-256 must match exact
accepted text encoded as UTF-8, not the surrounding JSON bytes. Failed attempts retain
only safe failure metadata, never a partial profile. Successful evidence is immutable.

Run lifecycle is running -> succeeded or failed. Claims bind a revision and canonical
fingerprint with an increasing attempt_number. Partial unique indexes allow at most
one running and one succeeded run per revision/fingerprint. A successful matching run
is reused with 200; a new successful run returns 201. A live duplicate returns 409.
A new fingerprint creates independent history, with attempt numbering scoped to it.

Each write locks auth user -> auth session -> roles/assignments -> learner -> supporting
relationship -> material -> revision -> run. Existing learner policy ordering may
inspect a guardian grant before selecting a complete instructor path. Only public
contracts own these authorization checks. Post-lock deadline checks precede state or
version disclosure. Creating/revising material is atomic and revisions increment the
material version. Changing a revision while an older revision processes does not
invalidate the immutable older source.

Processing claims a 60-second lease and commits before any normalization/segmentation.
Only a frozen source string and attempt identity leave that transaction. The pipeline
has no database access. Publication re-resolves current account/session/roles through
auth's protected-principal contract, reauthorizes instructor access, reacquires locks,
and checks the attempt version/fingerprint/lease. It inserts sentences while the run
is running, rechecks authorization/lease, then publishes document output and succeeds
atomically. No authority locks are held during text work.

An authorized subsequent request recovers an expired running attempt as failed with
processing_interrupted and claims a new attempt. Late publication cannot overwrite
that replacement. Ordinary pipeline exceptions record pipeline_failed and return a
sanitized 503, without exception text. If authorization is lost, material is archived,
or database publication fails, no output is published; a running claim may remain
until an authorized retry recovers it. No worker/scheduler automatically changes stale
runs. An archived material cannot be retried. A lease is stale-attempt protection,
not a hard CPU cancellation mechanism.

Six focused PostgreSQL guards protect material identity, revision immutability,
run identity/terminal evidence, sentence immutability, final aggregate consistency,
and sentence publication state. Deferred consistency checks require complete,
contiguous, ordered/nonoverlapping in-bounds sentence evidence with matching totals
for success, and no sentence evidence for running/failed attempts. Aggregate scans
run per parent transition; per-sentence checks only verify the final parent state.
Database checks also validate hashes, count relationships, timestamps, and state/output
nullability. Normal application roles must not own tables or have TRUNCATE or
trigger-disabling privileges. Test cleanup uses the exclusive disposable database.

## Errors and operational boundaries

401 authentication_required; target-specific 404 not_found; 409 material_state_conflict,
version_conflict, or processing_conflict; 413 payload_too_large; 415 unsupported_media_type;
422 validation_error; 503 service_unavailable. No global role-only material endpoint
exists; target-specific administrator denial remains 404. Existing global 403 behavior
is unchanged. Invalid text/language/body errors never echo input. Body resource/media
checks run before authentication to bound parser resource use.

Public errors and application logs never include source text, titles, hashes, tokens,
snippets, actor IDs, relationship details, SQL constraint names, or parser exceptions.
Archiving is not deletion. Copyright/licensing, production retention/purge (including
backups), and any research consent/assent require separate governance before real-child
deployment. There are no copyrighted production seeds; tests use synthetic original
text. Future PDF work may introduce private blob references, extraction versions/page
provenance/warnings, and resource-limited parsing. OCR/images require a later explicit
approval. No unused blob credentials or configuration exist now.

## Verification

Use explicit TEST_DATABASE_URL ending in _test and ALLOW_TEST_DATABASE_RESET=1, with
exclusive disposable PostgreSQL. Tests cover deterministic fixtures, Unicode offsets,
API permissions/projections, body limits, immutable evidence, lease recovery, independent
connection concurrency, revocation during computation, expiry after lock waits, and
migration upgrade/downgrade/drift. Run Ruff, formatting checks, mypy, full pytest with
coverage, alembic heads/check, and git diff --check. Never target shared or real data.
