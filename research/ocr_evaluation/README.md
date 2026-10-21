# OCR evaluation research tooling

This is a **32-case development OCR comparison with development settings frozen**, not a qualified production
OCR system. Production code and Phase 2B remain unchanged. See [EVALUATION.md](EVALUATION.md) for measured status
and [PADDLE_V5_DEVELOPMENT.md](PADDLE_V5_DEVELOPMENT.md) for the recognizer check.
[protocol.md](protocol.md) describes the planned experiment and remaining gates.
The current 32-case development results and selected settings are in
[CATEGORY_P_DEVELOPMENT.md](CATEGORY_P_DEVELOPMENT.md).

Use the project-local Python 3.12 environment, never the backend or global conda environment:

```sh
cd research/ocr_evaluation
UV_CACHE_DIR=/tmp/ocr-uv-cache uv sync --locked --python /opt/homebrew/bin/python3.12 --extra paddle
uv run --locked pytest
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy
uv run --locked python evaluate.py --validate
uv run --locked python -m generators.render_development --output artifacts/development-drafts-v3
```

On Linux use an installed Python 3.12 path instead. The manifest reserves 80 base slots;
the synthetic generator creates 30 non-photo development drafts. The two genuine
development photos depict the archived two-line v1 print masters; see
[PHONE_PHOTOS.md](PHONE_PHOTOS.md) for all five filenames and directories.
No held-out generator/executor is exposed. Existing output directories are never overwritten.
The separate corpus.py command emits authoring packets only, not benchmark images.

All large/raw data live in ignored artifacts/ or models/: corpus, pixels, references,
models, JSONL, native outputs, timings and bulk reports. Commit only source, schemas,
protocol, small provenance manifests and concise findings after explicit authorization.
Production must never import this directory. Never copy learner or private school data here.

Adapters: Tesseract TSV parser/executable bridge; Paddle local-bundle verifier, normalized
result parser and fresh CPU worker. Both have executed real local inference on the corrected A–O development corpus.
Paddle caches must use PADDLE_PDX_CACHE_HOME pointing to disposable research storage.
The two Category P development cases are registered; three held-out photos remain
pending. No production engine selection or held-out OCR claim exists.

## Development execution

`development.py` validates the entire selection's split/category/family metadata before
opening any source, then checks source and ground-truth SHA-256. Only direct PNG
non-photo development inputs are accepted in this stage. With a verified local engine
bundle, run:

```sh
uv run --locked python development.py \
  --index artifacts/development-drafts-v3/index.json \
  --config artifacts/local-engine-config.json \
  --output artifacts/development-engine-run-01
```

The config JSON requires `experiment_id`, `engine` (`tesseract` or `paddle`),
`engine_version`, `runtime_version`, `model_root`, and nonempty `artifacts` matching
schemas/artifact.schema.json. Tesseract additionally requires `executable`, with optional
`psm` (default 3). Paddle requires `detection_dir` and `recognition_dir`, relative to
model_root. Common `recipe` defaults to baseline and `parameters` to an empty object.
No example with invented hashes is supplied: populate these from actual verified files.
Each artifact must record the actual pinned engine/runtime versions and upstream revision.

`photo_development.py` validates and runs only the two registered development JPEGs.
`validate_development_32.py` audits all 32 sources; `verify_development_freeze.py`
checks the development-only freeze. The runner creates its output exclusively, records config fingerprint/native output/
assembled text and page JSONL, and writes a summary. Failures retain stage and exception
class without forwarding learner/source content. It does not execute held-out, select an
engine, infer layout matches, or establish final performance qualification. Unit tests use
labelled stub adapters only in temporary directories, never as benchmark evidence.
