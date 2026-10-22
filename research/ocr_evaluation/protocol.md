# OCR research protocol v1 — implementation draft, not a held-out freeze

Component 1, A. M. C. P. Ariyasena (IT22081766). Research only.

## Sampling and governance

80 independent base sources: 16 named categories, each with 2 development and 3 held-out
sources. Derived variants are not additional independent observations. All pages, crops,
photographs and degraded derivatives inherit their source family's split. Planned manifest
slots are not acquired documents. Only original authored, public-domain with provenance,
or explicitly cleared material is admissible. No children, private schools, learner
records or unlicensed textbook material. Category P requires genuine photographs of
researcher-authored printed pages against neutral surroundings; synthetic perspective is
category G, not category P. Never generate held-out fixtures before development selection.

The current v2 corpus has 30 non-photo drafts. Two older development print masters are
preserved awaiting researcher photography; new generators skip Category P entirely.
The short drafts are harness smoke material, not a representative corpus. Two-column
v2 drafts include headings, captions and footnotes; tables include cell geometry. Full
visual/source review remains necessary before verification. Every draft has an
independent original text but shares one authoring renderer: generalization is limited.
Ground truth is authored before OCR; OCR output must never populate it. Preserve separate
transcription and layout annotations, visible glyph review, page order, cell membership,
logical IDs, precedence pairs, legibility notes and geometry. Geometric transforms apply
the recorded forward homography to every polygon; clipping needs explicit review.

## Versions and primary metrics

Corpus ocr-corpus-v1; protocol ocr-protocol-v1; authoring ocr-authoring-v1;
metrics pdf-fidelity-v1 (byte-identical copy of frozen Phase 2B metrics.py);
degradation ocr-degradation-v1; preprocessing ocr-preprocessing-v1;
rasterization ocr-rasterization-v1; adapters ocr-adapter-v1; results ocr-result-v1;
artifact manifest ocr-artifacts-v1. This protocol is not yet frozen for final execution.

CER uses Unicode code points, WER maximal non-whitespace tokens. Case, punctuation,
numbers and CER whitespace are significant. No NFC normalization, spell correction,
lowercasing or dehyphenation in primary metrics. S/D/I and reference denominator are
retained. Empty reference rates are null (undefined_zero_reference), including empty vs
empty; insertions are still retained and count in pooled micro rates. Rates can exceed 1.
Equal-cost alignment preference is diagonal, deletion, insertion. NFC is diagnostic only.

## Assembly and layout

Preserve native engine sequence, without geometric sorting. Tesseract word records join
with one U+0020 inside a line, U+000A between lines, two U+000A between blocks. Paddle's
native recognized lines use U+000A, one native block. No trailing separator. Pages join
with U+000C between page strings. Keep page texts and document assembly separately.
These choices may penalize line/block disagreement; never alter references to match OCR.
A separately named experimental condition is required for geometric reordering.

Block precedence = uniquely present, correctly ordered required pairs / all required
pairs. Missing or duplicate endpoints fail a pair; no pairs yields null. Match regions
using independently reviewed IDs/geometry, not OCR text as the sole matching signal.
Report missing, duplicate and misplaced regions, line order, cell text and row/column
association separately. Low CER does not establish layout correctness. Automatic region
matching is not implemented; current layout functions require explicit annotations.

## Inputs, preprocessing and degradation

PNG/JPEG only; declared MIME must match magic, exactly one frame, <=10 MiB compressed,
<=6000 each axis and <=12 million pixels. Apply EXIF orientation once, convert ICC to
sRGB when present, assume sRGB for untagged input, composite alpha on white, output RGB
8-bit with metadata removed. TIFF/WebP/HEIC/GIF are out of scope. PDF rendering requires
prior successful Phase 2A validation; renderer itself is not a validation substitute.
Production failed outcomes never become OCR fallbacks. inspection_uncertain and replacement
character cases are manual review, vector-only ambiguity is not automatically eligible.
Only ocr_required/image_without_text is eligible; painted-image needs_review is comparison
and review only. Production pypdf extraction remains untouched.

PDFium baseline 300 DPI; development 200/150/100 DPI comparisons. Bound pixel allocation
before rendering, record point sizes, scale, wrapper/native versions and RGB pixel hash.
Pixel identity is only expected within the frozen environment; no cross-platform claim.
The current renderer is in-process and synthetic-only; isolated rasterization and OS
resource ceilings remain prerequisites for final PDF benchmark execution.

Degradation single factors are declared in generators/degradations.py: resolution,
±2/±5 skew, 90/180/270 fixed-canvas rotations (clipping possible), blur 0/.6/1.2,
contrast 1/.7/.4, brightness .8/1/1.2, JPEG 95/70/40, Gaussian noise 0/5/10,
fixed perspective and deterministic gradient. Persist order, parameters, seed,
interpolation, parent/output pixel hashes and forward matrix. Encoded source file digests
are separate from pixel digests. No Cartesian product or unregistered combinations.

Preprocessing baseline only mandatory image normalization. Develop grayscale, externally
specified deskew angle (not a claimed deskew estimator), contrast, resize, adaptive
threshold individually. Predeclare equal budgets: baseline plus five individual recipes
per engine, identical development cases. No automatic chaining. Select only after measured
development evidence, not convenience or held-out performance.

## Engines, fairness and provenance

Tesseract requires exact 5.x version and explicit eng.traineddata. Record executable,
linked-library/runtime build and model hashes before qualifying it. TSV native confidence
0..100 is not equivalent to Paddle's uncalibrated native recognition score 0..1. No text
is silently dropped for low recognition confidence. Paddle pinned packages are 3.2.0 /
3.2.0, PaddleX 3.2.1 from uv.lock. The development-selected pair is PP-OCRv5_mobile_det
and en_PP-OCRv4_mobile_rec; the English v5 recognizer was also tested on development.
All model files, inference configuration, dictionaries and any enabled auxiliary models
must have exact sizes, hashes, licences and immutable upstream revisions. No latest model
resolution during evaluation. Both candidate bundles now have pinned, verified manifests.
Paddle worker disables orientation/unwarping modules and recognition-score filtering;
explicit detector thresholds and resize settings are recorded in its source.

Controlled baseline shares source pixels, DPI, language, split, preprocessing and CPU
thread count. Engine-selected comparison uses equal exploration budgets and frozen
configurations. Record detector settings, dictionaries, orientation, resizing, acceleration,
all versions and hardware. Use one Linux CPU environment for final comparison. macOS
results are development/portability evidence only. Network disabled at OS/container boundary
is required for final runs; Python socket audit hooks alone are not a security boundary.

## Performance, freeze and selection

Selected performance cases: two warmups, ten measured fresh-process runs. Separate cold
wall latency, model load, rasterization, preprocessing, OCR, serialization and cleanup.
Median/min/max/population SD; p95 only for a dedicated 100-run subset, nearest rank.
Never repeat the whole corpus 100 times. Peak process-tree RSS remains null with reason
unless reliably instrumented. Local macOS measurements are recorded in EVALUATION.md.

Before held-out execution, freeze code/schema/protocol/lock/model hashes, manifest,
selected engine and preprocessing settings, render DPI, selection rules, source commit
references and development evidence. Check actual immutable artifacts and all mandatory
gates. Current freeze helpers are utilities, not a complete final-run qualification system;
the validation CLI does not execute held-out runs. Exclusive claim/output creation prevents
ordinary overwrites but is not tamper-proof. Do not treat operator booleans as evidence.
A failed/interrupted primary run remains claimed and requires a recorded amendment.

Mandatory gates: local/offline, acceptable licence, frozen models, safe failure,
Linux CPU deployability and bounded resources. Compare micro CER/WER, categories,
punctuation/numbers, layout/tables, degradations, native confidence, failures, latency,
memory, footprint and operational complexity. No weighted winner score. Selection may be
"Neither engine is ready for automatic production acceptance." No production threshold,
publication, endpoint, database change or diagnosis is authorized by research results.


## Category P development and held-out deferral

The researcher supplied two genuine development photographs of the archived two-line
v1 print masters. Both are registered and scored. The later longer development-v2
print sheets were not photographed and are not ground truth for these photos. The
three held-out photograph slots remain absent. No external or synthetic replacements are allowed.
See PHONE_PHOTOS.md. All five exact JPEG paths must exist and pass image policy before
claim_holdout can create a claim, even if the manifest has been marked verified. This is
an additional guard, not a replacement for provenance review or freeze validation.
New synthetic corpus generation skips P. The non-photo runner is in development.py;
photo_development.py handles only the two registered development photos. The 32-case
development configuration freeze is separate from the mandatory final held-out freeze;
final held-out execution remains unavailable.
