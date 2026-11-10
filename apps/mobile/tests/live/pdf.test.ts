import assert from "node:assert/strict";
import test from "node:test";
import { randomUUID } from "node:crypto";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
import { ApiError } from "@j26/api-client";
import { onboard } from "./fixtures";
test(
  "real HTTP: multipart PDF upload, same-ID retry, evidence, extraction cache, denial and archive",
  { skip: process.env.MOBILE_HTTP_TEST !== "1" },
  async () => {
    const c = await onboard();
    const id = c.learner.id;
    const data = execFileSync(
      resolve("apps/backend/.venv/bin/python"),
      [
        "-c",
        "import sys; from tests.pdf_extraction.conftest import pdf_bytes; sys.stdout.buffer.write(pdf_bytes())",
      ],
      { cwd: resolve("apps/backend"), stdio: ["ignore", "pipe", "pipe"] },
    );
    const pdf = new Blob([new Uint8Array(data)], { type: "application/pdf" });
    const request = randomUUID();
    const first = await c.api.uploadPdf(id, "Synthetic PDF", request, pdf);
    assert.equal(first.extraction.status, "extracted");
    const repeat = await c.api.uploadPdf(id, "Synthetic PDF", request, pdf);
    assert.equal(repeat.source.id, first.source.id);
    assert.equal((await c.api.pdfSources(id)).items.length, 1);
    const source = await c.api.pdfSource(id, first.source.id);
    assert.equal(
      (await c.api.extractPdf(id, source.id, {})).id,
      first.extraction.id,
    );
    assert.equal((await c.api.pdfRuns(id, source.id)).items.length, 1);
    const evidence = await c.api.pdfResult(id, source.id, first.extraction.id);
    assert.match(evidence.assembled_text ?? "", /A cat rests/);
    assert.equal(evidence.pages?.length, 1);
    const other = await c.admin.createLearner({
      display_name: "Synthetic unrelated PDF reader",
    });
    await assert.rejects(
      c.api.pdfSource(other.id, source.id),
      (e) => e instanceof ApiError && e.status === 404,
    );
    await assert.rejects(
      c.api.uploadPdf(id, "Changed metadata", request, pdf),
      (e) => e instanceof ApiError && e.status === 409,
    );
    assert.ok(
      (await c.api.archivePdf(id, source.id, source.row_version)).archived_at,
    );
    await assert.rejects(
      c.api.pdfSource(id, source.id),
      (e) => e instanceof ApiError && e.status === 404,
    );
    await c.session.logout();
    await c.adminSession.logout();
  },
);
