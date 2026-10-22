import { act, fireEvent, render, screen } from "@testing-library/react-native";
import { Platform } from "react-native";
import * as fs from "expo-file-system/legacy";
import App from "../../../../App";
import { developerTestStorage, nativeTestStorage } from "../preview/developerSessionStorage";
import { eligibleTestSessions, experimentalTestEngagement, testFile, testMetrics, validateTestFile, validateTestSession, type TestSession } from "../preview/developerSessions";
import { LearnerProgressScreen } from "../screens/LearnerProgressScreen";
import { unavailableLiveDashboardProvider } from "../data/dashboardProvider";
import { publishScenario } from "../preview/selectedScenario";

jest.mock("../preview/demoPersistence", () => ({ demoStorage: () => ({ load: async () => null, save: async () => {} }) }));

let mockDisk: string | null = null;
jest.mock("expo-file-system/legacy", () => ({
  documentDirectory: "file://test-documents/",
  getInfoAsync: jest.fn(async () => mockDisk === null ? { exists: false } : { exists: true, isDirectory: false, size: mockDisk.length }),
  readAsStringAsync: jest.fn(async () => mockDisk),
  writeAsStringAsync: jest.fn(async (_uri: string, text: string) => { mockDisk = text; }),
  deleteAsync: jest.fn(async () => { mockDisk = null; }),
}));
beforeEach(() => { publishScenario(null); process.env.EXPO_PUBLIC_COMPONENT4_DEVELOPER_TOOLS = "1"; mockDisk = null; jest.clearAllMocks(); });
afterEach(() => jest.restoreAllMocks());
const record: TestSession = { id: "00000000-0000-4000-8000-000000000001", start: "2026-10-19T10:00:00.000Z", end: "2026-10-19T10:01:00.000Z", task: "independent_reading", tier: "intermediate", mode: "adaptive", attempted: 100, correct: 90, target: 100, activeMs: 60000, totalMs: 60000, hesitations: 3, pauseCount: null, pauseMs: null, replayCount: null, completion: "completed" };

it("uses existing raw-count formulas and preserves missing measurements", () => {
  // Exact binary midpoint: backend Python round(1/32, 4) is .0312, not .0313.
  expect(testMetrics({ ...record, attempted: 32, correct: 1 }).accuracy).toBe(0.0312);
  expect(testMetrics({ ...record, attempted: 32, correct: 3 }).accuracy).toBe(0.0938);
  expect(testMetrics(record)).toEqual({ accuracy: 0.9, wpm: 100, hesitation: 0.03 });
  expect(testMetrics({ ...record, hesitations: null })).toEqual({ accuracy: 0.9, wpm: 100, hesitation: null });
  expect(testMetrics({ ...record, attempted: 0, correct: 0, activeMs: 999 })).toEqual({ accuracy: null, wpm: null, hesitation: null });
  expect(testMetrics({ ...record, attempted: 0, correct: 0 })).toEqual({ accuracy: null, wpm: 0, hesitation: null });
});
it.each([{ correct: 101 }, { activeMs: 60001 }, { attempted: -1 }, { correct: 1.1 }, { hesitations: -1 }, { task: "unknown" }, { tier: "beginner" }, { mode: "unknown" }, { id: "private name" }, { start: "2026-10-19" }, { end: "2026-10-18T00:00:00.000Z" }, { learner_id: "private" }])("rejects invalid raw simulator input %#", (change) => {
  expect(() => validateTestSession({ ...record, ...change })).toThrow();
});
it("rejects duplicate identities, unknown versions and private storage fields", () => {
  expect(() => testFile([record, { ...record }])).toThrow(/Duplicate/);
  expect(() => validateTestFile({ ...testFile([record]), version: 3 })).toThrow();
  expect(() => validateTestFile({ ...testFile([record]), learner_id: "private" })).toThrow();
});
it("preserves interval boundaries and deterministic equal-time ordering", () => {
  const end = Date.parse("2026-10-20T10:00:00.000Z");
  const atEnd = { ...record, id: "00000000-0000-4000-8000-000000000002", start: new Date(end).toISOString() };
  const atStart = { ...record, id: "00000000-0000-4000-8000-000000000003", start: new Date(end-7*86400000).toISOString() };
  const before = { ...record, id: "00000000-0000-4000-8000-000000000004", start: new Date(end-7*86400000-1).toISOString() };
  expect(eligibleTestSessions([atEnd, record, atStart, before], 7, end)).toEqual([atStart, record]);
  const sameTime = { ...record, id: "00000000-0000-4000-8000-000000000005" };
  expect(eligibleTestSessions([sameTime, record], 7, end)).toEqual(eligibleTestSessions([record, sameTime], 7, end));
});
it("saves, reloads in a new store instance and rejects duplicate UUIDs without overwriting", async () => {
  const io = { read: async () => mockDisk, write: async (text: string) => { mockDisk = text; }, clear: async () => { mockDisk = null; } };
  await developerTestStorage(io, () => true).save(record);
  const restarted = developerTestStorage(io, () => true);
  expect((await restarted.load()).records).toEqual([record]);
  expect((await restarted.save(record)).records).toEqual([record]);
  await expect(restarted.save({ ...record, correct: 91 })).rejects.toThrow(/Duplicate/);
  expect((await restarted.load()).records).toHaveLength(1);
  await restarted.clear(); expect(mockDisk).toBeNull();
});
it("fails closed for malformed or unavailable storage and denied contexts", async () => {
  mockDisk = "bad JSON";
  const store = nativeTestStorage(() => true);
  await expect(store.load()).rejects.toThrow(/unavailable or invalid/);
  await store.clear(); expect(mockDisk).toBeNull();
  jest.mocked(fs.writeAsStringAsync).mockRejectedValueOnce(Error("private native details"));
  await expect(store.save(record)).rejects.toThrow("Save could not be confirmed");
  const read = jest.fn(async () => null);
  await expect(developerTestStorage({ read, write: jest.fn(), clear: jest.fn() }, () => false).load()).rejects.toThrow(/Developer/);
  expect(read).not.toHaveBeenCalled();
});
async function openTest() {
  await screen.findByText("Hi, Reader!");
  fireEvent.press(screen.getByRole("button", { name: "Open Reading Session Test" }));
}
it("supports Save/Load/Clear, simulated restart and Home/Progress selection without demo mixing", async () => {
  const fetchSpy = jest.spyOn(globalThis, "fetch");
  const view = render(<LearnerProgressScreen periodDays={30} />);
  await openTest();
  expect(screen.getByText("Developer synthetic test data — not a real learner record.")).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "Save" }));
  await screen.findByText("Synthetic record saved and read back from device storage.");
  expect(mockDisk).toContain('"verifiedTelemetry":false');
  fireEvent.press(screen.getByRole("tab", { name: "Home learner view" }));
  expect(screen.getByText("Developer Home Dashboard")).toBeTruthy();
  expect(screen.getByText("Words attempted: 100. Words correct: 90. Active reading: 60000 ms.")).toBeTruthy();
  expect(screen.getByText(/Analytics pending offline backend calculation/)).toBeTruthy();
  expect(screen.queryByText("Accuracy: 90 %")).toBeNull();
  expect(screen.queryByText("Hi, reader!")).toBeNull();
  fireEvent.press(screen.getByRole("tab", { name: "Analytics learner view" }));
  expect(screen.getByText("Developer Progress Analytics")).toBeTruthy();
  expect(screen.queryByText("Reading pace: 100 words/minute")).toBeNull();
  expect(screen.getByText(/Hesitations are|Completion:/)).toBeTruthy();
  fireEvent.press(screen.getByRole("tab", { name: "Suggestions learner view" }));
  expect(screen.getByText("Developer recommendations unavailable")).toBeTruthy();
  expect(screen.queryByText("Adaptive recommendation")).toBeNull();
  view.unmount();
  render(<LearnerProgressScreen periodDays={30} />); await openTest();
  expect(screen.getByText(/Nothing loaded/)).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "Load" }));
  await screen.findByText("Loaded 1 synthetic records from device storage.");
  fireEvent.press(screen.getByRole("button", { name: "Reset input" }));
  expect(screen.getByRole("alert")).toHaveTextContent("Input reset only. Stored records are unchanged. Use a new UUID for each session.");
  expect(JSON.parse(mockDisk!).records).toHaveLength(1);
  fireEvent.press(screen.getByRole("button", { name: "Clear" }));
  await screen.findByText("Synthetic records cleared from device storage.");
  expect(mockDisk).toBeNull();
  expect(fetchSpy).not.toHaveBeenCalled();
});
it.each(["Guardian", "Educator"])("isolates live mode and %s role switches and requires explicit load on re-entry", async (role) => {
  const view = render(<App />); await openTest();
  fireEvent.press(screen.getByRole("button", { name: "Save" }));
  await screen.findByText("Synthetic record saved and read back from device storage.");
  const reads = jest.mocked(fs.readAsStringAsync).mock.calls.length;
  fireEvent.press(screen.getByRole("tab", { name: `${role} sample preview` }));
  if (role === "Educator") fireEvent.press(await screen.findByRole("button", { name: "View separate example" }));
  await screen.findByText(role === "Guardian" ? "Guardian progress summary" : "Educator reading analytics");
  expect(screen.queryByRole("button", { name: "Open Reading Session Test" })).toBeNull();
  expect(jest.mocked(fs.readAsStringAsync).mock.calls.length).toBe(reads);
  fireEvent.press(screen.getByRole("tab", { name: "Learner sample preview" })); await openTest();
  expect(screen.getByText(/Nothing loaded/)).toBeTruthy();
  view.unmount();
  render(<LearnerProgressScreen periodDays={30} provider={unavailableLiveDashboardProvider} />);
  expect(screen.queryByRole("button", { name: "Open Reading Session Test" })).toBeNull();
  await act(async () => {});
  expect(jest.mocked(fs.readAsStringAsync).mock.calls.length).toBe(reads);
});
it("hides the workflow and forbids storage access in production builds", async () => {
  jest.replaceProperty(globalThis as typeof globalThis & { __DEV__: boolean }, "__DEV__", false);
  render(<LearnerProgressScreen periodDays={30} />);
  await screen.findByText("Hi, Reader!");
  expect(screen.queryByRole("button", { name: "Open Reading Session Test" })).toBeNull();
  await expect(nativeTestStorage(() => true).load()).rejects.toThrow();
  expect(fs.getInfoAsync).not.toHaveBeenCalled();
});


it.each(["ios", "android"] as const)("uses only the namespaced native file on %s", async (platform) => {
  jest.replaceProperty(Platform, "OS", platform);
  await nativeTestStorage(() => true).save(record);
  expect(fs.writeAsStringAsync).toHaveBeenCalledWith("file://test-documents/readbuddy-component4-developer-synthetic-v1.json", expect.any(String));
});
it("shows invalid input and malformed storage errors without substituting dashboard demo evidence", async () => {
  render(<LearnerProgressScreen periodDays={30} />); await openTest();
  fireEvent.changeText(screen.getByLabelText("Words correct"), "101");
  fireEvent.press(screen.getByRole("button", { name: "Save" }));
  expect(screen.getByRole("alert")).toHaveTextContent("Invalid input. Use a UUID, valid UTC dates and non-negative whole counts/durations. Correct words cannot exceed attempted words; active time cannot exceed total time.");
  expect(fs.writeAsStringAsync).not.toHaveBeenCalled();
  mockDisk = "malformed";
  fireEvent.press(screen.getByRole("button", { name: "Load" }));
  await screen.findByText("Cannot load synthetic records: storage unavailable or invalid. Clear to recover.");
  fireEvent.press(screen.getByRole("tab", { name: "Home learner view" }));
  expect(screen.getByText("Developer Home Dashboard")).toBeTruthy();
  expect(screen.getByText("Cannot load synthetic records: storage unavailable or invalid. Clear to recover.")).toBeTruthy();
  expect(screen.queryByText("Hi, reader!")).toBeNull();
});
it("rejects oversized files and unavailable storage without leaking native details", async () => {
  const io = { read: jest.fn(async () => "x".repeat(100001)), write: jest.fn(), clear: jest.fn(async () => { throw Error("private native path"); }) };
  const store = developerTestStorage(io, () => true);
  await expect(store.load()).rejects.toThrow(/unavailable or invalid/);
  await expect(store.clear()).rejects.toThrow("Clear could not be confirmed. Device storage may be unavailable.");
  expect(io.write).not.toHaveBeenCalled();
});


it.each(["completed", "abandoned", "interrupted"] as const)("preserves %s completion and pause/replay units in storage", (completion) => {
  const input = { ...record, completion, pauseCount: 0, pauseMs: 12000, replayCount: 2 };
  const result = validateTestFile(JSON.parse(JSON.stringify(testFile([input]))));
  expect(result.records).toEqual([input]);
});
it.each([{ pauseCount: -1 }, { pauseMs: 60001 }, { pauseMs: 0.5 }, { replayCount: -1 }, { completion: "unknown" }, { pauseCount: undefined }])("rejects invalid added telemetry %#", (change) => {
  expect(() => validateTestSession({ ...record, ...change })).toThrow();
});
it("loads existing v1 completed fixtures with explicit missing new measurements without rewriting or inventing zero", async () => {
  const { pauseCount: _p, pauseMs: _d, replayCount: _r, completion: _c, ...legacy } = record;
  const text = JSON.stringify({ version: 1, synthetic: true, verifiedTelemetry: false, records: [legacy] });
  const write = jest.fn();
  const loaded = await developerTestStorage({ read: async () => text, write, clear: jest.fn() }, () => true).load();
  expect(loaded.version).toBe(2);
  expect(loaded.records).toEqual([record]);
  expect(write).not.toHaveBeenCalled();
});
it("matches backend engagement reference cases, including incomplete sessions and zero active time", () => {
  const input = { ...record, attempted: 50, correct: 40, totalMs: 100000, activeMs: 60000, pauseMs: 12000 };
  // Same golden vector as backend test_experimental_engagement_known_values.
  expect(experimentalTestEngagement({ ...record, activeMs: 40000, totalMs: 50000, pauseMs: 10000 })).toMatchObject({ score: 0.84, completion: 1, active: 0.8, pauseEfficiency: 0.5 });
  const complete = experimentalTestEngagement(input);
  expect(complete).toEqual({ score: 0.8, missing: [], completion: 1, active: 0.6, pauseEfficiency: 0.6 });
  expect(experimentalTestEngagement({ ...input, completion: "abandoned" }).score).toBe(0.55);
  expect(experimentalTestEngagement({ ...input, completion: "interrupted" }).score).toBe(0.425);
  expect(experimentalTestEngagement({ ...input, activeMs: 0 }).score).toBe(0.5);
  expect(experimentalTestEngagement({ ...input, pauseMs: 0 }).score).toBe(0.88);
  expect(experimentalTestEngagement({ ...input, replayCount: 50, pauseCount: 90 })).toEqual(complete);
});
it("keeps engagement missing when required measurements are absent or insufficient", () => {
  for (const input of [{ ...record, pauseMs: null }, { ...record, target: 0, pauseMs: 0 }, { ...record, totalMs: 0, activeMs: 0, pauseMs: 0 }]) {
    const result = experimentalTestEngagement(input);
    expect(result.score).toBeNull(); expect(result.missing.length).toBeGreaterThan(0);
  }
});
it("offers friendly completion input, expandable technical details and explicit engagement diagnostics", async () => {
  render(<LearnerProgressScreen periodDays={30} />); await openTest();
  expect(screen.getByRole("header", { name: "Try a Reading Session" })).toBeTruthy();
  expect(screen.getByText("Sample Data")).toBeTruthy();
  expect(screen.queryByLabelText("Synthetic session UUID")).toBeNull();
  fireEvent.press(screen.getByRole("button", { name: "Developer Details" }));
  expect(screen.getByLabelText("Synthetic session UUID")).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "Hide Developer Details" }));
  fireEvent.changeText(screen.getByLabelText("Pause count (blank = missing)"), "0");
  fireEvent.changeText(screen.getByLabelText("Total pause duration (milliseconds; blank = missing)"), "0");
  fireEvent.changeText(screen.getByLabelText("Replay count (blank = missing)"), "2");
  fireEvent.press(screen.getByRole("radio", { name: "Session completion: Interrupted" }));
  fireEvent.press(screen.getByRole("button", { name: "Save" }));
  await screen.findByText("Synthetic record saved and read back from device storage.");
  expect(JSON.parse(mockDisk!).records[0]).toMatchObject({ completion: "interrupted", pauseCount: 0, pauseMs: 0, replayCount: 2 });
  fireEvent.press(screen.getByRole("tab", { name: "Analytics learner view" }));
  expect(screen.queryByText("Experimental engagement: 0.75 (0 to 1).")).toBeNull();
  expect(screen.getByText(/Analytics pending offline backend calculation/)).toBeTruthy();
});


it("does not write or inflate observations for an exact retry", async () => {
  const io = { read: async () => mockDisk, write: jest.fn(async (text: string) => { mockDisk = text; }), clear: async () => { mockDisk = null; } };
  const store = developerTestStorage(io, () => true);
  await store.save(record);
  const before = mockDisk;
  const retry = await store.save({ ...record });
  expect(retry.records).toHaveLength(1); expect(mockDisk).toBe(before);
  expect(io.write).toHaveBeenCalledTimes(1);
  await expect(store.save({ ...record, correct: 91 })).rejects.toThrow(/conflicting/);
  expect(mockDisk).toBe(before); expect(io.write).toHaveBeenCalledTimes(1);
});

afterEach(() => { delete process.env.EXPO_PUBLIC_COMPONENT4_DEVELOPER_TOOLS; });
