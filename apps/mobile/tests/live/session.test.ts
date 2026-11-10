import assert from "node:assert/strict";
import test from "node:test";
import { ApiError } from "@j26/api-client";
import { Session } from "../../src/api/session";
import { workflows } from "../../src/api/workflows";
import { onboard, password, testSession } from "./fixtures";

test(
  "real HTTP: restore rotates, concurrent 401s share refresh, write replays once, revoked session signs out",
  {
    skip: process.env.MOBILE_HTTP_TEST !== "1",
  },
  async () => {
    const c = await onboard();
    const { session, store } = testSession();
    await session.login({ login_handle: c.handle, password });
    const before = await store.read();
    let refreshes = 0;
    let rejectedReads = 0;
    let rejectedWrites = 0;
    let successfulWrites = 0;
    let invalidateReads = false;
    let invalidateWrite = false;
    const active: boolean[] = [];
    const transport: typeof fetch = async (input, init) => {
      const request = new Request(input, init);
      if (request.url.endsWith("/auth/refresh")) refreshes++;
      if (
        invalidateReads &&
        request.url.endsWith("/auth/me") &&
        rejectedReads < 2
      ) {
        rejectedReads++;
        request.headers.set("Authorization", "Bearer synthetic-invalid-access");
      }
      const writing =
        request.method === "POST" && request.url.endsWith("/reading-materials");
      if (writing && invalidateWrite) {
        invalidateWrite = false;
        rejectedWrites++;
        request.headers.set("Authorization", "Bearer synthetic-invalid-access");
      }
      const response = await fetch(request);
      if (writing && response.ok) successfulWrites++;
      return response;
    };
    const restored = new Session(
      "http://127.0.0.1:18000/api/v1",
      store,
      (v) => active.push(v),
      transport,
    );
    await restored.restore();
    assert.notEqual(await store.read(), before);
    assert.equal(refreshes, 1);
    const api = workflows(restored);
    invalidateReads = true;
    const users = await Promise.all([api.me(), api.me()]);
    assert.ok(users.every((u) => u.user_id === c.educator.user_id));
    assert.equal(refreshes, 2);
    invalidateWrite = true;
    const material = await api.create(c.learner.id, {
      title: "Synthetic safe retry",
      text: "A bird sings.",
      language_tag: "en",
    });
    assert.equal(rejectedWrites, 1);
    assert.equal(successfulWrites, 1);
    assert.equal(refreshes, 3);
    assert.deepEqual(
      (await api.materials(c.learner.id)).items.map((m) => m.id),
      [material.id],
    );
    const revoked = await store.read();
    await restored.logout();
    assert.equal(await store.read(), null);
    // Simulate an app restart with a server-revoked refresh credential.
    await store.write(revoked!);
    const invalid = new Session("http://127.0.0.1:18000/api/v1", store, (v) =>
      active.push(v),
    );
    await assert.rejects(
      invalid.restore(),
      (e) => e instanceof ApiError && e.status === 401,
    );
    assert.equal(await store.read(), null);
    assert.equal(active.at(-1), false);
    await c.session.logout();
    await c.adminSession.logout();
  },
);
