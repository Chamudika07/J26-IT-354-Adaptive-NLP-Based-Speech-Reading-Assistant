# Phase 2B local evaluation record

The approved research harness is complete. Production behavior was not changed.
The final held-out evaluation ran once after the final development run and freeze.
This report describes the preserved local artifacts, not universal PDF accuracy.

1. **Partial work preserved.** The continuation found the isolated environment/lock,
   metrics, schemas, adapter, generator, evaluator, reporter, protocol, artifact policy
   and 17 metric tests. Those tests and configured mypy passed; Ruff found one long line.
   No benchmark PDFs or held-out results existed at continuation start.
2. **Files completed/fixed.** Corrected reporting/lint, byte-exact UTF-8 reference reads
   (no newline translation), schema constraints, source/visible-reference/offset/token
   validation, glyph/page bounds, duplicate PDF detection, caption IDs, distinct raster
   fixtures, full reporting and provenance, resume/freeze/primary-run safeguards.
   Added README, this report, manifest/result JSON Schemas, the 66-entry versioned
   manifest, freeze/run index, harness tests and separate robustness tests. All source
   changes are under `research/pdf_extraction`; all remain untracked, ready for review.
3. **Research dependencies.** Runtime locks: pypdf 6.21.0, Pydantic 2.14.1, ReportLab
   4.5.1, Pillow 13.0.0. Development: pytest 9.1.1, Ruff 0.17.1, mypy 1.20.2.
   Production dependency files are unchanged. ReportLab/Pillow author synthetic fixtures;
   the adapter invokes the real existing production child runner for evaluation.
4. **Production files changed:** none. No OCR, application schema, migration, real `.env`,
   production setting, learner data or automatic NLP invocation was added.
5. **Development corpus:** 22 final fixtures, two per category. Initial development-v1
   artifacts remain intact; duplicate raster templates discovered during development
   were corrected in final-corpus-v1. The final development run uses the frozen code.
6. **Held-out corpus:** 44 fixtures, four per category. Combined final corpus: 66 unique
   PDF hashes, no template-family overlap. Source JSON, page/assembly/visible references,
   structure, tokens and hashes were validated independently of extractor output.
7. **Held-out execution:** one primary run, 44 result records and 440 measured fresh-child
   repetitions, plus two unmeasured warmups per document. Its exclusive claim is preserved.
   No production tuning or held-out rerun occurred. The performance subset uses only dev.
8. **Benchmark/schema/protocol:** benchmark-v1 / schema 1 / protocol-v1; corpus
   original-pdf-66-v1; deterministic order seed 22081766. See the versioned manifest.
9. **Metric version:** pdf-fidelity-v1. Raw code-point CER and maximal-non-whitespace WER;
   no case/punctuation/whitespace rewriting. Counts and undefined-denominator statuses
   are preserved; normalized/NFC diagnostics never replace primary metrics.
10. **Evaluated production provenance:**
    - commit: `592b1c6c42a8d7fcaab14123703e5a560dccecad`
    - extraction fingerprint:
      `94ba2457f33d1def1cd265149852e8dd9b8b32ef31450829c7b44de61b54e14c`
    - pypdf 6.21.0, Python 3.13.0, Unicode 15.1.0, macOS 26.3.1 arm64.
      Both dependency lock hashes and all frozen file hashes are retained.
11. **Final development results:** 22/22 policy agreement; 20/20 eligible embedded exact
    matches, including one empty-reference fixture. Two unsupported/invalid fixtures
    excluded from fidelity. Raw micro CER 0/2244 = 0%; WER 0/389 = 0%. Independent
    visible-content diagnostics: CER 134/2378 = 5.635%; WER 22/411 = 5.353%.
    Review labels: 17 correct, 3 needs_review, 2 extraction_failure. One complete logo
    document conservatively routed to review. No accepted omission/order findings.
12. **Held-out results:** 44/44 policy agreement; 36/40 eligible embedded exact matches,
    including two empty-reference fixtures. Four unsupported/invalid fixtures excluded.
    Review labels: 30 correct, 10 needs_review, 4 extraction_failure. Two independently
    complete logo documents routed to review. Four accepted documents had ordering errors;
    no accepted document had an independently annotated material visible omission.
13. **Held-out fidelity:** raw assembled CER (184 S + 60 D + 60 I)/6176 = **4.9223%**;
    WER (0 S + 24 D + 24 I)/887 = **5.4115%**. Normalized diagnostics have the same
    micro rates. All embedded errors occur in four two-column fixtures: category CER
    62.2951%, WER 75%. Visible-content diagnostics additionally retain raster omissions:
    CER 615/6487 = 9.4805%; WER 96/935 = 10.2674%. These are not OCR accuracy.
14. **Routing confusion matrices:** counts below; every nonempty row has 100% on its
    diagonal and 0% elsewhere. Routing policy agreement is not completeness or order.

| Split / expected | extracted | ocr_required | needs_review | failed |
|---|---:|---:|---:|---:|
| Development extracted | 16 | 0 | 0 | 0 |
| Development ocr_required | 0 | 2 | 0 | 0 |
| Development needs_review | 0 | 0 | 2 | 0 |
| Development failed | 0 | 0 | 0 | 2 |
| Held-out extracted | 32 | 0 | 0 | 0 |
| Held-out ocr_required | 0 | 3 | 0 | 0 |
| Held-out needs_review | 0 | 0 | 5 | 0 |
| Held-out failed | 0 | 0 | 0 | 4 |

15. **Layout findings:** held-out page-ID order passed all 37 testable eligible documents;
    three lacked complete embedded page IDs and are explicitly not applicable. Four of
    37 documents with precedence pairs failed a pair: right-column content-stream order
    preceded the intended left column. Tables had no missing/altered cells or failed
    textual row/column probes. Header/footer, page-number and line-hyphen examples were
    exact. These small string-based table probes do not establish semantic reconstruction.
    Future reviewed work could address column-order detection; production stays unchanged.
16. **Performance:** normal protocol used two warmups plus ten measured serial child runs
    per document. Median of document medians: development 186.881 ms; held-out 185.399 ms.
    Held-out per-document medians ranged 132.625–188.484 ms. All 220 development and 440
    held-out measured repetitions retained the primary routing outcome. Dedicated dev
    subset used 100 measured repetitions per class; empirical nearest-rank p95 follows.

| Development subset | Median ms | Minimum ms | Maximum ms | Population SD ms | Empirical p95 ms |
|---|---:|---:|---:|---:|---:|
| Simple single column | 181.699 | 130.538 | 188.801 | 26.245 | 188.485 |
| Multipage | 187.334 | 130.618 | 232.525 | 19.658 | 188.724 |
| Two column | 180.314 | 129.801 | 188.663 | 26.686 | 188.538 |

17. **Robustness:** 14 separate research cases passed: encrypted/malformed/inert action/
    attachment/form rejection; accepted 25 pages vs rejected 26; benign malformed files
    exactly at 10 MiB and one byte over safely failed; controlled timeout/exit/bad JSON/
    unknown-code stubs; real harmless sleeping child killed and reaped. Rejections expose
    fixed codes and no partial page/text evidence. Existing production integration tests
    cover private storage, authorization, transactional revision publication, no automatic
    profile/NLP, lease/recovery and concurrency. No exploit or decompression-bomb fixtures.
18. **Research verification:** 66 tests passed; Ruff and formatting pass; configured
    strict mypy passes for metrics and schemas. All frozen hashes remain unchanged after
    held-out execution. No research coverage percentage was measured.
19. **Production verification:** 1,114 tests passed, including disposable PostgreSQL,
    migration, PDF/security, storage, publication and concurrency coverage; 94.267% total
    branch-aware coverage. Ruff/format/mypy pass (92 typed source files). One existing
    Starlette TestClient/httpx deprecation warning. Disposable database was used, not a
    production URL; no application settings file was edited.
20. **Alembic:** exactly one head, `0008_pdf_text_extraction`; `alembic check` reports no
    new upgrade operations. Migrations 0001–0008 and all production files are unchanged.
21. **Limitations:** one ReportLab authoring engine, small artificial documents and one
    laptop/runtime; family separation does not create a representative sample. Automated
    source/rubric checks have no independent human raters or rendered-page visual review.
    Font coverage is limited; combining/supplementary characters are metric-test coverage,
    not broad PDF corpus coverage. No OCR. Logos are decorative, excluded from the
    instructional visible reference. Host CPU/RAM sysctl access was denied, so RAM is
    null and CPU only identifies arm. Peak child RSS is null with reason; macOS has no
    claimed hard memory cap. No stable tail claim from ten repetitions. Controlled fault
    injection is not malicious-PDF resistance certification. Mypy scope is intentionally
    metrics/schemas; orchestration uses runtime validation and tests.
22. **Git state:** only `?? research/pdf_extraction/`; no tracked changes, commits or push.
    Bulk corpus, raw JSONL, references, derived reports and environments are ignored.
    `git diff --check` passes. No real learner/child content or copyrighted textbook
    materials were used; the bundled font is used under its recorded license.

## Preserved artifacts

- [Final development report](artifacts/development-final-v1/report.md)
- [Primary held-out report](artifacts/heldout-primary-v1/report.md)
- [Performance subset](artifacts/performance-v1/summary.json)
- [Versioned manifest](manifests/benchmark.v1.json)
- [Frozen contract](manifests/freeze.v1.json)
- [Artifact hashes](manifests/run-index.v1.json)

Local artifact links deliberately point into ignored storage. Keep those artifacts with
this evaluation record; a Git checkout alone contains code, metadata and hashes, not data.
