# Protocol v1 — direct PDF extraction

This is an exploratory, original synthetic university prototype benchmark, not a
representative sample of educational PDFs, a clinical evaluation, or OCR accuracy.
Production commit is recorded in the manifest and verified against the clean backend
tree on every run. The adapter uses the existing child-process runner without a DB.

## Corpus and freeze

Eleven primary categories have two development and four held-out fixtures each.
Development uses field-note templates; held-out uses museum-card templates, different
page dimensions, spacing and content-stream ordering for columns. Template families
cannot cross splits. This remains one ReportLab engine, not independent authoring tools.
External original, public-domain or permission-cleared files can be represented by the
same manifest: provide authoring-source records and every hashed reference. Never infer
reference strings by extracting the submitted PDF.

Generate development, validate all authoring records/hashes/assembly, run and debug the
harness. Freeze protocol, metrics, schema, generator, adapter, evaluator, reporter, locks,
production SHA and fingerprint. Then generate and hash held-out files; validate families;
run the final held-out primary evaluation once. Existing held-out output directories
cannot be overwritten or resumed. A failed held-out execution remains an interrupted
experiment; subsequent execution requires a separately identified experiment and must
be disclosed. Never tune production from this holdout. Freeze artifacts and raw output
are retained under ignored research/pdf_extraction/artifacts. Manifest metadata is small and versioned.

## Ground truth and denominators

The authoring JSON contains logical blocks, coordinates, physical draw order and raster
text. Embedded references are logical blocks with one LF per authored line; assembly
uses exactly two LF characters between page strings, including empty pages. Offsets are
Unicode code-point half-open ranges. Visible references separately include authored
raster text. These references are authoring conventions, not extractor-derived strings.
Automated checks independently reconstruct them from source and verify hashes. They are
not independent human ratings; no inter-rater reliability is claimed. Visual rendering
is not a prerequisite for this automated prototype, and clipping/font limitations must
be disclosed. Token references use maximal non-whitespace strings, not lexical profiles.

CER uses Unicode code points; WER uses maximal non-whitespace sequences. Preserve case,
all whitespace in CER, punctuation, apostrophes, hyphens and numbers. Unit-cost
Levenshtein uses diagonal, deletion, insertion tie preference after an exact common
prefix. Persist substitutions/deletions/insertions and full reference size. Rates are
not clamped. Zero denominator is null with explicit undefined status and spurious-unit
count, even when both strings are empty (exact=true). Positive reference with missing
output has deletion-only rate 1. Raw page and raw assembled fidelity are primary.
Production normalization is a secondary diagnostic; NFC exact match is also secondary.
Unsupported/invalid fixtures are excluded from fidelity, retained in routing.
Micro rates sum errors / sum reference units, including insertion errors on empty
references; all-empty aggregate is undefined. Report operational results (missing output
as empty) and conditional returned-output fidelity separately. No single PDF accuracy.

## Structure and independent content assessment

Logical page IDs must appear in exactly the expected sequence; missing/duplicate IDs
fail. Image-only/blank pages without embedded IDs are not applicable, not perfect.
Predeclared unique block-anchor pairs score 1 only if each occurs exactly once and in
order. Missing/duplicated endpoints fail; no pairs yields null. Tables report absent or
altered unique cell strings, nonadjacent logical rows and nonordered column anchors;
these are textual association probes, not semantic table reconstruction.

Frozen deterministic review rubric:
- extraction_failure: actual failed outcome.
- needs_review: independently anticipated visible omission/order problem, observed
  page/block order failure, or word-token mismatch.
- acceptable_with_limitation: raw characters differ but word tokens match, with no
  preceding structural/content failure.
- correct: exact embedded text, no preceding structural/content failure.

These are automated annotation-supported labels, not retrospective human judgements.
Expected policy labels are separate from content assessment. Logos with complete body
text expect review; scan plus caption expects review with missing visible content;
image-only expects OCR-required; encrypted/blank/active features expect failure.
Routing is a 4x4 matrix with row percentages and exact policy agreement. Independently
report complete-document review and accepted omissions/order problems. Agreement with
conservative policy is not proof of content completeness.

## Runtime, faults and reproducibility

Serial seeded document order, two warmups, ten measured fresh child runs per document.
First measured result supplies fidelity; every repetition's full structured outcome is
retained, including failures. Times include parent read/check and child startup/cleanup.
Median/min/max/population SD are local wall-clock measurements. No p95 claim from ten.
Separate development size/layout subset uses two warmups and 100 measured runs;
empirical p95 is sorted[ceil(.95*n)-1], not a universal tail guarantee.
Peak child RSS is null: the approved runner does not expose attributable peak RSS.
No allocation tracer is substituted. macOS has no claimed hard address-space cap.

Record OS, architecture, CPU if available, RAM availability, Python/pypdf versions,
production/research lock hashes, production SHA, extraction fingerprint, manifest hash,
source/reference hashes, order/seed and frozen code hashes. JSONL is authoritative;
CSV blank fields denote null, with status/reason fields retained. Resume is development
only and requires identical run metadata; completed fixture IDs are skipped, partial
repetition records remain audit evidence. New raw-result directories are exclusive.

Robustness uses benign fixtures and controlled process faults, separate from the 66.
Existing backend integration tests establish authorization, no partial publication,
non-extracted no revision/profile, lease/recovery, sanitization and storage guards.
Research tests exercise the runner adapter, not a second PDF parser. These tests do not
certify malicious-PDF resistance or an OS sandbox.

## Source validation limitations

The bundled Bitstream Vera font is license-referenced and hashed; every authored text
glyph must exist in its cmap and each line must fit the page. This corpus uses supported
precomposed Latin accents, punctuation and selected symbols. Combining marks and
supplementary characters are covered by metric tests, not claimed as font-supported
PDF corpus coverage. Decorative LOGO lettering is excluded from the instructional
visible-content reference; the presence of the logo remains a painted-image feature.
No human visual review or inter-rater study has been performed.

A corpus-level exclusive held-out claim also prevents selecting another output directory
to bypass primary-run protection. The freeze requires a completed development run using
the identical final harness. Completion verifies the harness did not change during a run.

Duplicate PDF hashes are rejected: the 66 entries must identify distinct binaries.
Raster lessons use distinct original text across splits. One fixture per split includes
an embedded-text page followed by a raster-only page; OCR-required takes precedence.
The exploratory first development corpus/run is retained as development-v1. Duplicate
raster-only authoring templates were corrected before the final development corpus;
no held-out data had been generated at that point.
