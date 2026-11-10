import assert from "node:assert/strict";
import test from "node:test";
import { ApiError } from "@j26/api-client";
import { apiUrl, Session, type CredentialStore } from "../src/api/session";
import { loginForm, textForm } from "../src/forms";

const base = "http://127.0.0.1:18000/api/v1";
const tokens = (n: number) => ({
  access_token: `access-${n}`,
  refresh_token: `refresh-${n}`,
  expires_in: 300,
  token_type: "bearer",
});
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
function storage() {
  let value: string | null = null;
  const store: CredentialStore = {
    read: async () => value,
    write: async (v) => {
      value = v;
    },
    clear: async () => {
      value = null;
    },
  };
  return store;
}

test("API URL requires explicit host, v1 path and HTTPS outside development", () => {
  assert.equal(apiUrl(`${base}/`, true), base);
  for (const value of [
    undefined,
    "http://user:password@example.com/api/v1",
    "http://example.com",
    `${base}?token=private`,
  ])
    assert.throws(() => apiUrl(value, true));
  assert.throws(() => apiUrl(base, false));
  assert.equal(
    apiUrl("https://example.com/api/v1", false),
    "https://example.com/api/v1",
  );
});

test("validation rejects empty credentials and whitespace or oversized passages", () => {
  assert.equal(
    loginForm.safeParse({ login_handle: " ", password: "" }).success,
    false,
  );
  assert.equal(
    textForm.safeParse({ title: "Title", text: "   " }).success,
    false,
  );
  assert.equal(
    textForm.safeParse({ title: "Title", text: "a".repeat(50001) }).success,
    false,
  );
  assert.equal(
    textForm.parse({ title: " Story ", text: "A cat rests." }).title,
    "Story",
  );
});

test("simultaneous 401s rotate once, persist only refresh credential and replay with fresh bearer", async () => {
  let refreshes = 0;
  const store = storage();
  const transport: typeof fetch = async (input) => {
    const req = new Request(input);
    assert.equal(new URL(req.url).pathname.startsWith("/api/v1/api/v1"), false);
    if (req.url.endsWith("/auth/login")) return json(tokens(1));
    if (req.url.endsWith("/auth/refresh")) {
      refreshes++;
      await new Promise((resolve) => setTimeout(resolve, 10));
      return json(tokens(2));
    }
    if (req.headers.get("Authorization") === "Bearer access-1")
      return json({ error: { code: "authentication_required" } }, 401);
    assert.equal(req.headers.get("Authorization"), "Bearer access-2");
    return json({
      user_id: "synthetic",
      login_handle: "synthetic",
      roles: ["educator"],
      status: "active",
    });
  };
  const session = new Session(base, store, () => undefined, transport);
  await session.login({ login_handle: "synthetic", password: "synthetic" });
  const result = await Promise.all([
    session.api.GET("/api/v1/auth/me"),
    session.api.GET("/api/v1/auth/me"),
  ]);
  assert.equal(refreshes, 1);
  assert.ok(result.every((r) => r.response.status === 200));
  assert.equal(await store.read(), "refresh-2");
});

test("invalid refresh clears credentials and invalidates protected UI", async () => {
  const store = storage();
  await store.write("expired");
  const changes: boolean[] = [];
  const session = new Session(
    base,
    store,
    (value) => changes.push(value),
    async () => json({ error: { code: "invalid_session" } }, 401),
  );
  await assert.rejects(
    session.restore(),
    (error) => error instanceof ApiError && error.status === 401,
  );
  assert.equal(await store.read(), null);
  assert.deepEqual(changes, [false]);
});

test("temporary restore failure keeps saved credential for explicit retry", async () => {
  const store = storage();
  await store.write("saved");
  const session = new Session(
    base,
    store,
    () => undefined,
    async () => {
      throw new TypeError("offline");
    },
  );
  await assert.rejects(session.restore());
  assert.equal(await store.read(), "saved");
});

test("permissions and validation failures do not rotate or automatically repeat writes", async () => {
  let calls = 0;
  const session = new Session(
    base,
    storage(),
    () => undefined,
    async (input) => {
      if (new Request(input).url.endsWith("/login")) return json(tokens(1));
      calls++;
      return json({ error: { code: "not_found" } }, 404);
    },
  );
  await session.login({ login_handle: "synthetic", password: "synthetic" });
  const response = await session.api.POST(
    "/api/v1/learners/{learner_id}/reading-materials",
    {
      params: { path: { learner_id: "synthetic" } },
      body: { title: "Synthetic", text: "A cat rests.", language_tag: "en" },
    },
  );
  assert.equal(response.response.status, 404);
  assert.equal(calls, 1);
});

test("logout clears local credentials even if server revocation is unavailable", async () => {
  const store = storage();
  const changes: boolean[] = [];
  const session = new Session(
    base,
    store,
    (value) => changes.push(value),
    async (input) =>
      new Request(input).url.endsWith("/login")
        ? json(tokens(1))
        : json({}, 503),
  );
  await session.login({ login_handle: "synthetic", password: "synthetic" });
  await assert.rejects(session.logout());
  assert.equal(await store.read(), null);
  assert.deepEqual(changes, [true, false]);
});

test("late refresh cannot restore a signed-out session", async () => {
  const store = storage();
  await store.write("saved");
  let release!: () => void;
  const waiting = new Promise<void>((resolve) => {
    release = resolve;
  });
  let entered!: () => void;
  const started = new Promise<void>((resolve) => {
    entered = resolve;
  });
  const changes: boolean[] = [];
  const session = new Session(
    base,
    store,
    (value) => changes.push(value),
    async (input) => {
      if (new Request(input).url.endsWith("/refresh")) {
        entered();
        await waiting;
        return json(tokens(2));
      }
      return new Response(null, { status: 204 });
    },
  );
  const restoring = session.restore();
  const rejected = assert.rejects(restoring);
  await started;
  await session.logout();
  release();
  await rejected;
  assert.equal(await store.read(), null);
  assert.deepEqual(changes, [false]);
});

test("ambiguous network failure never repeats a write or rotates", async () => {
  let writes = 0;
  const session = new Session(
    base,
    storage(),
    () => {},
    async (input) => {
      if (new Request(input).url.endsWith("/login")) return json(tokens(1));
      writes++;
      throw new TypeError("connection lost after sending");
    },
  );
  await session.login({ login_handle: "synthetic", password: "synthetic" });
  await assert.rejects(
    session.api.POST("/api/v1/learners", {
      body: { display_name: "Synthetic" },
    }),
  );
  assert.equal(writes, 1);
});

test("failed secure storage revokes the new session without exposing credentials", async () => {
  let revocations = 0;
  let cleared = false;
  const session = new Session(
    base,
    {
      read: async () => null,
      write: async () => {
        throw new Error("storage unavailable");
      },
      clear: async () => {
        cleared = true;
      },
    },
    () => {},
    async (input) => {
      if (new Request(input).url.endsWith("/login")) return json(tokens(1));
      revocations++;
      return new Response(null, { status: 204 });
    },
  );
  await assert.rejects(
    session.login({ login_handle: "synthetic", password: "synthetic" }),
    /Secure session storage failed/,
  );
  assert.equal(cleared, true);
  assert.equal(revocations, 1);
});
