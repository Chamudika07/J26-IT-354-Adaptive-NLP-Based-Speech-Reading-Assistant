# Final held-out OCR evaluation v1

**Recommendation C: neither engine is currently suitable for automatic production acceptance. Review-first is required for any future candidate integration.**

This is OCR research evaluation, not medical or dyslexia diagnosis. Held-out data was never used for tuning. No production OCR is implemented.

## Stages and immutable evidence

Development selected Tesseract 5.5.3, PSM 3, contrast ×1.3 and PaddleOCR/PaddlePaddle 3.2.0 with PP-OCRv5_mobile_det + en_PP-OCRv4_mobile_rec, grayscale. The development freeze remains unchanged. Held-out preparation and genuine-photo registration preceded this one-time final evaluation.

Corpus version: `ocr-heldout-preparation-v1`; 45 A–O cases and three genuine phone captures. The historical preparation manifest retains its pre-execution counter; the execution index is authoritative for the completed state. All 48 image and ground-truth hashes, configurations, model artifacts/revisions, runtime versions, and output hashes are bound in `manifests/heldout-execution.v1.json`.

Execution UTC: 2026-10-22T13:43:42.536188+00:00 to 2026-10-22T13:46:22.690022+00:00. Exactly 48 Tesseract + 48 Paddle = 96 engine-case evaluations. No failures, exclusions, or retries. Poor results were retained.

Raw process stdout/stderr, command/return-code records, native normalized outputs, assembled strings, and per-case results are preserved in ignored `artifacts/heldout-final-v1/<engine>/<fixture>/`. Each engine has `pages.jsonl` and a byte-equivalent frozen `config.json`. The historical experiment ID in those configurations is retained to avoid modifying frozen configuration hashes; the execution index identifies the held-out experiment. A write-exclusive reservation and per-case directory prevent ordinary reruns.

Run `uv run python verify_heldout_results.py` for read-only hash and metric verification. `heldout_execution.py` without flags also verifies, never executes. The preparation pre-run validator now correctly rejects persisted held-out results. Do not run `--execute` again.

## Overall results

Primary CER/WER use the frozen raw Unicode / whitespace-token edit definitions and micro aggregation. Strict exact compares unmodified strings. The existing diagnostic replaces only reference double newlines with single newlines; it is not a primary score. Neither metric proves reading order.

| Engine | CER | WER | Character S/D/I | Word S/D/I | Strict exact | Newline diagnostic |
|---|---:|---:|---|---|---:|---:|
| tesseract | 681/5620 = 12.1174% | 122/932 = 13.0901% | 226/335/120 | 18/77/27 | 23/48 | 0/48 |
| paddle | 535/5620 = 9.5196% | 127/932 = 13.6266% | 162/324/49 | 40/63/24 | 0/48 | 19/48 |

## Per-category results and development comparison

Three held-out cases versus two development cases per category. Different content and the much longer held-out phone pages mean these are descriptive differences, not paired statistical improvements.

| Category | Tesseract held-out CER/WER | Tesseract development CER/WER | Paddle held-out CER/WER | Paddle development CER/WER |
|---|---:|---:|---:|---:|
| A: clean_digital_scan | 0.0000% / 0.0000% | 0.0000% / 0.0000% | 1.9900% / 2.7778% | 1.6393% / 0.0000% |
| B: grayscale_scan | 0.0000% / 0.0000% | 0.0000% / 0.0000% | 2.0942% / 2.9412% | 2.4793% / 5.8824% |
| C: low_resolution | 18.4080% / 47.0588% | 4.0323% / 30.0000% | 2.4876% / 5.8824% | 1.6129% / 0.0000% |
| D: mild_blur | 0.0000% / 0.0000% | 0.0000% / 0.0000% | 2.5641% / 3.0303% | 1.7544% / 0.0000% |
| E: skew_rotation | 40.4040% / 43.7500% | 0.0000% / 0.0000% | 2.0202% / 3.1250% | 2.7273% / 0.0000% |
| F: uneven_lighting | 100.0000% / 100.0000% | 100.0000% / 100.0000% | 1.9417% / 2.8571% | 1.7699% / 0.0000% |
| G: perspective_distortion | 0.0000% / 0.0000% | 0.0000% / 0.0000% | 2.6042% / 0.0000% | 3.4783% / 0.0000% |
| H: low_contrast | 0.0000% / 0.0000% | 0.0000% / 0.0000% | 1.5306% / 0.0000% | 1.7857% / 0.0000% |
| I: noise_compression | 0.0000% / 0.0000% | 0.0000% / 0.0000% | 1.9608% / 2.8571% | 1.7241% / 0.0000% |
| J: mixed_fonts_sizes | 1.6129% / 5.1724% | 0.8811% / 5.1282% | 4.0323% / 13.7931% | 3.0837% / 0.0000% |
| K: punctuation_numbers_symbols | 0.0000% / 0.0000% | 0.0000% / 0.0000% | 1.9704% / 2.6316% | 1.7544% / 0.0000% |
| L: accented_english_unicode | 1.0101% / 6.2500% | 4.5045% / 15.0000% | 4.0404% / 15.6250% | 8.1081% / 25.0000% |
| M: tables | 35.3234% / 30.3030% | 39.3162% / 45.4545% | 14.4279% / 6.0606% | 18.8034% / 9.0909% |
| N: two_column | 29.4268% / 35.8974% | 47.2371% / 48.8889% | 29.6815% / 35.8974% | 27.2727% / 40.0000% |
| O: illustration_text | 2.7523% / 0.0000% | 3.5176% / 6.0606% | 1.5291% / 1.8519% | 1.5075% / 0.0000% |
| P: phone_camera_photo | 2.2286% / 0.0000% | 13.0435% / 8.0000% | 11.6000% / 20.2020% | 5.7971% / 8.0000% |

Tesseract pooled development CER/WER was 18.3373%/20.8134%, versus held-out 12.1174%/13.0901%. Paddle changed from 8.9897%/11.0048% to 9.5196%/13.6266%. Tesseract improves on longer phone passages, tables, Unicode, and this two-column sample, but regresses on low-resolution and skewed pages. Paddle improves Unicode and table transcription but regresses on phone text, mixed fonts, and several clean/degraded samples. No setting was changed in response.

Tesseract entirely omits text on all three uneven-lighting pages (100% CER/WER), matching the development failure. Low-resolution WER rises from 30% to 47.0588%; skew WER rises from 0% to 43.75%. Paddle mixed-font WER rises from 0% to 13.7931%. Punctuation/numbers WER is 0% for Tesseract and 2.6316% for Paddle; accented-text WER is 6.25% versus 15.625%.

## Genuine Category P photographs

| File | SHA-256 |
|---|---|
| phone_camera_photo-heldout-01.jpg | `7b97c94c0b12d707e14e92b2ee6da6eb36ce8d3ec227f530399f253eeb1e694d` |
| phone_camera_photo-heldout-02.jpg | `5f03d438beb9a9d2e2f1915e83a847b143902eecd0dfea73dc09d435ae11c418` |
| phone_camera_photo-heldout-03.jpg | `d1715c9416129ecf60de93b7a9fc77aac941e8285f11d36929391d76b4502860` |

All three are user-attested genuine captures, visually matched to their fixtures; raw JPEG bytes and ground truth are unchanged. Device origin is not independently certified.

| Engine | Pooled phone CER/WER |
|---|---:|
| tesseract | 2.2286% / 0.0000% |
| paddle | 11.6000% / 20.2020% |

| Photo | Tesseract CER/WER | Paddle CER/WER |
|---|---:|---:|
| 01 | 2.1488% / 0.0000% | 2.8099% / 15.0000% |
| 02 | 1.5437% / 0.0000% | 29.8456% / 37.7551% |
| 03 | 3.0249% / 0.0000% | 2.1352% / 8.0808% |

All six phone results fail strict exact match. Tesseract retains every whitespace token on all three photographs (0% WER); CER reflects line breaks, paragraph spacing, and extraneous blank units. Paddle photo 01 joins punctuation to neighbouring words; photo 03 has similar spacing/punctuation errors. Photo 02 loses the final two lines, from “compare patterns from many trees” through the end of the passage: 171 character deletions and 31 word deletions. The saved output ends at “Scientists”.

Photo spatial omission and confidence-correctness metrics are unavailable: master polygons have not been registered to photographed coordinates. The observed photo-02 truncation above is direct transcription inspection, not a newly invented spatial metric.

## Two-column reading order

Both engines pass 7/8 required adjacent precedence pairs per page, 21/24 total. Both interleave left and right columns. Required order: heading → left-heading → left-body → b3 → right-heading → b5 → b6 → b7 → b8. Observed on all six results: heading → left-heading → right-heading → left-body → b5 → b3 → b6 → b7 → b8. The pair b3 → right-heading fails on every page. The 7/8 score does not establish full reading order; the adjacent-pair measure also leaves some interleaving unpenalized.

| Engine / fixture | Required pairs | Passed pairs |
|---|---|---|
| tesseract / two_column-heldout-01 | `[['heading', 'left-heading'], ['left-heading', 'left-body'], ['left-body', 'b3'], ['b3', 'right-heading'], ['right-heading', 'b5'], ['b5', 'b6'], ['b6', 'b7'], ['b7', 'b8']]` | `[['heading', 'left-heading'], ['left-heading', 'left-body'], ['left-body', 'b3'], ['right-heading', 'b5'], ['b5', 'b6'], ['b6', 'b7'], ['b7', 'b8']]` |
| tesseract / two_column-heldout-02 | `[['heading', 'left-heading'], ['left-heading', 'left-body'], ['left-body', 'b3'], ['b3', 'right-heading'], ['right-heading', 'b5'], ['b5', 'b6'], ['b6', 'b7'], ['b7', 'b8']]` | `[['heading', 'left-heading'], ['left-heading', 'left-body'], ['left-body', 'b3'], ['right-heading', 'b5'], ['b5', 'b6'], ['b6', 'b7'], ['b7', 'b8']]` |
| tesseract / two_column-heldout-03 | `[['heading', 'left-heading'], ['left-heading', 'left-body'], ['left-body', 'b3'], ['b3', 'right-heading'], ['right-heading', 'b5'], ['b5', 'b6'], ['b6', 'b7'], ['b7', 'b8']]` | `[['heading', 'left-heading'], ['left-heading', 'left-body'], ['left-body', 'b3'], ['right-heading', 'b5'], ['b5', 'b6'], ['b6', 'b7'], ['b7', 'b8']]` |
| paddle / two_column-heldout-01 | `[['heading', 'left-heading'], ['left-heading', 'left-body'], ['left-body', 'b3'], ['b3', 'right-heading'], ['right-heading', 'b5'], ['b5', 'b6'], ['b6', 'b7'], ['b7', 'b8']]` | `[['heading', 'left-heading'], ['left-heading', 'left-body'], ['left-body', 'b3'], ['right-heading', 'b5'], ['b5', 'b6'], ['b6', 'b7'], ['b7', 'b8']]` |
| paddle / two_column-heldout-02 | `[['heading', 'left-heading'], ['left-heading', 'left-body'], ['left-body', 'b3'], ['b3', 'right-heading'], ['right-heading', 'b5'], ['b5', 'b6'], ['b6', 'b7'], ['b7', 'b8']]` | `[['heading', 'left-heading'], ['left-heading', 'left-body'], ['left-body', 'b3'], ['right-heading', 'b5'], ['b5', 'b6'], ['b6', 'b7'], ['b7', 'b8']]` |
| paddle / two_column-heldout-03 | `[['heading', 'left-heading'], ['left-heading', 'left-body'], ['left-body', 'b3'], ['b3', 'right-heading'], ['right-heading', 'b5'], ['b5', 'b6'], ['b6', 'b7'], ['b7', 'b8']]` | `[['heading', 'left-heading'], ['left-heading', 'left-body'], ['left-body', 'b3'], ['right-heading', 'b5'], ['b5', 'b6'], ['b6', 'b7'], ['b7', 'b8']]` |

## Table-cell evidence

Tesseract: 16/27 exact cells, 10 missing cells, one altered cell. Paddle: 22/27 exact cells, zero missing cells, five altered cells (including leading-space mismatches). These use the existing fixed geometry matcher and exact text; neither adapter emits semantic row/column membership, so no semantic table-understanding claim is made.

| Engine / fixture / cell | Expected | Observed |
|---|---|---|
| tesseract / tables-heldout-01 / r0c0 | `"Sample"` | `"Sample"` |
| tesseract / tables-heldout-01 / r0c1 | `"Number"` | `"Number"` |
| tesseract / tables-heldout-01 / r0c2 | `"Box"` | `"Box"` |
| tesseract / tables-heldout-01 / r1c0 | `"Quartz"` | `"Quartz"` |
| tesseract / tables-heldout-01 / r1c1 | `"17"` | `""` |
| tesseract / tables-heldout-01 / r1c2 | `"E5"` | `""` |
| tesseract / tables-heldout-01 / r2c0 | `"Feldspar"` | `"Feldspar"` |
| tesseract / tables-heldout-01 / r2c1 | `"28"` | `"28"` |
| tesseract / tables-heldout-01 / r2c2 | `"H9"` | `"H9"` |
| tesseract / tables-heldout-02 / r0c0 | `"Sample"` | `"Sample"` |
| tesseract / tables-heldout-02 / r0c1 | `"Number"` | `"Number"` |
| tesseract / tables-heldout-02 / r0c2 | `"Box"` | `"Box"` |
| tesseract / tables-heldout-02 / r1c0 | `"Moss"` | `"Moss"` |
| tesseract / tables-heldout-02 / r1c1 | `"23"` | `""` |
| tesseract / tables-heldout-02 / r1c2 | `"F8"` | `""` |
| tesseract / tables-heldout-02 / r2c0 | `"Bark"` | `"Bark"` |
| tesseract / tables-heldout-02 / r2c1 | `"35"` | `""` |
| tesseract / tables-heldout-02 / r2c2 | `"J2"` | `""` |
| tesseract / tables-heldout-03 / r0c0 | `"Sample"` | `"Sample"` |
| tesseract / tables-heldout-03 / r0c1 | `"Number"` | `"Number"` |
| tesseract / tables-heldout-03 / r0c2 | `"Box"` | `"Box"` |
| tesseract / tables-heldout-03 / r1c0 | `"Paper"` | `"  Paper"` |
| tesseract / tables-heldout-03 / r1c1 | `"32"` | `""` |
| tesseract / tables-heldout-03 / r1c2 | `"G6"` | `""` |
| tesseract / tables-heldout-03 / r2c0 | `"Bark"` | `"Bark"` |
| tesseract / tables-heldout-03 / r2c1 | `"35"` | `""` |
| tesseract / tables-heldout-03 / r2c2 | `"J2"` | `""` |
| paddle / tables-heldout-01 / r0c0 | `"Sample"` | `" Sample"` |
| paddle / tables-heldout-01 / r0c1 | `"Number"` | `" Number"` |
| paddle / tables-heldout-01 / r0c2 | `"Box"` | `"Box"` |
| paddle / tables-heldout-01 / r1c0 | `"Quartz"` | `"Quartz"` |
| paddle / tables-heldout-01 / r1c1 | `"17"` | `"7"` |
| paddle / tables-heldout-01 / r1c2 | `"E5"` | `"E5"` |
| paddle / tables-heldout-01 / r2c0 | `"Feldspar"` | `"Feldspar"` |
| paddle / tables-heldout-01 / r2c1 | `"28"` | `"28"` |
| paddle / tables-heldout-01 / r2c2 | `"H9"` | `"H9"` |
| paddle / tables-heldout-02 / r0c0 | `"Sample"` | `"Sample"` |
| paddle / tables-heldout-02 / r0c1 | `"Number"` | `"Number"` |
| paddle / tables-heldout-02 / r0c2 | `"Box"` | `"Box"` |
| paddle / tables-heldout-02 / r1c0 | `"Moss"` | `"Moss"` |
| paddle / tables-heldout-02 / r1c1 | `"23"` | `"2"` |
| paddle / tables-heldout-02 / r1c2 | `"F8"` | `"F8"` |
| paddle / tables-heldout-02 / r2c0 | `"Bark"` | `"Bark"` |
| paddle / tables-heldout-02 / r2c1 | `"35"` | `"35"` |
| paddle / tables-heldout-02 / r2c2 | `"J2"` | `"J2"` |
| paddle / tables-heldout-03 / r0c0 | `"Sample"` | `"Sample"` |
| paddle / tables-heldout-03 / r0c1 | `"Number"` | `" Number"` |
| paddle / tables-heldout-03 / r0c2 | `"Box"` | `"Box"` |
| paddle / tables-heldout-03 / r1c0 | `"Paper"` | `"Paper"` |
| paddle / tables-heldout-03 / r1c1 | `"32"` | `"32"` |
| paddle / tables-heldout-03 / r1c2 | `"G6"` | `"G6"` |
| paddle / tables-heldout-03 / r2c0 | `"Bark"` | `"Bark"` |
| paddle / tables-heldout-03 / r2c1 | `"35"` | `"35"` |
| paddle / tables-heldout-03 / r2c2 | `"J2"` | `"J2"` |

## Confidence, omissions, and runtime

Confidence values are engine-specific, uncalibrated native scores, not probabilities. No acceptance threshold was created. Omitted regions have no recognition confidence. Existing geometry-linked diagnostics on A–O are retained in `heldout-results.v1.json`; phone correctness cannot use the master-coordinate matcher.

- tesseract: 16 missing A–O regions; 564 geometry-linked correct units and 39 error-labelled units. Error-labelled confidence min/median/max: 0.0000/95.0000/96.1984. Page mean-confidence/CER Pearson r: -0.2387. Single-run-per-page engine-call latency median/min/max/SD: 200.53/91.17/375.05/47.22 ms. These timings include loading and are not repeated benchmark trials.
- paddle: 0 missing A–O regions; 113 geometry-linked correct units and 33 error-labelled units. Error-labelled confidence min/median/max: 0.0000/0.9693/0.9998. Page mean-confidence/CER Pearson r: -0.0109. Single-run-per-page engine-call latency median/min/max/SD: 2572.07/2159.87/8812.47/1090.26 ms. These timings include loading and are not repeated benchmark trials.

Existing development baseline medians were 223.33 ms for Tesseract and 2418.86 ms for Paddle. Development Paddle worker-only median peak RSS was about 688 MB; process-tree peak memory was unavailable. These are local macOS CPU observations, not Linux deployment measurements. Frozen selected-run timings and confidence aggregates are included in the machine-readable comparison.

## Decision and limitations

Choose C: neither engine is currently suitable for automatic production acceptance. Paddle has lower pooled CER and better table/degradation coverage, but loses substantial genuine-photo content and has slightly worse pooled WER. Tesseract retains all phone tokens and runs much faster here, but completely misses uneven-lighting pages, misses table cells, and regresses on skew/low resolution. Both fail column order. There is no defensible universal automatic-acceptance threshold.

Review-first is required for any future implementation; do not auto-accept based on confidence alone. Tesseract is the stronger observed phone-text option, while Paddle is stronger on table-cell recovery and several degraded inputs. This does not promote either to an unqualified production winner.

The run was performed in the current local macOS environment under the explicit final-evaluation request. It does not satisfy the frozen protocol’s separate Linux CPU qualification or establish OS/container-level network isolation. The unchanged Paddle worker uses local models and a Python network-denial audit hook; that hook is not an OS security boundary. Linux deployment, memory containment, and operational robustness remain unqualified. No claim of production readiness follows from completion of this held-out run.

Only three genuine phone pages and three cases per category were available; A–O pages are sparse synthetic sources sharing the frozen renderer. Development phone pages had only two short lines, whereas held-out passages are longer. Corpus composition affects pooled scores. Source independence and hashes passed, but independent external corpus review is not established. Manifest hashes detect ordinary changes and the reservation prevents ordinary reruns; this is not a tamper-proof external audit log.

Configurations and all ground truth remained frozen. The one-time held-out evidence is final evaluation only, never tuning. Future production implementation requires a separate task and review.

## Final checks

148 OCR research tests and 66 PDF research tests passed. Ruff, formatting, and
configured mypy (metrics/schemas scope) passed. Development freeze and execution
hashes passed. Alembic remains `0008_pdf_text_extraction`; no migration 0009 or
production changes. No commit or push was performed.
