import { createRememberStore } from "../data/rememberedAccount";
import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import { Text } from "react-native";
import { Component4AccountBoundary } from "../components/Component4AccountBoundary";
const id = "00000000-0000-4000-8000-000000000001";
function response(value: unknown, status = 200): Response { return { status, ok: status >= 200 && status < 300, headers: { get: () => null }, text: async () => JSON.stringify(value) } as unknown as Response; }
const original = global.fetch;
afterEach(() => { global.fetch = original; });
function setup(items = [{ id, display_name: "Fictional Reader" }], roles = ["guardian"]) {
  const mock = jest.fn(async (url: string | URL | Request) => {
    if (String(url).endsWith("/auth/login")) return response({ access_token: "test-access", refresh_token: "test-refresh", token_type: "bearer", expires_in: 600 });
    if (String(url).endsWith("/auth/me")) return response({ user_id: id, login_handle: "fictional-account", status: "active", roles });
    if (String(url).includes("/learners?")) return response({ items, next_cursor: null });
    if (String(url).endsWith("/auth/logout")) return response(null, 204);
    return response({ error: { code: "consent_required" } }, 403);
  });
  global.fetch = mock as typeof fetch;
  const rememberStore = createRememberStore({ loadSettings: async () => null, saveSettings: async () => {}, readSecret: async () => null, writeSecret: async () => {}, deleteSecret: async () => {} });
  render(<Component4AccountBoundary periodDays={30} rememberStore={rememberStore}><Text>Demo content</Text></Component4AccountBoundary>);
  return mock;
}
async function login() {
  fireEvent.press(screen.getByText("Sign In for Live Mode"));
  fireEvent.changeText(screen.getByLabelText("HTTPS server address"), "https://readbuddy.example/api/v1");
  fireEvent.changeText(screen.getByLabelText("Login handle"), "fictional-account");
  fireEvent.changeText(screen.getByLabelText("Password"), "test-only-password");
  fireEvent.press(screen.getByText("Sign In"));
  await screen.findByText("Choose a learner");
}
it("keeps Demo Mode independent until login and uses only authoritative learner choices", async () => {
  const mock = setup();
  expect(screen.getByText("Demo content")).toBeTruthy(); expect(mock).not.toHaveBeenCalled();
  await login();
  await screen.findByText("Fictional Reader");
  expect(screen.queryByText("Demo content")).toBeNull();
  expect(screen.queryByText("Learner Reports")).toBeNull();
  expect(screen.queryByText("Educator Reports")).toBeNull();
  fireEvent.press(screen.getByText("Fictional Reader"));
  await screen.findByText("Learning-support consent must be confirmed before this report is available.");
  expect(screen.getByText("Live Mode")).toBeTruthy();
  expect(mock.mock.calls.some(c => String(c[0]).includes(`/${id}/guardian-summary?`))).toBe(true);
  expect(mock.mock.calls.some(c => String(c[0]).includes("reading-sessions"))).toBe(false);
});
it("shows a clear unavailable state without fabricated learners", async () => {
  setup([]); await login();
  await screen.findByText("No authorized learners are available to this account.");
  expect(screen.queryByText("Fictional Reader")).toBeNull();
});
it("logout clears selected learner, hides live report and calls backend revocation", async () => {
  const mock = setup(); await login();
  fireEvent.press(await screen.findByText("Fictional Reader"));
  await screen.findByText("Learning-support consent must be confirmed before this report is available.");
  fireEvent.press(screen.getByText("Sign Out"));
  await screen.findByText("Sign in to ReadBuddy");
  expect(screen.queryByText("Fictional Reader")).toBeNull();
  expect(screen.getByLabelText("Password").props.value).toBe("");
  await waitFor(() => expect(mock.mock.calls.some(c => String(c[0]).endsWith("/auth/logout"))).toBe(true));
});
it("switching report roles clears learner selection and does not infer relationships", async () => {
  setup(undefined, ["guardian", "educator"]); await login();
  fireEvent.press(await screen.findByText("Fictional Reader"));
  await screen.findByText("Learning-support consent must be confirmed before this report is available.");
  fireEvent.press(screen.getByText("Educator Reports"));
  expect(screen.queryByText("Live Mode")).toBeNull();
  expect(screen.getByText("Choose a learner")).toBeTruthy();
});
it("opens the learner PP1 journey with the authenticated session without calling production analytics", async () => {
  const mock = setup(undefined, ["learner"]); await login();
  fireEvent.press(screen.getByText("Open PP1 Sample Journey"));
  await screen.findByText("Hi, Reader!");
  fireEvent.press(screen.getByRole("button", { name: "Reading Results" }));
  fireEvent.press(screen.getByRole("radio", { name: "Results source: Connected sample (laptop)" }));
  expect(screen.queryByText("Sign in, then choose Open PP1 Sample Journey to connect.")).toBeNull();
  fireEvent.press(screen.getByRole("button", { name: "Save Sample Progress" }));
  await screen.findByText("Save or refresh not confirmed. Retry the same sample safely, or use offline examples.");
  expect(mock.mock.calls.some(c => String(c[0]).includes("/pp1-demo/saved-progress/"))).toBe(true);
  expect(mock.mock.calls.some(c => String(c[0]).includes("/progress?"))).toBe(false);
  fireEvent.press(screen.getByRole("button", { name: "Back to signed-in reports" }));
  await screen.findByText("Choose a learner");
});
it("does not expose connected PP1 entry to guardian-only accounts", async () => {
  setup(); await login();
  expect(screen.queryByText("Open PP1 Sample Journey")).toBeNull();
});
