# Category P photo development evaluation and configuration freeze

The two user-supplied JPEGs were visually inspected and matched to the **archived
two-line `development-drafts-v1` print masters and their unchanged ground truth**.
They do not depict the longer `development-v2` print sheets authored later. Both
versions are preserved; the later sheets are unused alternatives. Genuine phone-camera
capture is user-attested, not independently provable from file metadata. The visible
pages contain no private or child data. This is development evidence only.

| Fixture | Printed title | JPEG bytes | Decoded size/pixels | JPEG SHA-256 | Ground-truth SHA-256 |
|---|---|---:|---:|---|---|
| `phone_camera_photo-development-01` | Photo print master one | 32,884 | 959×1280 / 1,227,520 | `75d5bec373b3a15e8ca6bf33e747e347fcac2bfafc24443bc0727a46fd2b2743` | `afe8210e1c638e4cb0bfc618eca95bbcc1d4970b237db87847b75c770db5828e` |
| `phone_camera_photo-development-02` | Photo print master two | 31,088 | 960×1280 / 1,228,800 | `e70ea27c0e97c91969263d4c7d9ddf4e16306c2317586a14b3cb98594d4700bb` | `c94c7dd7c390864a7a5e3884217cbebd1804e82fad67ec452207ed74291aab8e` |

Both files have JPEG/JFIF signatures, decode as single-frame RGB JPEGs, meet the
10 MiB/6000-pixel-side/12-million-pixel limits, and have no EXIF orientation or other
EXIF tags. The decoder applies EXIF transpose once when present, converts to RGB and
clears image metadata; normalized pixel digests are checked. Source family, original
master hashes, dimensions, capture attestation and absence of observed private data
are recorded in [phone-development.v1.json](manifests/phone-development.v1.json).
Binary photographs and native OCR output remain ignored by Git.

The [32-source validation](artifacts/validation-development-32-v1/validation.json)
passed: 30 distinct A–O synthetic development cases plus these two distinct genuine
photos, two source families in each of 16 categories, no held-out input opened. The
earlier defective accented-corpus and pre-fix attempts remain excluded.

## Category P OCR observations

All six two-photo runs succeeded as engine calls. Character and word S/D/I are
substitutions/deletions/insertions. Strict exact comparison retains the authored
double-newline separator and all emitted whitespace.

| Engine/config | Photo | Char S/D/I | CER | Word S/D/I | WER | Exact | Engine-call ms |
|---|---|---:|---:|---:|---:|---:|---:|
| Tesseract baseline | 01 | 2/0/9 | 16.18% | 2/0/0 | 16.67% | no | 372.63 |
| Tesseract baseline | 02 | 0/0/7 | 10.00% | 0/0/0 | 0.00% | no | 209.07 |
| Tesseract contrast ×1.3 | 01 | 2/0/9 | 16.18% | 2/0/0 | 16.67% | no | 198.72 |
| Tesseract contrast ×1.3 | 02 | 0/0/7 | 10.00% | 0/0/0 | 0.00% | no | 151.04 |
| Paddle v4 English baseline | 01 | 0/3/0 | 4.41% | 1/1/0 | 16.67% | no | 4227.11 |
| Paddle v4 English baseline | 02 | 0/4/0 | 5.71% | 2/0/0 | 15.38% | no | 2927.52 |
| Paddle v4 English grayscale | 01 | 0/1/0 | 1.47% | 0/0/0 | 0.00% | no | 4451.07 |
| Paddle v4 English grayscale | 02 | 0/7/0 | 10.00% | 2/0/0 | 15.38% | no | 3101.37 |
| Paddle v5 English baseline | 01 | 0/39/0 | 57.35% | 1/7/0 | 66.67% | no | 5329.24 |
| Paddle v5 English baseline | 02 | 0/23/0 | 32.86% | 7/1/0 | 61.54% | no | 3522.50 |
| Paddle v5 English grayscale | 01 | 0/1/0 | 1.47% | 0/0/0 | 0.00% | no | 2382.27 |
| Paddle v5 English grayscale | 02 | 0/37/0 | 52.86% | 4/5/0 | 69.23% | no | 2216.50 |

Pooled over these **two** photos (138 reference characters, 25 words): Tesseract
baseline and contrast both have **13.04% CER / 8.00% WER**. Paddle v4 baseline has
**5.07% / 16.00%**, v4 grayscale **5.80% / 8.00%**, v5 baseline **44.93% / 64.00%**,
and v5 grayscale **27.54% / 36.00%**. These percentages are highly sensitive to a
few characters and words. No setting was tuned after viewing photo outputs.

On both pages, all engines emit the title before a body-line candidate: **1/1 simple
title→body precedence per photo** by visual/native sequence inspection. This does not
test two-column reading order. Tesseract also emits whitespace-like units before the
title, with native confidence around 95, explaining many strict character insertions;
on photo 01 it reads `a` as `@` under contrast and changes the terminal period to a
comma. Photo 02's words are correct under Tesseract, but leading whitespace prevents
strict exact match. Paddle v4 grayscale transcribes photo 01's words exactly; only
the single-versus-double newline prevents strict exact match. Its photo 02 body has
missing letters despite a native line score of 0.810. Paddle v5's body line is badly
truncated on photo 02 under both settings, and on photo 01 under baseline. No photo
caused an adapter failure, crash or timeout.

For selected settings, Tesseract contrast's median confidence over nonblank emitted
words is 92.50 on photo 01 and 95.54 on photo 02 (native 0–100 scale). Paddle v4
grayscale's two-line median scores are 0.951 and 0.891 (native 0–1 scale). These
scales and unit types cannot be compared directly. Selected-setting median engine-call
latency over two photos is 174.88 ms for Tesseract and 3776.22 ms for Paddle v4.
Only Paddle worker-only peak RSS was available for these photo calls (660,996,096
and 666,189,824 bytes under v4 grayscale); simultaneous process-tree peak is null.
Two observations do not establish a latency or memory distribution.

## Complete 32-case development comparison

This combines the saved 30 A–O results with the two photo runs without rerunning A–O.
The denominator is 2514 characters and 418 words per condition.

| Configuration | 32-case micro CER | 32-case micro WER | Strict exact pages |
|---|---:|---:|---:|
| Tesseract baseline | 18.5362% | 21.7703% | 16/32 |
| **Tesseract contrast ×1.3** | **18.3373%** | **20.8134%** | 16/32 |
| Paddle v4 English baseline | 8.9897% | 11.7225% | 0/32 |
| **Paddle v4 English grayscale** | **8.9897%** | **11.0048%** | 0/32 |
| Paddle v5 English baseline | 10.6603% | 11.9617% | 0/32 |
| Paddle v5 English grayscale | 9.7056% | 10.2871% | 0/32 |

Paddle v5 still has lower pooled WER than v4 grayscale, but its severe omissions on
these genuine photos are an important regression; v4 grayscale also has the lower
32-case CER. These samples are exceptionally short and do not establish how either
recognizer handles longer natural photographed passages.

**Development configuration freeze:** Tesseract 5.5.3, English tessdata_fast and PSM 3
with contrast ×1.3; PaddleOCR/PaddlePaddle 3.2.0 with `PP-OCRv5_mobile_det` +
`en_PP-OCRv4_mobile_rec`, CPU/one thread and grayscale preprocessing. The exact model,
adapter, metric, rasterizer, corpus and configuration hashes are bound in
[development-configuration-freeze.v1.json](manifests/development-configuration-freeze.v1.json).
This freezes development selection only. **No production engine is selected; held-out
execution count remains zero.** The three held-out phone photographs are still absent.

After macOS read access was restored, both original JPEGs were readable and their
SHA-256 values matched the registry. The full 32-source validator and
development-freeze verifier passed again. The verifier now resolves registry paths
relative to the research directory, including when invoked from the repository root;
its updated source hash is recorded in the freeze manifest. No photo bytes, metadata
or ground truth were altered.
