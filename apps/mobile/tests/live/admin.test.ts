import assert from "node:assert/strict";
import test from "node:test";
import { randomUUID } from "node:crypto";
import { ApiError } from "@j26/api-client";
import { Session } from "../../src/api/session";
import { adminApi } from "../../src/api/admin";
import { workflows } from "../../src/api/workflows";

export const password = "Synthetic mobile fixture passphrase 42";
export function testSession() {
  let saved: string | null = null;
  return new Session(
    "http://127.0.0.1:18000/api/v1",
    {
      read: async () => saved,
      write: async (v) => {
        saved = v;
      },
      clear: async () => {
        saved = null;
      },
    },
    () => {},
  );
}
test(
  "admin mobile API: create account, learner, instructor assignment; educator login; revoke",
  { skip: process.env.MOBILE_HTTP_TEST !== "1" },
  async () => {
    const adminSession = testSession();
    await adminSession.login({
      login_handle: "synthetic.mobile.admin",
      password,
    });
    const admin = adminApi(adminSession);
    const handle = `synthetic.${randomUUID().slice(0, 8)}`;
    const educator = await admin.createEducator({
      login_handle: handle,
      password,
    });
    const learner = await admin.createLearner({
      display_name: "Synthetic admin workflow reader",
    });
    const grant = await admin.assign(learner.id, {
      educator_user_id: educator.user_id,
      access_level: "instructor",
      expires_at: new Date(Date.now() + 3600000).toISOString(),
    });
    await assert.rejects(
      workflows(adminSession).profile(learner.id),
      (e) => e instanceof ApiError && e.status === 404,
    );
    const session = testSession();
    await session.login({ login_handle: handle, password });
    const api = workflows(session);
    assert.ok((await api.learners()).items.some((l) => l.id === learner.id));
    assert.equal((await api.profile(learner.id)).id, learner.id);
    await assert.rejects(
      adminApi(session).createLearner({ display_name: "Synthetic denied" }),
      (e) => e instanceof ApiError && e.status === 403,
    );
    assert.ok((await admin.revoke(learner.id, grant.id)).revoked_at);
    await assert.rejects(
      api.profile(learner.id),
      (e) => e instanceof ApiError && e.status === 404,
    );
    await session.logout();
    await adminSession.logout();
  },
);
