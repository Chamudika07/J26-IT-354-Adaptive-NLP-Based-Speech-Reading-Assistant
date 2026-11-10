import { randomUUID } from "node:crypto";
import { Session } from "../../src/api/session";
import { adminApi } from "../../src/api/admin";
import { workflows } from "../../src/api/workflows";
export const password = "Synthetic mobile fixture passphrase 42";
export function testSession(transport: typeof fetch = fetch) {
  let saved: string | null = null;
  const store = {
    read: async () => saved,
    write: async (v: string) => {
      saved = v;
    },
    clear: async () => {
      saved = null;
    },
  };
  return {
    session: new Session(
      "http://127.0.0.1:18000/api/v1",
      store,
      () => {},
      transport,
    ),
    store,
  };
}
export async function onboard() {
  const { session: adminSession } = testSession();
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
    display_name: "Synthetic complete workflow reader",
  });
  const grant = await admin.assign(learner.id, {
    educator_user_id: educator.user_id,
    access_level: "instructor",
    expires_at: new Date(Date.now() + 3600000).toISOString(),
  });
  const { session } = testSession();
  await session.login({ login_handle: handle, password });
  return {
    adminSession,
    admin,
    session,
    api: workflows(session),
    learner,
    educator,
    grant,
    handle,
  };
}
