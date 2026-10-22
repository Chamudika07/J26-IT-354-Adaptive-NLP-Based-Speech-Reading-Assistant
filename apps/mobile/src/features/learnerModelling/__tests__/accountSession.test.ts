import { createAccountSession } from "../data/accountSession";

const id = "00000000-0000-4000-8000-000000000001";
const me = { user_id: id, login_handle: "synthetic-user", status: "active", roles: ["guardian"] };
const credential = (suffix = "first", expires = 600) => ({ access_token: `test-access-${suffix}`, refresh_token: `test-refresh-${suffix}`, token_type: "bearer", expires_in: expires });
function response(value: unknown, status = 200): Response { return { status, ok: status >= 200 && status < 300, headers: { get: () => null }, text: async () => JSON.stringify(value) } as unknown as Response; }
function mockApi() {
  return jest.fn(async (url: string | URL | Request) => {
    if (String(url).endsWith("/auth/login")) return response(credential());
    if (String(url).endsWith("/auth/me")) return response(me);
    if (String(url).includes("/learners?")) return response({ items: [{ id, display_name: "Fictional Learner" }], next_cursor: null });
    if (String(url).endsWith("/auth/refresh")) return response(credential("rotated"));
    return response(null, 204);
  });
}
it("uses documented login, me and authorized learner list without decoding JWT claims", async () => {
  const mock = mockApi();
  const account = createAccountSession("https://readbuddy.example/api/v1", jest.fn(), mock as typeof fetch);
  expect(await account.login("Synthetic-User", "test-only-password")).toEqual(me);
  expect(await account.learners()).toEqual({ items: [{ id, display_name: "Fictional Learner" }], next_cursor: null });
  expect(await account.session.getAccessToken()).toBe("test-access-first");
  expect(mock.mock.calls.map(c => String(c[0]))).toEqual(["https://readbuddy.example/api/v1/auth/login", "https://readbuddy.example/api/v1/auth/me", "https://readbuddy.example/api/v1/learners?limit=25"]);
  expect(account).not.toHaveProperty("password");
  expect(account).not.toHaveProperty("refresh_token");
  expect(account.session.scopeKey).not.toContain("test-access");
});
it("keeps no session after a new instance/restart", async () => {
  const account = createAccountSession("https://readbuddy.example/api/v1", jest.fn(), mockApi() as typeof fetch);
  await account.login("user", "test-only-password");
  const next = createAccountSession("https://readbuddy.example/api/v1", jest.fn(), mockApi() as typeof fetch);
  expect(await next.session.getAccessToken()).toBeNull();
  expect(next.session.scopeKey).not.toBe(account.session.scopeKey);
});
it("single-flights refresh rotation for simultaneous callers", async () => {
  const mock = mockApi();
  const account = createAccountSession("https://readbuddy.example/api/v1", jest.fn(), mock as typeof fetch);
  await account.login("user", "test-only-password");
  expect(await Promise.all([account.session.refreshAccessToken!(), account.session.refreshAccessToken!()])).toEqual(["test-access-rotated", "test-access-rotated"]);
  expect(mock.mock.calls.filter(c => String(c[0]).endsWith("/auth/refresh"))).toHaveLength(1);
});
it("refreshes expired access tokens without exposing them", async () => {
  const mock = mockApi();
  const clock = jest.spyOn(Date, "now").mockReturnValue(100000);
  try {
    const account = createAccountSession("https://readbuddy.example/api/v1", jest.fn(), mock as typeof fetch);
    await account.login("user", "test-only-password");
    clock.mockReturnValue(800000);
    expect(await account.session.getAccessToken()).toBe("test-access-rotated");
  } finally { clock.mockRestore(); }
});
it("invalidates memory after a failed/uncertain refresh and does not replay it", async () => {
  const mock = mockApi(); const expired = jest.fn();
  const account = createAccountSession("https://readbuddy.example/api/v1", expired, mock as typeof fetch);
  await account.login("user", "test-only-password");
  mock.mockRejectedValueOnce(new Error("sensitive transport details"));
  expect(await account.session.refreshAccessToken!()).toBeNull();
  expect(await account.session.getAccessToken()).toBeNull();
  expect(expired).toHaveBeenCalledTimes(1);
});
it("clears local state before logout request finishes and sends only refresh credential", async () => {
  const mock = mockApi();
  const account = createAccountSession("https://readbuddy.example/api/v1", jest.fn(), mock as typeof fetch);
  await account.login("user", "test-only-password");
  const logout = account.logout();
  expect(await account.session.getAccessToken()).toBeNull();
  expect(await logout).toBe(true);
});
it("reports remote logout failure while clearing local credentials", async () => {
  const mock = mockApi();
  const account = createAccountSession("https://readbuddy.example/api/v1", jest.fn(), mock as typeof fetch);
  await account.login("user", "test-only-password");
  mock.mockRejectedValueOnce(new Error("private"));
  expect(await account.logout()).toBe(false);
  expect(await account.session.getAccessToken()).toBeNull();
});
it.each(["http://host/api/v1", "https://user:secret@host/api/v1", "https://host/api/v1?token=bad"])("rejects unsafe address %s before credentials are sent", address => {
  expect(() => createAccountSession(address, jest.fn(), mockApi() as typeof fetch)).toThrow();
});
it.each([401, 429, 503])("sanitizes login HTTP %s and leaves no session", async status => {
  const mock = jest.fn(async () => response({ error: { message: "private-token-material" } }, status));
  const account = createAccountSession("https://host/api/v1", jest.fn(), mock as typeof fetch);
  await expect(account.login("user", "test-only-password")).rejects.toMatchObject({ code: status === 401 ? "sign_in_required" : status === 429 ? "rate_limited" : "unavailable", message: "Account request could not be completed." });
  expect(await account.session.getAccessToken()).toBeNull();
});
it("supports pagination and rejects malformed learner IDs", async () => {
  const mock = mockApi();
  const account = createAccountSession("https://host/api/v1", jest.fn(), mock as typeof fetch);
  await account.login("user", "test-only-password");
  await account.learners(id);
  expect(mock.mock.calls[2]?.[0]).toBe(`https://host/api/v1/learners?limit=25&cursor=${id}`);
  mock.mockResolvedValueOnce(response({ items: [{ id: "fake", display_name: "wrong" }], next_cursor: null }));
  await expect(account.learners()).rejects.toMatchObject({ code: "invalid_response" });
});
it("does not resurrect tokens after disposal during refresh", async () => {
  const mock = mockApi();
  const account = createAccountSession("https://host/api/v1", jest.fn(), mock as typeof fetch);
  await account.login("user", "test-only-password");
  let finish!: (value: Response) => void;
  mock.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
  const refreshing = account.session.refreshAccessToken!();
  account.dispose(); finish(response(credential("late")));
  expect(await refreshing).toBeNull();
  expect(await account.session.getAccessToken()).toBeNull();
});
