# Phase 2B: direct PDF extraction evaluation

Research-only harness around the unchanged production `runner.run` child-process
interface. No application database or accounts are needed for the benchmark. No OCR,
NLP endpoint calls, migrations or production imports of research are introduced.
Read [protocol.md](protocol.md) before interpreting results.

From this directory, with Python 3.13 and uv:

```sh
uv sync --locked
uv run --locked pytest
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy

uv run --locked python evaluate.py generate --root artifacts/my-corpus
uv run --locked python evaluate.py validate --root artifacts/my-corpus
uv run --locked python evaluate.py run --root artifacts/my-corpus --output artifacts/my-development
uv run --locked python evaluate.py freeze --root artifacts/my-corpus
uv run --locked python evaluate.py generate --root artifacts/my-corpus --split heldout
uv run --locked python evaluate.py validate --root artifacts/my-corpus
uv run --locked python evaluate.py run --root artifacts/my-corpus --split heldout --output artifacts/my-heldout
uv run --locked python evaluate.py performance --root artifacts/my-corpus --output artifacts/my-performance
```

Do not run another primary experiment on the same holdout after tuning production.
The initial evaluated production baseline is
`592b1c6c42a8d7fcaab14123703e5a560dccecad`. A current clean production tree and matching
commit are required. The locked pypdf is 6.21.0; ReportLab/Pillow are research-only
fixture authoring dependencies. The isolated child runs with this research interpreter;
both research and backend lock hashes are recorded to distinguish runtime environments.

`manifests/benchmark.schema.json` is the exported Pydantic manifest schema;
`schemas/result.schema.json` describes top-level JSONL records. Pydantic models in
`schemas/__init__.py` are authoritative. To supply externally authored original material,
create a manifest entry with tool/version/license provenance and relative PDF, authoring
JSON, page references, assembly and structural annotation files matching the generator's
source schema. `validate` checks paths, SHA-256, byte counts, source/reference consistency,
page offsets, tokens, category/split values, duplicate bytes and template-family leakage.
No extractor is used to produce or validate ground truth.

Bulk PDFs, references and reports live under ignored `artifacts/`. The small versioned
manifest contains paths and hashes, not PDF binaries or bulk ground-truth text. Preserve
raw artifacts locally when reviewing this change; they are deliberately absent from Git.
JSONL is authoritative, including per-repetition outcomes; CSV is a flat summary with
blank cells representing null. `report --root ... --output ...` regenerates derived
summaries without rerunning extraction. Development `run --resume` skips completed IDs
only when environment, code and manifest provenance match; incomplete repetitions remain
in the timing audit log. Held-out primary execution has an exclusive corpus-level claim
and cannot resume or overwrite. Do not delete claim/freeze files to disguise reruns.

The default run has two warmups and ten measured fresh-child runs per document. The
separate performance command evaluates three development classes with 100 repetitions
and empirical nearest-rank p95. No reliable per-child RSS is exposed by the production
runner; memory is null with a reason. macOS has no claimed hard parser-memory limit.
Host CPU/RAM queries may be unavailable in a restricted execution environment.

Research unit tests cover metric edge cases, artifact/schema corruption, independent
source assembly, ordering, output validation, CLI guards/resume, aggregation, adapter
provenance, harmless process faults and safe parser rejection. Mypy strict checking is
configured for the independent metrics and schema modules; orchestration/generator
modules currently rely on runtime validation and tests. Production integration tests
remain the authority for storage, auth, transactional publication and no automatic NLP.

The 66-document corpus is exploratory. One PDF authoring engine, small documents,
limited fonts/scripts, no human layout raters and artificial content limit generality.
Exact embedded-text matches on image-only documents do not imply visible content was
recovered. Reports retain a separate visible-content diagnostic and content assessment.
See EVALUATION.md for the completed local experiment and its limitations.
