# English v5 recognizer: A–O development comparison — 2026-10-21

**Later evidence:** The two genuine phone photographs were subsequently evaluated and
showed a substantial v5 recognition regression against v4 on their short body lines.
See [CATEGORY_P_DEVELOPMENT.md](CATEGORY_P_DEVELOPMENT.md) for the 32-case development
decision. The v5/baseline choice at the end of this A–O-only report is superseded.

This is a **provisional A–O development Paddle configuration** comparison. It uses the
same 30 corrected, authored A–O development PNGs and frozen raw Unicode CER/WER
definitions as the earlier runs. Category P photographs do not exist; no held-out source
was generated or executed. The existing v4-recognizer results were read, not rerun or
relabelled. New v5 runs have exclusive baseline and grayscale output directories.

## Reproducible model and runtime

PaddleOCR 3.2.0, PaddlePaddle 3.2.0 and PaddleX 3.2.1 ran on macOS CPU, one thread,
MKLDNN disabled. Both configurations use `PP-OCRv5_mobile_det`, upstream revision
`0d63e78e2b680928f6b1747d76a08db6e645efb7`, weights SHA-256
`afa1820cb16c1fd0dad589d0f8b389139061c1ef6d68019685fd07be997dda5b`.
The saved comparator uses `en_PP-OCRv4_mobile_rec`, revision
`f97b62fdc0eb71c689393a19a4b21baa1795c9ab`, weights SHA-256
`75f64a1ffb70c56b7a25655963ca16f5bf3286202e3f52ac972bee05cdee2f56`.
The new candidate uses the [official English v5 mobile recognizer](https://huggingface.co/PaddlePaddle/en_PP-OCRv5_mobile_rec/tree/267c36e24c331595590fe7bd72bde2436fd286f2),
revision `267c36e24c331595590fe7bd72bde2436fd286f2`, weights SHA-256
`3ec8a97ed6cefe8568d3e2ee90bb193299b566a7661aa4fd52d224b96b59f66b`.

The new recognizer's `config.json`, `inference.json`, `inference.pdiparams`, and
`inference.yml` SHA-256 values are respectively:

```text
16103ac291a82fca50f0bb000d62a4b8168f6042f03c89c44cf32f241d1eb1f2
fd1b6ec722ea841a72d3ba43e527df1d1066d5d7808e0503ee3eec7265188753
3ec8a97ed6cefe8568d3e2ee90bb193299b566a7661aa4fd52d224b96b59f66b
27e91d0582f40168aa218303c76e184bc78fa7a5d105aad0cfbad8458b441067
```

The last file carries the recognition dictionary/config. All eight candidate bundle
files, including four unchanged detector files, passed pinned size/hash verification;
their URLs, roles and digests are in
[artifacts-paddle-v5-development.v1.json](manifests/artifacts-paddle-v5-development.v1.json).
The worker receives explicit local directories and model name, with offline resolution
enabled during inference. No runtime `latest` download is involved. Configuration
fingerprints: v5 baseline
`0f99f43a6e549b5ba3115a322f7a7914aab887412b13b93aeb0c0a2b6474b72a`,
v5 grayscale `cf2bf50f9b76bf3ae805c7ba80c60568e416e4682fb2c5a97e4334a7a7149e80`.
Saved v4 fingerprints were `a06d12cb41e6118cf0084b3cc3aaffe915ee9b814aa7ae5e5be19d4beb7f8913`
and `448061a0d4ac491463d1918c14d95e5209d7665463f7973c2e8244a425399b16`.
Per-run config, page, summary and diagnostic hashes are in
[paddle-v5-development-comparison.v1.json](manifests/paddle-v5-development-comparison.v1.json).

## Strict transcription results

All four runs completed **30/30**, with zero engine failures and zero exclusions in this
valid comparison. Reference denominators are 2376 characters and 393 words in each run.

| Recognizer | Condition | Character S/D/I | Micro CER | Word S/D/I | Micro WER | Strict exact | Separator-only diagnostic exact |
|---|---|---:|---:|---:|---:|---:|---:|
| v4 English | baseline | 100/87/32 | 9.2172% | 36/4/5 | 11.4504% | 0/30 | 18/30 |
| v5 English | baseline | 88/93/25 | 8.6700% | 24/5/5 | 8.6514% | 0/30 | 24/30 |
| v4 English | grayscale | 100/87/31 | 9.1751% | 36/4/4 | 11.1959% | 0/30 | 18/30 |
| v5 English | grayscale | 88/93/25 | 8.6700% | 24/5/5 | 8.6514% | 0/30 | 24/30 |

Strict exact uses the authored double-newline block separators. The diagnostic changes
only those separators to single newlines, matching Paddle's native line assembly; it
does not alter the primary metric or excuse remaining errors. v5 baseline improves
micro CER by 0.5471 percentage points and WER by 2.7990 points versus v4 baseline.

Each following cell is **CER/WER percent** over two cases. The small category counts
limit generalization.

| Category | v4 baseline | v5 baseline | v4 grayscale | v5 grayscale |
|---|---:|---:|---:|---:|
| accented_english_unicode | 8.11/25.00 | 2.70/5.00 | 8.11/25.00 | 2.70/5.00 |
| clean_digital_scan | 1.64/0 | 1.64/0 | 1.64/0 | 1.64/0 |
| grayscale_scan | 2.48/5.88 | 1.65/0 | 2.48/5.88 | 1.65/0 |
| illustration_text | 2.01/3.03 | 2.01/3.03 | 1.51/0 | 2.01/3.03 |
| low_contrast | 1.79/0 | 1.79/0 | 1.79/0 | 1.79/0 |
| low_resolution | 1.61/0 | 1.61/0 | 1.61/0 | 1.61/0 |
| mild_blur | 1.75/0 | 1.75/0 | 1.75/0 | 1.75/0 |
| mixed_fonts_sizes | 3.08/0 | 2.64/0 | 3.08/0 | 2.64/0 |
| noise_compression | 1.72/0 | 1.72/0 | 1.72/0 | 1.72/0 |
| perspective_distortion | 3.48/0 | 1.74/0 | 3.48/0 | 1.74/0 |
| punctuation_numbers_symbols | 1.75/0 | 1.75/0 | 1.75/0 | 1.75/0 |
| skew_rotation | 2.73/0 | 1.82/0 | 2.73/0 | 1.82/0 |
| tables | 18.80/9.09 | 18.80/9.09 | 18.80/9.09 | 18.80/9.09 |
| two_column | 27.27/40.00 | 26.92/33.33 | 27.27/40.00 | 26.92/33.33 |
| uneven_lighting | 1.77/0 | 1.77/0 | 1.77/0 | 1.77/0 |

The baseline v5 recognizer has no category-level CER/WER regression relative to v4.
Against **v4 grayscale**, v5 grayscale loses the illustration/text gain (3.03% WER
versus 0%), despite its better total error rates. On accented pages, v5 improves both
rates substantially, though it still misreads one accent in `brûlée`. Both recognizers
return the same punctuation/numeric strings, including `#27`, `12.5%`, `$3.40`,
`4/5` and `6.25%`; their category CER is caused by separator differences, with 0 WER.

## Layout, confidence and cost

Both recognizers satisfy **7/8** required precedence pairs on each two-column page,
under both conditions. Both put `right-heading` before the last left paragraph (`b3`);
v5 improves transcription but does not fix reading order. Table geometry diagnostics
show v4 **15/18** exact cell texts and v5 **16/18**, each with zero missing cell regions.
All table precedence pairs are satisfied. A blank/incorrect count remains in the first
table; flattened text and geometry do not establish semantic row/column associations.
Those association scores remain unavailable for both adapters.

Baseline confidence is native recognition score, not a calibrated probability. Geometry
linked exact-line diagnostics label v4 77 correct/20 incorrect observed lines, and v5
92 correct/5 incorrect. Of the erroneous lines, 16 v4 and 2 v5 scores are at least 0.9.
Correct/error median scores are 0.9944/0.9634 for v4 and 0.9958/0.5929 for v5.
No emitted unit lacked confidence, but omitted content has no score. Mean page score
versus CER Pearson r is -0.366 for v4 and -0.323 for v5; small, synthetic samples do
not justify an acceptance threshold.

Median fresh-process engine-call latency over the 30 development pages was 2418.86 ms
for v4 baseline, 2486.39 ms for v5 baseline; grayscale was 2469.03 and 2538.28 ms.
This includes startup/model loading, but separate runs were not a controlled paired
performance experiment. Median worker-only peak RSS bytes: v4 baseline 688,185,344;
v5 baseline 688,521,216; v4 grayscale 688,308,224; v5 grayscale 679,329,792.
One v5 baseline worker reached 910,753,792 bytes on an accented page, so memory tails
need further study. Reliable simultaneous process-tree peak RSS was not measured.

## Provisional decision and boundary

Use **PP-OCRv5_mobile_det + en_PP-OCRv5_mobile_rec with baseline preprocessing** as
the provisional A–O development Paddle configuration. Baseline matches v5 grayscale
accuracy, avoids the small illustration/text grayscale regression against saved v4
grayscale, and had a slightly lower observed median call latency. This is not a final
engine or production configuration selection. The two real Category P development
photographs, source review, and Linux evaluation remain outstanding. Held-out execution
count is **zero**.
