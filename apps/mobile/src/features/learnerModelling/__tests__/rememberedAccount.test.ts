import { createAccountSession } from "../data/accountSession";
import { createRememberStore, type LoginSettings, type LoginStorage } from "../data/rememberedAccount";

const settings: LoginSettings = { version: 1, baseUrl: "https://readbuddy.example/api/v1", handle: "fictional", remember: true, autoSignIn: true };
const id = "00000000-0000-4000-8000-000000000001";
function memory() {
  let preferences: LoginSettings | null = null;
  let secret: string | null = null;
  const storage: LoginStorage = { loadSettings: async () => preferences, saveSettings: async v => { preferences = v; }, readSecret: async () => secret, writeSecret: async v => { secret = v; }, deleteSecret: async () => { secret = null; } };
  return { storage, secret: () => secret };
}
function api() {
  let rotation = 0;
  return jest.fn(async (url: string | URL | Request) => {
    const value = String(url).endsWith("/auth/me") ? { user_id: id, login_handle: "fictional", status: "active", roles: ["learner"] } : { access_token: `mock-access-${++rotation}`, refresh_token: `mock-refresh-${rotation}`, token_type: "bearer", expires_in: 300 };
    return { status: 200, ok: true, headers: { get: () => null }, text: async () => JSON.stringify(value) } as unknown as Response;
  });
}
it("restores after restart by consuming and rotating only the securely stored refresh token", async () => {
  const disk = memory(), first = createRememberStore(disk.storage), http = api();
  await first.saveSettings(settings);
  const one = createAccountSession(settings.baseUrl, jest.fn(), http, first.persistence(settings));
  await one.login(settings.handle, "fictional-password-not-persisted");
  expect(disk.secret()).not.toContain("mock-access");
  expect(disk.secret()).not.toContain("fictional-password");
  one.dispose();
  const restarted = createRememberStore(disk.storage);
  const two = createAccountSession(settings.baseUrl, jest.fn(), http, restarted.persistence((await restarted.load())!));
  expect((await two.restore())?.user_id).toBe(id);
  expect(http.mock.calls.filter(([url]) => String(url).endsWith("/auth/login"))).toHaveLength(1);
  expect(http.mock.calls.filter(([url]) => String(url).endsWith("/auth/refresh"))).toHaveLength(1);
  expect(disk.secret()).toContain("mock-refresh-2");
});
it("logout clears secure credentials and persists a no-auto-login marker while keeping form settings", async () => {
  const disk = memory(), store = createRememberStore(disk.storage), http = api();
  await store.saveSettings(settings);
  const client = createAccountSession(settings.baseUrl, jest.fn(), http, store.persistence(settings));
  await client.login(settings.handle, "fictional-password");
  await store.signOut(settings); await client.logout();
  expect(disk.secret()).toBeNull();
  expect(await store.load()).toEqual({ ...settings, autoSignIn: false });
  expect(http.mock.calls.some(([url]) => String(url).endsWith("/auth/logout"))).toBe(true);
});
it("expired credentials fail closed and are never replayed after a failed refresh", async () => {
  const disk = memory(), store = createRememberStore(disk.storage);
  await store.persistence(settings).save("expired-mock-token");
  const http = jest.fn(async () => ({ status: 401, ok: false } as unknown as Response));
  const client = createAccountSession(settings.baseUrl, jest.fn(), http, store.persistence(settings));
  await expect(client.restore()).rejects.toThrow();
  expect(disk.secret()).toBeNull(); expect(http).toHaveBeenCalledTimes(1);
  await expect(client.restore()).resolves.toBeNull();
  expect(http).toHaveBeenCalledTimes(1);
});
it("refuses refresh when deletion-before-use fails and never uses plaintext fallback", async () => {
  const disk = memory(), store = createRememberStore(disk.storage);
  await store.persistence(settings).save("mock-refresh");
  disk.storage.deleteSecret = async () => { throw new Error("unavailable"); };
  const http = api();
  const client = createAccountSession(settings.baseUrl, jest.fn(), http, store.persistence(settings));
  await expect(client.restore()).rejects.toThrow(); expect(http).not.toHaveBeenCalled();
});
it("binds remembered credentials to the HTTPS origin and login handle", async () => {
  const disk = memory(), store = createRememberStore(disk.storage);
  await store.persistence(settings).save("mock-refresh");
  await expect(store.persistence({ ...settings, baseUrl: "https://different.example/api/v1" }).consume()).rejects.toThrow();
  expect(disk.secret()).toBeNull();
});
it("storage write failure does not return an authenticated identity", async () => {
  const disk = memory(); disk.storage.writeSecret = async () => { throw new Error("unavailable"); };
  const store = createRememberStore(disk.storage), http = api();
  const client = createAccountSession(settings.baseUrl, jest.fn(), http, store.persistence(settings));
  await expect(client.login(settings.handle, "fictional-password")).rejects.toMatchObject({ code: "storage_unavailable" });
  expect(await client.session.getAccessToken()).toBeNull();
});
