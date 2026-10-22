# Held-out corpus preparation v1

Prepared on 2026-10-22 from the development freeze at `60a330c`.
No OCR was executed, no engine was selected for production, and no development
source, metric, configuration, or frozen file was changed.

## Inventory

`manifests/heldout-preparation.v1.json` is the preparation/provenance overlay for
the 48 reserved held-out slots in the unchanged `manifests/benchmark.v1.json`.
The original benchmark's planned flags remain historical; the overlay records
current preparation state separately from execution state.

- Categories A–O: 45 prepared image/ground-truth pairs, three per category.
- Category P: three prepared print-master/ground-truth pairs; three real photos registered.
- Held-out OCR executions: **0**.

Artifacts are local and ignored by Git under `artifacts/heldout-preparation-v1/`.
Each image has a matching `.truth.json`; A–O pairs are in `ao/`, and Category P
pairs are in `phone-print-masters/`. Each directory also has `index.json`.
The provenance overlay records SHA-256 hashes, fixture and source-family IDs,
generator versions, dependency-lock/code hashes, and degradation parameters.
Contact sheets are convenience previews, not benchmark inputs.

## Print and capture

Print each of these original PNG masters fitted to A4 portrait paper:

- `artifacts/heldout-preparation-v1/phone-print-masters/phone_camera_photo-heldout-01.png`
- `artifacts/heldout-preparation-v1/phone-print-masters/phone_camera_photo-heldout-02.png`
- `artifacts/heldout-preparation-v1/phone-print-masters/phone_camera_photo-heldout-03.png`

They contain original educational passages about bridge expansion joints, tree
rings, and periscopes, with normal paragraphs and 80–120 words including headings.
The 1600 × 2263 raster pages preserve the existing print-master layout, using
Bitstream Vera with a 31-pixel body font (about 11.5 points fitted to A4).

Registered genuine captures are at:

- `artifacts/phone_photos/heldout/phone_camera_photo-heldout-01.jpg`
- `artifacts/phone_photos/heldout/phone_camera_photo-heldout-02.jpg`
- `artifacts/phone_photos/heldout/phone_camera_photo-heldout-03.jpg`

All three are available. Their verified hashes, byte counts, dimensions, JPEG format,
and user-attested capture type are recorded in the preparation manifest.
Print masters are not substitutes for camera captures.
The current ground-truth polygons describe the print masters; future photo
registration/geometry still require validation before any spatial photo diagnostics.
Photo capture provenance and filename-to-passage matches have been verified; ground
truth remains unchanged.

## Reproducibility and validation

The dedicated held-out renderers preserve development-v3 canvas, font selection,
layout, and degradation semantics while replacing educational text. They are
separate snapshots to avoid modifying frozen development code. Degradations use
the unchanged shared implementation and seed 22081766. Authoring is nonrandom.
All content is original project-authored synthetic material with no learner data.

From this directory, run `uv run python heldout_preparation.py` to validate the
existing preparation. `--prepare` is only for first-time generation and refuses
to overwrite existing artifacts or the preparation manifest. Neither mode imports
or invokes OCR engines. Do not execute held-out OCR until separately authorized.

Validation checks the benchmark schema, exact fixture/category counts, source
families, generator hashes, all ground-truth hashes/tokens/layout geometry, image
hashes/pixels, development text overlap, within-held-out duplicates, and pending
phone metadata in both pending and available lifecycle states. It also rejects persisted held-out result rows under `artifacts/`
and `results/`. Preparation tests require the local artifacts; on a fresh checkout
those integration checks explicitly skip until the corpus is prepared.

Validation at preparation: 122 OCR research tests and 66 PDF research tests passed;
OCR Ruff and formatting checks passed; configured OCR mypy passed (metrics and
schemas scope). The development-freeze verifier passed. Alembic remains at the
single head `0008_pdf_text_extraction`. No production files were changed.

## Registered-photo pre-run validation

Run `uv run python heldout_preparation.py --pre-run` to require all three registered
photos and verify the development freeze as well as the full preparation checks.
The ordinary validator also supports the earlier pending state, where photos must
be absent. Extra files in the held-out photo directory are rejected. No command
executes OCR. The top-level `prepared_not_executed` status remains unchanged.

The `source_digest` and `image` fields continue to describe each print master;
`photo_source_digest` and `expected_photo_path` describe the genuine capture.
The category identifier remains `phone_camera_photo` (Category P in the protocol).
The registration record preserves the prior manifest and validator hashes, while
`file_sha256` identifies the current lifecycle-aware validator. The 45 A–O records,
source generators, all ground truth, and JPEG bytes are unchanged.

Registration checks: 142 OCR research tests and 66 PDF research tests passed.
Ruff, formatting, configured mypy, and pre-run/development-freeze validation passed.
Held-out OCR executions remain **0**.
