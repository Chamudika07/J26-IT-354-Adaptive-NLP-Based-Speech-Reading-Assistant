import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import { Text } from "react-native";
import { Component4AccountBoundary } from "../components/Component4AccountBoundary";
import { createRememberStore, type LoginSettings, type LoginStorage } from "../data/rememberedAccount";
const id = "00000000-0000-4000-8000-000000000001";
const settings: LoginSettings = { version: 1, baseUrl: "https://reading.example/api/v1", handle: "fictional", remember: true, autoSignIn: true };
const original = global.fetch;
afterEach(() => { global.fetch = original; });
function disk() {
  let prefs: LoginSettings | null = settings, secret: string | null = null;
  const storage: LoginStorage = { loadSettings: async () => prefs, saveSettings: async v => { prefs = v; }, readSecret: async () => secret, writeSecret: async v => { secret = v; }, deleteSecret: async () => { secret = null; } };
  return { storage, secret: () => secret };
}
function transport(expired = false) {
  let generation = 0;
  const response = (value: unknown, status = 200) => ({ status, ok: status >= 200 && status < 300, headers: { get: () => null }, text: async () => JSON.stringify(value) } as unknown as Response);
  const http = jest.fn(async (url: string | URL | Request) => {
    if (String(url).endsWith("/auth/refresh")) return expired ? response({}, 401) : response({ access_token: `test-access-${++generation}`, refresh_token: `test-refresh-${generation}`, token_type: "bearer", expires_in: 300 });
    if (String(url).endsWith("/auth/me")) return response({ user_id: id, login_handle: "fictional", status: "active", roles: ["learner"] });
    if (String(url).includes("/learners?")) return response({ items: [{ id, display_name: "Fictional Reader" }], next_cursor: null });
    if (String(url).endsWith("/auth/logout")) return response(null, 204);
    throw new Error("Unexpected request");
  });
  global.fetch = http; return http;
}
it("restores the account after remount, rotates refresh credentials and still obtains authorized learners", async () => {
  const data = disk(); const store = createRememberStore(data.storage);
  await store.persistence(settings).save("test-refresh-initial"); const http = transport();
  const first = render(<Component4AccountBoundary periodDays={30} rememberStore={store}><Text>Demo</Text></Component4AccountBoundary>);
  await screen.findByText("Fictional Reader");
  first.unmount();
  render(<Component4AccountBoundary periodDays={30} rememberStore={createRememberStore(data.storage)}><Text>Demo</Text></Component4AccountBoundary>);
  await screen.findByText("Fictional Reader");
  expect(http.mock.calls.filter(([url]) => String(url).endsWith("/auth/refresh"))).toHaveLength(2);
  expect(http.mock.calls.some(([url]) => String(url).endsWith("/auth/login"))).toBe(false);
  fireEvent.press(screen.getByText("Sign Out"));
  await screen.findByText("Sign in to ReadBuddy");
  await waitFor(() => expect(data.secret()).toBeNull());
  expect(screen.getByLabelText("HTTPS server address").props.value).toBe(settings.baseUrl);
  expect(screen.getByLabelText("Login handle").props.value).toBe(settings.handle);
  expect(screen.getByLabelText("Password").props.value).toBe("");
});
it("expired refresh returns to prefilled sign-in without a password or learner cache", async () => {
  const data = disk(), store = createRememberStore(data.storage);
  await store.persistence(settings).save("test-expired-refresh"); transport(true);
  render(<Component4AccountBoundary periodDays={30} rememberStore={store}><Text>Demo</Text></Component4AccountBoundary>);
  await screen.findByText("Sign in to ReadBuddy");
  expect(screen.getByLabelText("Login handle").props.value).toBe(settings.handle);
  expect(screen.getByLabelText("Password").props.value).toBe("");
  expect(screen.queryByText("Fictional Reader")).toBeNull();
  await waitFor(() => expect(data.secret()).toBeNull());
});
it("saved explicit logout never restores automatically on a new mount", async () => {
  const data = disk(), store = createRememberStore(data.storage);
  await store.persistence(settings).save("test-refresh"); await store.signOut(settings);
  const http = transport();
  render(<Component4AccountBoundary periodDays={30} rememberStore={store}><Text>Demo</Text></Component4AccountBoundary>);
  await waitFor(() => expect(screen.getByText("Demo")).toBeTruthy());
  fireEvent.press(screen.getByText("Sign In for Live Mode"));
  expect(screen.getByLabelText("Password").props.value).toBe("");
  expect(http).not.toHaveBeenCalled();
});
