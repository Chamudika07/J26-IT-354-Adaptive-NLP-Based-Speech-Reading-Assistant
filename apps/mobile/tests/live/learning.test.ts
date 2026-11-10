import assert from "node:assert/strict";
import test from "node:test";
import { ApiError } from "@j26/api-client";
import { workflows } from "../../src/api/workflows";
import { onboard, password, testSession } from "./fixtures";
const enabled = { skip: process.env.MOBILE_HTTP_TEST !== "1" };
test(
  "real HTTP: assessment catalog/start/detail/complete/abandon/history and authorization",
  enabled,
  async () => {
    const c = await onboard();
    const id = c.learner.id;
    assert.equal((await c.api.health()).status, "ok");
    assert.equal((await c.api.readiness()).status, "ready");
    const catalog = await c.api.assessmentMaterials();
    assert.ok(catalog.items.length);
    const material = catalog.items[0]!;
    const a = await c.api.startAssessment(id, { material_id: material.id });
    assert.equal(a.status, "started");
    const detail = await c.api.assessment(id, a.id);
    assert.ok("passage_text" in detail.material);
    const complete = await c.api.completeAssessment(id, a.id, {
      row_version: a.row_version,
      reading_duration_ms: 30000,
      attempted_word_count: 6,
      correct_word_count: 5,
      omission_count: 0,
      substitution_count: 1,
      insertion_count: 0,
      repetition_count: 0,
      self_correction_count: 0,
      unfamiliar_word_count: null,
      comprehension_correct: null,
      comprehension_total: null,
    });
    assert.equal(complete.status, "completed");
    assert.equal(Number(complete.result?.words_correct_per_minute), 10);
    const b = await c.api.startAssessment(id, { material_id: material.id });
    assert.equal(
      (await c.api.abandonAssessment(id, b.id, b.row_version)).status,
      "abandoned",
    );
    const history = await c.api.assessments(id);
    assert.equal(history.items.length, 2);
    const other = await c.admin.createLearner({
      display_name: "Synthetic unrelated assessment reader",
    });
    await assert.rejects(
      c.api.assessment(other.id, a.id),
      (e) => e instanceof ApiError && e.status === 404,
    );
    await assert.rejects(
      workflows(c.adminSession).startAssessment(id, {
        material_id: material.id,
      }),
      (e) => e instanceof ApiError && e.status === 404,
    );
    await c.session.logout();
    await c.adminSession.logout();
  },
);
test(
  "real HTTP: preferences deny educator; self read/update/reset and optimistic conflict",
  enabled,
  async () => {
    const c = await onboard();
    await assert.rejects(
      c.api.preferences(c.learner.id),
      (e) => e instanceof ApiError && e.status === 404,
    );
    const { session } = testSession();
    await session.login({ login_handle: "synthetic.mobile.reader", password });
    const api = workflows(session);
    const learner = (await api.learners()).items[0]!;
    const current = await api.preferences(learner.id);
    const saved = await api.updatePreferences(learner.id, {
      row_version: current.row_version,
      text_scale: "1.25",
      line_spacing: "1.50",
      theme: "high_contrast",
      reduce_motion: true,
    });
    assert.equal(saved.text_scale, "1.25");
    assert.equal(saved.reduce_motion, true);
    await assert.rejects(
      api.updatePreferences(learner.id, {
        row_version: current.row_version,
        theme: "dark",
      }),
      (e) => e instanceof ApiError && e.status === 409,
    );
    const reset = await api.updatePreferences(learner.id, {
      row_version: saved.row_version,
      text_scale: null,
      line_spacing: null,
      theme: null,
      reduce_motion: null,
    });
    assert.equal(reset.theme, null);
    await session.logout();
    await c.session.logout();
    await c.adminSession.logout();
  },
);
test(
  "real HTTP: original revision, new revision, stale conflict, processing history, archive",
  enabled,
  async () => {
    const c = await onboard();
    const l = c.learner.id;
    const material = await c.api.create(l, {
      title: "Synthetic initial",
      text: "A cat rests. A dog runs!",
      language_tag: "en",
    });
    assert.equal(
      (await c.api.material(l, material.id)).latest_revision.id,
      material.latest_revision.id,
    );
    const original = await c.api.revision(
      l,
      material.id,
      material.latest_revision.id,
    );
    assert.equal(original.original_text, "A cat rests. A dog runs!");
    const revision = await c.api.revise(l, material.id, {
      row_version: material.row_version,
      title: "Synthetic revision",
      text: "A small bird sings.",
      language_tag: "en",
    });
    assert.equal(revision.latest_revision.revision_number, 2);
    await assert.rejects(
      c.api.revise(l, material.id, {
        row_version: material.row_version,
        title: "Stale",
        text: "A bird sings.",
        language_tag: "en",
      }),
      (e) => e instanceof ApiError && e.status === 409,
    );
    assert.equal((await c.api.revisions(l, material.id)).items.length, 2);
    const path = {
      learner_id: l,
      material_id: material.id,
      revision_id: revision.latest_revision.id,
    };
    const run = await c.api.process(path);
    assert.equal(run.profile?.length_load.word_count, 4);
    assert.equal(
      (await c.api.result(path, run.id)).sentences?.[0]?.original_text,
      "A small bird sings.",
    );
    assert.ok(
      (await c.api.archiveMaterial(l, material.id, revision.row_version))
        .archived_at,
    );
    assert.equal(
      (await c.api.materials(l)).items.some((m) => m.id === material.id),
      false,
    );
    await c.session.logout();
    await c.adminSession.logout();
  },
);
