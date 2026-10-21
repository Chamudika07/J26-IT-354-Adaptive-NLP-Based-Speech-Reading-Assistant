# Paddle English recognizer decision on 32 development cases

The planned `PP-OCRv5_mobile_det` + `en_PP-OCRv5_mobile_rec` comparison **already
existed**. Its baseline and grayscale runs each contain 30 A–O cases plus two genuine
Category P phone photos. No OCR was rerun for this decision. All four A–O and four
phone-photo Paddle run directories match their archived config/page/summary hashes;
all 32 rows per condition succeeded. Across the four conditions, fixture IDs, source
hashes, ground-truth hashes, categories, and reference denominators match exactly.
The detector, PaddleOCR/PaddlePaddle 3.2.0 runtime, adapter, and metric definitions
are unchanged. This is development evidence, not held-out or production selection.

The shared detector revision is `0d63e78e2b680928f6b1747d76a08db6e645efb7`
(weights SHA-256 `afa1820cb16c1fd0dad589d0f8b389139061c1ef6d68019685fd07be997dda5b`).
The v4 English recognizer revision is `f97b62fdc0eb71c689393a19a4b21baa1795c9ab`
(weights SHA-256 `75f64a1ffb70c56b7a25655963ca16f5bf3286202e3f52ac972bee05cdee2f56`).
The v5 English recognizer revision is `267c36e24c331595590fe7bd72bde2436fd286f2`
(weights SHA-256 `3ec8a97ed6cefe8568d3e2ee90bb193299b566a7661aa4fd52d224b96b59f66b`).
All files in both pinned [v4 bundle](manifests/artifacts.v1.json) and
[v5 bundle](manifests/artifacts-paddle-v5-development.v1.json) pass byte-size and
SHA-256 verification. The [A–O run index](manifests/paddle-v5-development-comparison.v1.json)
and [phone run index](manifests/photo-development-run-index.v1.json) identify every
archived result and its hash.

## Transcription results

Each condition has 2,514 reference characters and 418 reference words. Raw Unicode
CER/WER and strict exact match retain the authored ground truth. The newline diagnostic
only replaces authored double-newline block separators with single newlines before
comparing assembled text; it is not a primary score.

| Recognizer | Recipe | Micro CER | Micro WER | Strict exact | Newline diagnostic exact | Failures |
|---|---|---:|---:|---:|---:|---:|
| v4 English | baseline | 226/2514 = 8.9897% | 49/418 = 11.7225% | 0/32 | 18/32 | 0 |
| **v4 English** | **grayscale** | **226/2514 = 8.9897%** | **46/418 = 11.0048%** | **0/32** | **19/32** | **0** |
| v5 English | baseline | 268/2514 = 10.6603% | 50/418 = 11.9617% | 0/32 | 24/32 | 0 |
| v5 English | grayscale | 244/2514 = 9.7056% | 43/418 = 10.2871% | 0/32 | 25/32 | 0 |

The v5 grayscale WER is 0.7177 percentage points lower than v4 grayscale, while
its CER is 0.7159 points higher. Strict exact match is zero because of more than
recognition errors: Paddle joins native lines with a single newline where authored
blocks have two. The diagnostic counts pages whose only mismatch is that separator.

Each category cell below is micro CER/WER in percent over two pages, ordered
v4 baseline, v4 grayscale, v5 baseline, v5 grayscale.

| Category | v4 baseline | v4 grayscale | v5 baseline | v5 grayscale |
|---|---:|---:|---:|---:|
| accented_english_unicode | 8.11/25.00 | 8.11/25.00 | 2.70/5.00 | 2.70/5.00 |
| clean_digital_scan | 1.64/0 | 1.64/0 | 1.64/0 | 1.64/0 |
| grayscale_scan | 2.48/5.88 | 2.48/5.88 | 1.65/0 | 1.65/0 |
| illustration_text | 2.01/3.03 | 1.51/0 | 2.01/3.03 | 2.01/3.03 |
| low_contrast | 1.79/0 | 1.79/0 | 1.79/0 | 1.79/0 |
| low_resolution | 1.61/0 | 1.61/0 | 1.61/0 | 1.61/0 |
| mild_blur | 1.75/0 | 1.75/0 | 1.75/0 | 1.75/0 |
| mixed_fonts_sizes | 3.08/0 | 3.08/0 | 2.64/0 | 2.64/0 |
| noise_compression | 1.72/0 | 1.72/0 | 1.72/0 | 1.72/0 |
| perspective_distortion | 3.48/0 | 3.48/0 | 1.74/0 | 1.74/0 |
| punctuation_numbers_symbols | 1.75/0 | 1.75/0 | 1.75/0 | 1.75/0 |
| skew_rotation | 2.73/0 | 2.73/0 | 1.82/0 | 1.82/0 |
| tables | 18.80/9.09 | 18.80/9.09 | 18.80/9.09 | 18.80/9.09 |
| two_column | 27.27/40.00 | 27.27/40.00 | 26.92/33.33 | 26.92/33.33 |
| uneven_lighting | 1.77/0 | 1.77/0 | 1.77/0 | 1.77/0 |
| **phone_camera_photo** | **5.07/16.00** | **5.80/8.00** | **44.93/64.00** | **27.54/36.00** |

The A–O v5 improvements are real within this small synthetic corpus: accented text
improves markedly, punctuation/numbers tie, and v5 reduces two-column transcription
error. But on the two genuine, short phone photos v5 often truncates the body line.
With grayscale, photo 01 is nearly exact, while photo 02 loses most of its body text;
baseline v5 loses substantial text on both. V4 grayscale retains far more photo text.
The two photos do not establish robustness on longer photographed pages.

## Layout, confidence, and cost

The saved A–O geometry diagnostics give both recognizers 7/8 required adjacent
precedence pairs on each two-column page under both recipes. Both place the right
heading before the final left paragraph. V4 has 15/18 exact table-cell texts; v5 has
16/18, with no missing table region for either. Both satisfy all annotated table
precedence pairs. Neither adapter supplies semantic row/column membership.

On A–O, geometry-linked native-line confidence diagnostics label 77 correct and
20 incorrect lines for v4 baseline, versus 92 correct and five incorrect for v5
baseline. Sixteen v4 errors and two v5 errors still have scores at least 0.9.
Confidence is an uncalibrated native score; omitted text has no score. On the phone
photos, v5's truncated body candidates have native scores about 0.54–0.57, whereas
v4 grayscale's imperfect photo 02 body scores 0.810. Scores cannot justify a
production acceptance threshold from these samples.

A–O median fresh-process engine-call latency was 2418.86/2469.03 ms for v4
baseline/grayscale and 2486.39/2538.28 ms for v5 baseline/grayscale. Median
worker-only peak RSS was 688,185,344/688,308,224 bytes for v4 and
688,521,216/679,329,792 for v5. One v5 baseline worker reached 910,753,792
bytes. Separate two-photo call medians were 3577.32/3776.22 ms for v4 and
4425.87/2299.39 ms for v5; these tiny samples are not a controlled speed study.
Simultaneous process-tree peak memory was unavailable.

## Development decision

**Retain `PP-OCRv5_mobile_det` + `en_PP-OCRv4_mobile_rec` with grayscale** as the
development Paddle configuration. V5 helps A–O and has slightly lower pooled WER
under grayscale, but its severe phone-body omissions and higher pooled CER are a
material regression on the only genuine photo samples. This is a final choice for
the frozen **development configuration**, not a production OCR engine selection.
Tesseract's frozen development configuration remains PSM 3 with contrast ×1.3.
Held-out execution count remains zero.
