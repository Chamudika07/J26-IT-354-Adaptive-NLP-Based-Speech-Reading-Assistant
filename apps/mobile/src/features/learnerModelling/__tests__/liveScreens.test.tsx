import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import { Text } from "react-native";
import fixtures from "./liveProjectionFixtures.json";
import { DashboardModeBoundary } from "../components/DashboardModeBoundary";
import type { LiveConnection } from "../data/component4Client";
import { GuardianSummaryScreen } from "../screens/GuardianSummaryScreen";
import { EducatorAnalyticsScreen } from "../screens/EducatorAnalyticsScreen";
import { LearnerProgressScreen } from "../screens/LearnerProgressScreen";

function config(role: LiveConnection["role"] = "learner"): LiveConnection {
  return { baseUrl: "https://readbuddy.example/api/v1", learnerId: "00000000-0000-4000-8000-000000000001", role,
    session: { scopeKey: "test-scope", getAccessToken: async () => "test-token" } };
}
function reply(value: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, headers: { get: () => null }, text: async () => JSON.stringify(value) } as unknown as Response;
}
const originalFetch = global.fetch;
afterEach(() => { global.fetch = originalFetch; jest.restoreAllMocks(); });
function mockLive(role: LiveConnection["role"]) {
  const mock = jest.fn(async (url: string | URL | Request) => {
    const query = new URL(String(url)).searchParams;
    return reply({ ...fixtures[role], reporting_period: { start_at_utc: query.get("start_at_utc"), end_at_utc: query.get("end_at_utc") } });
  });
  global.fetch = mock as typeof fetch;
  return mock;
}
it.each(["learner", "guardian", "educator"] as const)("explicitly selects Live Mode on existing %s screen", async role => {
  const mock = mockLive(role);
  const Component = role === "learner" ? LearnerProgressScreen : role === "guardian" ? GuardianSummaryScreen : EducatorAnalyticsScreen;
  render(<Component periodDays={30} liveConnection={config(role)} />);
  expect(mock).not.toHaveBeenCalled();
  fireEvent.press(screen.getByText("Use Live Mode"));
  await screen.findByText("6 recorded sessions");
  expect(screen.queryByText("Sample Data")).toBeNull();
  expect(screen.queryByText("Download AI Report PDF")).toBeNull();
  expect(screen.queryByText("My Students")).toBeNull();
  expect(screen.getByText("Live Mode")).toBeTruthy();
  expect(mock).toHaveBeenCalledTimes(1);
});
it("does not mount demo children or fall back after consent denial; supports retry", async () => {
  const mock = jest.fn().mockResolvedValueOnce(reply({ error: { code: "consent_required" } }, 403));
  global.fetch = mock;
  const connection = config();
  render(<DashboardModeBoundary liveConnection={connection} role="learner" periodDays={30}><Text>DEMO-ONLY-CONTENT</Text></DashboardModeBoundary>);
  fireEvent.press(screen.getByText("Use Live Mode"));
  await screen.findByText("Learning-support consent must be confirmed before this report is available.");
  expect(screen.queryByText("DEMO-ONLY-CONTENT")).toBeNull();
  mock.mockImplementation(async (url: string) => { const p = new URL(url).searchParams; return reply({ ...fixtures.learner, reporting_period: { start_at_utc: p.get("start_at_utc"), end_at_utc: p.get("end_at_utc") } }); });
  fireEvent.press(screen.getByText("Try Again"));
  await screen.findByText("6 recorded sessions");
  fireEvent.press(screen.getByText("Use Demo Mode"));
  expect(screen.getByText("DEMO-ONLY-CONTENT")).toBeTruthy();
});
it("shows empty evidence without sample results", async () => {
  global.fetch = jest.fn(async (url: string | URL | Request) => {
    const p = new URL(String(url)).searchParams;
    return reply({ ...fixtures.learner, included_session_count: 0, contexts: [], support_observations: [], difficulty_observations: [], reporting_period: { start_at_utc: p.get("start_at_utc"), end_at_utc: p.get("end_at_utc") } });
  }) as typeof fetch;
  render(<DashboardModeBoundary liveConnection={config()} role="learner" periodDays={30}><Text>demo</Text></DashboardModeBoundary>);
  fireEvent.press(screen.getByText("Use Live Mode"));
  await screen.findByText("No reading results for this period yet.");
  expect(screen.queryByText("demo")).toBeNull();
});
it("blocks a mismatched role without issuing a request", () => {
  const mock = mockLive("learner");
  render(<DashboardModeBoundary liveConnection={config()} role="guardian" periodDays={30}><Text>demo</Text></DashboardModeBoundary>);
  fireEvent.press(screen.getByText("Use Live Mode"));
  expect(screen.getByText("Sign in with an authorized account to view this report.")).toBeTruthy();
  expect(mock).not.toHaveBeenCalled();
});
it("aborts an in-flight request on leaving Live Mode and ignores late replies", async () => {
  let signal: AbortSignal | undefined;
  global.fetch = jest.fn((_url, options) => { signal = options?.signal as AbortSignal; return new Promise<Response>(() => {}); });
  render(<DashboardModeBoundary liveConnection={config()} role="learner" periodDays={30}><Text>demo</Text></DashboardModeBoundary>);
  fireEvent.press(screen.getByText("Use Live Mode"));
  await waitFor(() => expect(signal).toBeDefined());
  fireEvent.press(screen.getByText("Use Demo Mode"));
  expect(signal?.aborted).toBe(true);
  expect(screen.getByText("demo")).toBeTruthy();
});
it("clears visible results when the account or learner changes", async () => {
  mockLive("learner");
  const first = config();
  const view = render(<DashboardModeBoundary liveConnection={first} role="learner" periodDays={30}><Text>demo</Text></DashboardModeBoundary>);
  fireEvent.press(screen.getByText("Use Live Mode"));
  await screen.findByText("6 recorded sessions");
  global.fetch = jest.fn(async () => reply({ error: { code: "not_found" } }, 404));
  const next = { ...config(), learnerId: "00000000-0000-4000-8000-000000000099", session: { scopeKey: "next-account", getAccessToken: async () => "next-token" } };
  view.rerender(<DashboardModeBoundary liveConnection={next} role="learner" periodDays={30}><Text>demo</Text></DashboardModeBoundary>);
  expect(screen.queryByText("6 recorded sessions")).toBeNull();
  await screen.findByText("This learner is not available to this account.");
  expect(screen.queryByText("demo")).toBeNull();
});

it("supports explicit cancellation and retry without mounting demo content", async () => {
  global.fetch = jest.fn(() => new Promise<Response>(() => {}));
  render(<DashboardModeBoundary liveConnection={config()} role="learner" periodDays={30}><Text>demo</Text></DashboardModeBoundary>);
  fireEvent.press(screen.getByText("Use Live Mode"));
  fireEvent.press(screen.getByText("Cancel Loading"));
  expect(screen.getByText("The request was cancelled.")).toBeTruthy();
  expect(screen.queryByText("demo")).toBeNull();
  mockLive("learner");
  fireEvent.press(screen.getByText("Try Again"));
  await screen.findByText("6 recorded sessions");
});

it("submits supplied upstream telemetry only on action and reloads after acknowledgment", async () => {
  const connection = config();
  const pendingSession = {
    learner_id: connection.learnerId, client_session_id: "00000000-0000-4000-8000-000000000002",
    session_start_time: "2026-01-05T00:00:00Z", session_end_time: "2026-01-05T00:02:00Z",
    task_type: "independent_reading" as const, difficulty_tier: "intermediate" as const,
    support_mode: "adaptive" as const, completion_status: "completed" as const,
    words_attempted: 100, words_correct: 90, target_word_count: 100, active_duration_ms: 60000, total_duration_ms: 70000,
  };
  const mock = jest.fn(async (url: string | URL | Request, options?: RequestInit) => {
    if (options?.method === "POST") return reply({ id: "00000000-0000-4000-8000-000000000003", client_session_id: pendingSession.client_session_id, created: true }, 201);
    const p = new URL(String(url)).searchParams;
    return reply({ ...fixtures.learner, reporting_period: { start_at_utc: p.get("start_at_utc"), end_at_utc: p.get("end_at_utc") } });
  });
  global.fetch = mock as typeof fetch;
  render(<DashboardModeBoundary liveConnection={connection} pendingSession={pendingSession} role="learner" periodDays={30}><Text>demo</Text></DashboardModeBoundary>);
  expect(mock).not.toHaveBeenCalled();
  fireEvent.press(screen.getByText("Use Live Mode"));
  await screen.findByText("6 recorded sessions");
  expect(mock).toHaveBeenCalledTimes(1);
  fireEvent.press(screen.getByText("Submit Reading Session"));
  await screen.findByText("Reading session received.");
  await waitFor(() => expect(mock).toHaveBeenCalledTimes(3));
  expect(mock.mock.calls[1]?.[1]?.body).toBe(JSON.stringify(pendingSession));
  expect(screen.queryByText("Download AI Report PDF")).toBeNull();
});

it("does not fall back on logout but permits explicitly returning to Demo Mode", async () => {
  mockLive("learner");
  const view = render(<DashboardModeBoundary liveConnection={config()} role="learner" periodDays={30}><Text>demo</Text></DashboardModeBoundary>);
  fireEvent.press(screen.getByText("Use Live Mode"));
  await screen.findByText("6 recorded sessions");
  view.rerender(<DashboardModeBoundary role="learner" periodDays={30}><Text>demo</Text></DashboardModeBoundary>);
  expect(screen.queryByText("6 recorded sessions")).toBeNull();
  expect(screen.queryByText("demo")).toBeNull();
  expect(screen.getByText("Sign in with an authorized account to view this report.")).toBeTruthy();
  fireEvent.press(screen.getByText("Use Demo Mode"));
  expect(screen.getByText("demo")).toBeTruthy();
});
