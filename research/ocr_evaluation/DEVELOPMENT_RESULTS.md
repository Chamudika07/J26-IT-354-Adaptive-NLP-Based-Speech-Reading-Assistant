# Provisional A–O development OCR comparison — 2026-10-20

This preserves the original six-run comparison. The later
[v5 English recognizer development check](PADDLE_V5_DEVELOPMENT.md) provisionally
selects v5 recognition with baseline preprocessing; the v4/grayscale choice below
describes only the original v4 run set. The subsequent
[Category P development comparison](CATEGORY_P_DEVELOPMENT.md) supersedes both
provisional choices for the complete 32-case development set.

Thirty original synthetic development base cases (two in each of categories A–O) were
processed by both local engines under three equal-budget conditions: baseline, grayscale,
and contrast ×1.3. **180 successful page-condition evaluations; no engine failures in the
corrected comparison.** These are 30 independent planned base IDs, not 180 documents.
Category P is excluded and pending. No final configuration freeze, held-out generation,
held-out evaluation, migration, production change, commit or push occurred.

## Environment and artifacts

macOS 26.3.1 arm64, project-local CPython 3.12.12. Backend requirements remain unchanged.
Tesseract 5.5.3 with Leptonica 1.87.0, English tessdata_fast 4.1.0, PSM 3 and one thread.
PaddleOCR 3.2.0 / PaddlePaddle 3.2.0 / PaddleX 3.2.1, CPU, one thread, MKLDNN off.
Paddle uses PP-OCRv5_mobile_det and en_PP-OCRv4_mobile_rec; orientation, document
unwarping and text-line orientation are disabled. Recognition score cutoff is 0.0;
no low-confidence recognized text is silently discarded. Detector thresholds, 960-pixel
maximum-side resize and unclip ratio are explicit in engines/paddle_worker.py.
This mixed-generation pair was configured deliberately to use the lightweight English
recognizer with the v5 mobile detector; it is not Paddle’s same-generation default.
All 90 corrected Paddle page-condition executions succeeded on the pinned macOS bundle.
That demonstrates local reproducibility, not a general upstream compatibility guarantee
or Linux qualification. Per-run configs and fingerprints identify the actual pairing.
Model files are all local; evaluation worker Python socket calls are denied. This is not
an OS network-isolation certification. No changing latest-model resolution occurred.

Homebrew installation also upgraded shared native dependencies (including glib, cairo,
harfbuzz and pango). This is recorded as a host environment change; it did not modify the
backend environment or code. Exact executable and directly linked library hashes are in
[environment.v1.json](manifests/environment.v1.json). A Linux CPU comparison remains required.

| Artifact | Upstream revision | SHA-256 |
|---|---|---|
| PP-OCRv5_mobile_det | 0d63e78e2b680928f6b1747d76a08db6e645efb7 | `afa1820cb16c1fd0dad589d0f8b389139061c1ef6d68019685fd07be997dda5b` |
| en_PP-OCRv4_mobile_rec | f97b62fdc0eb71c689393a19a4b21baa1795c9ab | `75f64a1ffb70c56b7a25655963ca16f5bf3286202e3f52ac972bee05cdee2f56` |
| eng.traineddata (Homebrew tessdata_fast) | tessdata_fast 4.1.0 | `7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2` |

All nine artifacts' exact sizes, sources and hashes—including inference graphs/configs
and the recognition YAML containing the character dictionary—are in
[artifacts.v1.json](manifests/artifacts.v1.json). The recognition YAML SHA-256 is
`5f6b19b6b09b6b6f7924de6c25076d0b3528b6f641e64d4f12e6e6207ec33200`.
Local model footprint is approximately 16 MiB; the complete research environment is
approximately 903 MiB including dev tools, Paddle and ReportLab. These are development
footprints, not deployment images. Model licenses are Apache-2.0 according to the pinned
upstream cards/installed Tesseract formula; card snapshots are preserved under artifacts/provenance/.

pypdfium2 4.30.0 / PDFium 126.0.6462.0 passed synthetic rendering checks at
100/150/200/300 DPI, malformed-PDF handling and repeat-pixel checks. This comparison uses
direct PNGs, so rasterization latency is not part of its engine accuracy/performance results.
The rasterizer remains research-only; arbitrary PDF validation/isolation is not newly certified.

## Corpus validation and corrections

The current corpus is artifacts/development-drafts-v3. Source and ground-truth byte hashes,
RGB pixel hashes, split/family identity, token consistency, distinct source bytes and font
coverage passed for all 30 cases. A full contact sheet was visually inspected for gross
layout/legibility; this is not independent human annotation review. Source IDs are marked
**authored**, not finally verified. Category P and held-out slots remain planned.

Validation caught missing accented glyphs in Pillow's bundled Aileron font. The two
accented pages now use licensed Bitstream Vera from locked ReportLab 4.5.1; font/licence
hashes are recorded in fonts.v1.json. The regenerated fixtures are
`accented_english_unicode-development-01` and `-02`; the v1/v2 rendered glyphs did
not match the accented authored truth. Other pages retain their original fonts. All
references come from authoring source, never OCR output. v1/v2 artifacts and six
preliminary run directories (171 page records) are preserved and excluded: one pre-fix
Tesseract attempt with 30 failures, four complete Tesseract attempts on the defective
corpus (120 successes), and one interrupted Paddle attempt with 21 defective pages.

Real runtime tests also exposed and fixed two adapter issues: isolated Tesseract data lacked
the TSV config file (now enabled directly with tessedit_create_tsv=1), and the Paddle worker's
local paddle.py shadowed the installed runtime (worker path is removed before import).
Pre-fix failed attempts remain preserved and are not silently overwritten.

## Strict primary transcription results

Raw Unicode CER and maximal-non-whitespace WER retain Phase 2B semantics. No NFC,
lowercasing, spell correction or dehyphenation. S/D/I and denominators are preserved in
page JSONL. Every condition uses the same source pixels, reference and split.

| Engine | Condition | Character S/D/I (ref 2376) | CER | Word S/D/I (ref 393) | WER | Exact | Success/failure/exclusion |
|---|---|---:|---:|---:|---:|---:|---:|
| Tesseract | baseline | 221/179/48 | 18.8552% | 15/52/22 | 22.6463% | 16/30 | 30/0/0 |
| Tesseract | grayscale | 221/179/48 | 18.8552% | 15/52/22 | 22.6463% | 16/30 | 30/0/0 |
| Tesseract | contrast ×1.3 | 219/176/48 | 18.6448% | 11/52/22 | 21.6285% | 16/30 | 30/0/0 |
| Paddle | baseline | 100/87/32 | 9.2172% | 36/4/5 | 11.4504% | 0/30 | 30/0/0 |
| Paddle | grayscale | 100/87/31 | 9.1751% | 36/4/4 | 11.1959% | 0/30 | 30/0/0 |
| Paddle | contrast ×1.3 | 100/88/34 | 9.3434% | 37/4/5 | 11.7048% | 0/30 | 30/0/0 |

The raw reference uses two newlines between authored blocks. Tesseract preserves detected
blocks; Paddle supplies native lines in one block, joined with one newline. Thus Paddle's
zero exact-document count includes a systematic separator mismatch. Primary metrics were
not rewritten to favor an engine. CER/WER also include genuine recognition and ordering
errors. Exact match and micro edit rate therefore answer different questions here.
In a **diagnostic only**, replacing authored double-newline block separators with single
newlines yields exact text on 18/30 Paddle pages at baseline and grayscale, and 17/30
at contrast. Thus at least 18, 18 and 17 primary exact-match failures respectively are
explained solely by this separator convention. The strict primary result remains 0/30;
the diagnostic does not normalize other transcription, order or punctuation errors.

**Provisional lowest-error settings among these three conditions:** Tesseract PSM 3 plus
contrast ×1.3; Paddle's pinned lightweight CPU configuration plus grayscale. Paddle's
improvement is just one character edit and one word edit versus baseline; no significance
or generalization claim is justified. These are not frozen choices, production thresholds,
or an engine-selection recommendation. Category P and broader development exploration
remain outstanding. Deskew, adaptive threshold and controlled resize were tested as
functions but not included in this three-condition comparison.

## Category and degradation results (controlled baseline)

Each cell is **CER/WER %**, micro-aggregated over the two pages in that category.

| Category | Tess baseline | Tess gray | Tess contrast | Paddle baseline | Paddle gray | Paddle contrast |
|---|---:|---:|---:|---:|---:|---:|
| accented_english_unicode | 3.60/15.00 | 3.60/15.00 | 4.50/15.00 | 8.11/25.00 | 8.11/25.00 | 8.11/25.00 |
| clean_digital_scan | 0/0 | 0/0 | 0/0 | 1.64/0 | 1.64/0 | 1.64/0 |
| grayscale_scan | 0/0 | 0/0 | 0/0 | 2.48/5.88 | 2.48/5.88 | 2.48/5.88 |
| illustration_text | 3.52/6.06 | 3.52/6.06 | 3.52/6.06 | 2.01/3.03 | 1.51/0 | 2.01/3.03 |
| low_contrast | 0/0 | 0/0 | 0/0 | 1.79/0 | 1.79/0 | 1.79/0 |
| low_resolution | 8.87/50.00 | 8.87/50.00 | 4.03/30.00 | 1.61/0 | 1.61/0 | 1.61/0 |
| mild_blur | 0/0 | 0/0 | 0/0 | 1.75/0 | 1.75/0 | 1.75/0 |
| mixed_fonts_sizes | 0.88/5.13 | 0.88/5.13 | 0.88/5.13 | 3.08/0 | 3.08/0 | 3.08/0 |
| noise_compression | 0/0 | 0/0 | 0/0 | 1.72/0 | 1.72/0 | 1.72/0 |
| perspective_distortion | 0/0 | 0/0 | 0/0 | 3.48/0 | 3.48/0 | 3.48/0 |
| punctuation_numbers_symbols | 0/0 | 0/0 | 0/0 | 1.75/0 | 1.75/0 | 1.75/0 |
| skew_rotation | 0/0 | 0/0 | 0/0 | 2.73/0 | 2.73/0 | 3.64/0 |
| tables | 39.32/45.45 | 39.32/45.45 | 39.32/45.45 | 18.80/9.09 | 18.80/9.09 | 19.66/13.64 |
| two_column | 47.24/48.89 | 47.24/48.89 | 47.24/48.89 | 27.27/40.00 | 27.27/40.00 | 27.45/40.00 |
| uneven_lighting | 100/100 | 100/100 | 100/100 | 1.77/0 | 1.77/0 | 1.77/0 |

These category results compare different source texts, not paired same-page degradation
curves. Each category has only two short artificial pages. They cannot isolate causal
robustness or establish performance on natural school material. The deterministic
single-factor transformation tooling is tested; no additional derived-variant sweep was
counted as independent documents.

## Layout, tables and confidence

Both engines scored **7/8 required adjacent block-precedence pairs on each two-column
page** (0.875) under every condition, with no missing regions. On both fixtures,
Tesseract put caption `b7` and footnote `b8` before the right column, failing the
`b6 → b7` right-column-to-caption pair. Paddle moved the right heading before the last
left paragraph, failing `b3 → right-heading`. The diagnostic matches unit polygons to author regions by center containment
with a fixed 12-pixel tolerance; OCR text is not used for region assignment. This remains
a small geometry-based diagnostic, not a validated layout reconstruction system.

Across the two tables (18 cells), baseline Tesseract produced **8/18 exact cell texts**,
with **10 missing cell regions** and zero observed-but-altered cells. Paddle produced
**15/18 exact cell texts**, zero missing cells and three altered values. Totals are the
same under grayscale and contrast, although the altered Paddle cell identities change.
Table precedence scores: Tesseract 1/9 and 4/9; Paddle 9/9 on both, under every condition.
Neither adapter emits native semantic row/column membership, so row/column association
scores remain null with an explicit reason. Geometry assignment is not claimed as native
table understanding. No low-CER result is treated as proof that layout is solved.

Baseline confidence diagnostics remain engine-specific. Tesseract uses geometry-linked
word-token multiset matching, Paddle exact whole-line matching; these are different units.
Tesseract: 348 correct and 27 incorrect observed units; 15 incorrect units had native
confidence >=90, while 2 correct units had confidence <50. Paddle: 77 correct and 20
incorrect lines; 16 incorrect lines had native score >=0.9, with no correct line <0.5.
Baseline confidence min/median/max: Tesseract correct 26.90/96.48/97.01 and error
28.32/95.00/95.88 (0–100); Paddle correct 0.749/0.994/1.000 and error
0.505/0.963/0.999 (0–1). No emitted baseline unit lacked a confidence.
Those cutoffs are descriptive only, not production acceptance thresholds or equivalent
probabilities. Mean-page confidence versus page CER Pearson r: Tesseract -0.00125;
Paddle -0.36624 (28 and 30 pages with emitted scores, respectively). Against WER,
r was -0.50144 and -0.03505 on those same page subsets. Tesseract had 14 missing
annotated regions overall (10 table cells and four uneven-lighting text regions);
Paddle had zero. Missing regions have no emitted confidence. Recognition substitutions
are not mislabeled as confidence-bearing omissions.

## Performance

All measurements are local macOS CPU observations, not universal Linux deployment results.
Across 30 baseline pages, median engine-call latency including process/model loading:
Tesseract 223.33 ms, Paddle 2418.86 ms. Paddle worker median model-load/OCR phases were
648.67 / 868.56 ms; imports/process launch and serialization explain additional wall time.
Tesseract loading/OCR phase separation is unavailable.

A separate common clean development page was measured with **two warmups plus ten fresh
process runs per engine**. Full per-repetition evidence is preserved. No 100-run subset
was performed; p95 is null, not inferred from ten runs.

| Engine | Median cold wall ms | Min | Max | Population SD | Largest child peak RSS bytes |
|---|---:|---:|---:|---:|---:|
| tesseract | 309.96 | 307.12 | 319.92 | 3.85 | 76857344 |
| paddle | 2539.79 | 2489.72 | 2836.16 | 95.68 | 689307648 |

RSS is the largest child-process maximum reported by getrusage (platform-adjusted bytes),
**not simultaneous process-tree peak memory**. Process-tree peak remains unavailable.
Paddle baseline worker-only RSS across the corpus had median 688,185,344 bytes and maximum
689,258,496 bytes. No hard-memory containment claim follows from these measurements.

## Verification and pending work

- Research: **104 tests passed**, Ruff/format pass, configured strict mypy passes
  (metrics/schemas scope), all nine local artifacts verify, 30-case validation passes.
- Production: **358 passed, 756 skipped**, one existing Starlette/httpx warning. Skips
  require an exclusive disposable PostgreSQL instance, which was not configured. Ruff,
  formatting and mypy pass; no production database was accessed.
- Alembic: exactly one head, **0008_pdf_text_extraction**. No migration 0009 or schema edits.
- Pending development photos: **phone_camera_photo-development-01** and
  **phone_camera_photo-development-02**. No substitutes. All three held-out photo slots
  also remain planned; the photo handoff guide remains applicable.
- **Held-out generations: zero; held-out executions: zero; no final freeze.**
- Git: only `?? research/ocr_evaluation/`; generated images, models, native outputs,
  timings and bulk results are ignored. No tracked production/Phase 2B/.env changes.
  `git diff --check` passes. No commit or push.

Production baseline commit: 021362555b7b57e462a04d8823171ccf9eaa24ff. Research is uncommitted.
The larger original sprint is not complete: missing phone photos, Linux validation,
broader robustness/selection evidence and a final reviewed corpus still block a freeze.
Neither engine is qualified for automatic production acceptance by this study.

## Reproducible evidence

- [Artifact manifest](manifests/artifacts.v1.json), [native environment](manifests/environment.v1.json),
  [font provenance](manifests/fonts.v1.json), [corpus slots/hashes](manifests/benchmark.v1.json).
- `provision.py` explicitly downloads only manifest-pinned artifacts and verifies bytes
  before publishing; it is never invoked by evaluation. `compare.py` reproduces the equal
  three-condition development experiment into a new exclusive directory.
- `validate_corpus.py`, `analyze_development.py` and `performance.py` provide auditable
  validation, geometry/confidence diagnostics and repeated process measurements.
- Corrected results: `artifacts/ao-v3-{tesseract,paddle}-{baseline,grayscale,contrast}-measured/`:
  authoritative pages.jsonl, config.json, native text/JSON, assembled text, diagnostics.json.
- The archived preliminary attempts use different paths. No overwritten/rerun held-out
  results exist. `manifests/development-run-index.v1.json` records evidence hashes; this is
  a development record, not a final configuration freeze.
