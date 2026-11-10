import assert from "node:assert/strict";
import test from "node:test";
import { randomUUID } from "node:crypto";
import { ApiError, createApi, unwrap } from "@j26/api-client";
import { Session } from "../../src/api/session";
import { workflows } from "../../src/api/workflows";

test(
  "real HTTP: managed synthetic access → login → me → learners → create/process → results → refresh/logout",
  { skip: process.env.MOBILE_HTTP_TEST !== "1" },
  async () => {
    // Fixed fixture address prevents accidentally targeting the persistent backend.
    const base = "http://127.0.0.1:18000/api/v1";
    const publicApi = createApi(base);
    const password = "Synthetic mobile fixture passphrase 42";
    const adminToken = unwrap(
      await publicApi.POST("/api/v1/auth/login", {
        body: { login_handle: "synthetic.mobile.admin", password },
      }),
    );
    const admin = createApi(base, (input, init) => {
      const req = new Request(input, init);
      req.headers.set("Authorization", `Bearer ${adminToken.access_token}`);
      return fetch(req);
    });
    const handle = `synthetic.${randomUUID().slice(0, 8)}`;
    const account = unwrap(
      await admin.POST("/api/v1/auth/users", {
        body: { login_handle: handle, password },
      }),
    );
    const learner = unwrap(
      await admin.POST("/api/v1/learners", {
        body: { display_name: "Synthetic mobile reader" },
      }),
    );
    const grant = unwrap(
      await admin.POST("/api/v1/learners/{learner_id}/educator-grants", {
        params: { path: { learner_id: learner.id } },
        body: {
          educator_user_id: account.user_id,
          access_level: "instructor",
          expires_at: new Date(Date.now() + 3600_000).toISOString(),
        },
      }),
    );
    let stored: string | null = null;
    let expireNext = false;
    let observed401 = false;
    const transport: typeof fetch = async (input, init) => {
      const request = new Request(input, init);
      if (expireNext && request.url.endsWith("/auth/me")) {
        expireNext = false;
        request.headers.set("Authorization", "Bearer synthetic-invalid-access");
      }
      const response = await fetch(request);
      if (response.status === 401) observed401 = true;
      return response;
    };
    const session = new Session(
      base,
      {
        read: async () => stored,
        write: async (value) => {
          stored = value;
        },
        clear: async () => {
          stored = null;
        },
      },
      () => undefined,
      transport,
    );
    const api = workflows(session);
    await assert.rejects(
      session.login({ login_handle: handle, password: "incorrect" }),
      (e) => e instanceof ApiError && e.status === 401,
    );
    await session.login({ login_handle: handle, password });
    assert.deepEqual((await api.me()).roles, ["educator"]);
    assert.equal(
      (await api.learners()).items.some((item) => item.id === learner.id),
      true,
    );
    await assert.rejects(
      api.create(learner.id, { title: " ", text: " ", language_tag: "en" }),
      (e) => e instanceof ApiError && e.status === 422,
    );
    const material = await api.create(learner.id, {
      title: "Synthetic mobile passage",
      text: "A cat rests. A dog runs!",
      language_tag: "en",
    });
    const params = {
      learner_id: learner.id,
      material_id: material.id,
      revision_id: material.latest_revision.id,
    };
    const run = await api.process(params);
    assert.equal(run.status, "succeeded");
    const result = await api.result(params, run.id);
    assert.deepEqual(result.profile?.length_load, {
      character_count: 24,
      word_count: 6,
      sentence_count: 2,
    });
    assert.equal(result.sentences?.length, 2);
    assert.equal((await api.process(params)).id, run.id);
    assert.ok(
      (await api.materials(learner.id)).items.some(
        (item) => item.id === material.id,
      ),
    );
    assert.ok(
      (await api.runs(params)).items.some((item) => item.id === run.id),
    );
    const unrelated = unwrap(
      await admin.POST("/api/v1/learners", {
        body: { display_name: "Synthetic unrelated reader" },
      }),
    );
    await assert.rejects(
      api.materials(unrelated.id),
      (e) => e instanceof ApiError && e.status === 404,
    );
    const before = stored;
    observed401 = false;
    expireNext = true;
    assert.equal((await api.me()).user_id, account.user_id);
    assert.equal(observed401, true);
    assert.notEqual(stored, before);
    const revoked = await admin.POST(
      "/api/v1/learners/{learner_id}/educator-grants/{grant_id}/revoke",
      { params: { path: { learner_id: learner.id, grant_id: grant.id } } },
    );
    assert.equal(revoked.response.status, 200);
    await assert.rejects(
      api.result(params, run.id),
      (e) => e instanceof ApiError && e.status === 404,
    );
    assert.equal(
      (await api.learners()).items.some((item) => item.id === learner.id),
      false,
    );
    const refresh = stored;
    await session.logout();
    assert.equal(stored, null);
    assert.equal(
      (
        await publicApi.POST("/api/v1/auth/refresh", {
          body: { refresh_token: refresh! },
        })
      ).response.status,
      401,
    );
    assert.equal(
      (
        await publicApi.POST("/api/v1/auth/logout", {
          body: { refresh_token: adminToken.refresh_token },
        })
      ).response.status,
      204,
    );
    console.log(
      "HTTP PASS: login/me/list 200; provision/create/process 201; cached process 200; refresh 200; logout 204; invalid login/refresh 401; unrelated/revoked 404; invalid text 422.",
    );
  },
);
