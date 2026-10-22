import { act, fireEvent, render, screen } from "@testing-library/react-native";
import * as fs from "expo-file-system/legacy";
import * as sharing from "expo-sharing";
import App from "../../../../App";
import bundledArtifact from "../preview/connectedSessionPreview.json";
import replay from "../preview/connectedSessionReplay.json";
import example from "../preview/connectedSessionExample.json";
import * as selection from "../preview/connectedSessionPreview";
import { selectConnectedPreview, type ConnectedArtifact } from "../preview/connectedSessionPreview";
import { exportDeveloperSessions } from "../preview/exportDeveloperSessions";
import { LearnerProgressScreen } from "../screens/LearnerProgressScreen";
import { unavailableLiveDashboardProvider } from "../data/dashboardProvider";
import { publishScenario } from "../preview/selectedScenario";

jest.mock("../preview/demoPersistence", () => ({ demoStorage: () => ({ load: async () => null, save: async () => {} }) }));

const artifact = bundledArtifact as unknown as ConnectedArtifact;
let mockDisk: string | null = null;
let mockExport: string | null = null;
jest.mock("expo-file-system/legacy", () => ({
  documentDirectory: "file://test-documents/", cacheDirectory: "file://cache/",
  getInfoAsync: jest.fn(async () => mockDisk === null ? { exists: false } : { exists: true, isDirectory: false, size: mockDisk.length }),
  readAsStringAsync: jest.fn(async () => mockDisk),
  writeAsStringAsync: jest.fn(async (uri: string, text: string) => { if (uri.startsWith("file://cache/")) mockExport = text; else mockDisk = text; }),
  deleteAsync: jest.fn(async () => { mockDisk = null; }),
}));
jest.mock("expo-sharing", () => ({ isAvailableAsync: jest.fn(async () => true), shareAsync: jest.fn(async () => {}) }));
beforeEach(() => { publishScenario(null); process.env.EXPO_PUBLIC_COMPONENT4_DEVELOPER_TOOLS = "1"; mockDisk = null; mockExport = null; jest.clearAllMocks(); });
afterEach(() => jest.restoreAllMocks());
const gates = { enabled: true, development: true, demoMode: true, role: "learner" as const };

it("accepts only the backend-generated pinned artifact and returns detached values", () => {
  expect(selectConnectedPreview({ ...gates, read: () => artifact })).toEqual(artifact);
  const result = selectConnectedPreview({ ...gates })!;
  result.metrics[0]!.explanation = "changed";
  expect(selectConnectedPreview({ ...gates })).toEqual(artifact);
  for (const change of [{ role: "guardian" }, { synthetic: false }, { context: { ...artifact.context, tier: "early" } }, { generatedAt: "unknown" }, { learner_id: "private" }, { recommendation: { ...artifact.recommendation, changes_applied: true } }, { metrics: [] }]) {
    expect(selectConnectedPreview({ ...gates, read: () => ({ ...artifact, ...change }) })).toBeNull();
  }
});
it.each([{ enabled: false }, { development: false }, { demoMode: false }, { role: "guardian" as const }, { role: "educator" as const }])("checks all opt-in/role/live gates before reading %#", (change) => {
  const read = jest.fn(() => artifact);
  expect(selectConnectedPreview({ ...gates, ...change, read })).toBeNull();
  expect(read).not.toHaveBeenCalled();
});
async function openTest() {
  await screen.findByText("Hi, Reader!");
  fireEvent.press(screen.getByRole("button", { name: "Open Reading Session Test" }));
}
it("selects one source, context, period and generation timestamp across all four connected views", async () => {
  const fetchSpy = jest.spyOn(globalThis, "fetch");
  render(<LearnerProgressScreen periodDays={30} />); await openTest();
  expect(screen.queryByText("Your Reading Journey")).toBeNull();
  if (screen.queryByRole("button", { name: "Developer Details" })) fireEvent.press(screen.getByRole("button", { name: "Developer Details" }));
  fireEvent.press(screen.getByRole("button", { name: "Select connected backend preview" }));
  for (const [tab, title] of [["Home", "Hi, Reader!"], ["Analytics", "My Reading Analytics"], ["Suggestions", "Reading Tips"], ["Profile", "My Profile"]]) {
    fireEvent.press(screen.getByRole("tab", { name: `${tab} learner view` }));
    expect(screen.getByText(title!)).toBeTruthy();
    expect(screen.getByText(tab === "Home" ? "Demo Mode \u00b7 Fictional data" : tab === "Analytics" ? "Demo \u00b7 Fictional data" : "Sample Data")).toBeTruthy();
    fireEvent.press(screen.getByRole("button", { name: "Developer Details" }));
    expect(screen.getByText(`Generated: ${artifact.generatedAt}`)).toBeTruthy();
    expect(screen.getByText(`Reporting period: ${artifact.reportingStartUtc} to ${artifact.reportingEndUtc} (UTC, end exclusive).`)).toBeTruthy();
    if (tab === "Analytics") {
      for (const label of ["Reading Accuracy", "Reading Speed", "Hesitation Frequency"]) expect(screen.getByRole("header", { name: `${label} across sessions` })).toBeTruthy();
      expect(screen.getByRole("button", { name: "View Reading Tips" })).toBeTruthy();
      continue;
    }
    expect(screen.getByText(artifact.recommendation?.action ?? "Recommendation unavailable")).toBeTruthy();
    for (const metric of artifact.metrics) expect(screen.getByText(metric.display_label)).toBeTruthy();
    expect(screen.getByText("The saved Qwen3 AI report is independent and is not derived from these sessions.")).toBeTruthy();
    expect(screen.queryByText("Hi, reader!")).toBeNull();
  }
  fireEvent.press(screen.getByRole("button", { name: "Back to Reading Home" }));
  expect(screen.getByText("Reading Settings")).toBeTruthy();
  expect(fetchSpy).not.toHaveBeenCalled();
  expect(fs.readAsStringAsync).not.toHaveBeenCalled();
});
it("shows invalid artifact and unavailable recommendations without substituting demo advice", async () => {
  const spy = jest.spyOn(selection, "selectConnectedPreview").mockReturnValue(null);
  render(<LearnerProgressScreen periodDays={30} />); await openTest();
  if (screen.queryByRole("button", { name: "Developer Details" })) fireEvent.press(screen.getByRole("button", { name: "Developer Details" }));
  fireEvent.press(screen.getByRole("button", { name: "Select connected backend preview" }));
  fireEvent.press(screen.getByRole("tab", { name: "Suggestions learner view" }));
  expect(screen.getByRole("alert")).toHaveTextContent("These reading results could not be opened. Please return Home and try again. No other results have been substituted.");
  expect(screen.queryByText("Adaptive recommendation")).toBeNull();
  spy.mockReturnValue({ ...artifact, recommendation: null, recommendationExplanation: ["Insufficient comparable completed-session evidence."] } as ConnectedArtifact);
  fireEvent.press(screen.getByRole("button", { name: "Open Reading Session Test" }));
  if (screen.queryByRole("button", { name: "Developer Details" })) fireEvent.press(screen.getByRole("button", { name: "Developer Details" }));
  fireEvent.press(screen.getByRole("button", { name: "Select connected backend preview" }));
  fireEvent.press(screen.getByRole("tab", { name: "Suggestions learner view" }));
  expect(screen.getByText("Recommendation unavailable")).toBeTruthy();
  if (artifact.recommendation) expect(screen.queryByText(artifact.recommendation.action)).toBeNull();
});
it.each(["Guardian", "Educator"])("shares only selected scenario identity when switching to %s", async (role) => {
  render(<App />); await openTest();
  if (screen.queryByRole("button", { name: "Developer Details" })) fireEvent.press(screen.getByRole("button", { name: "Developer Details" }));
  fireEvent.press(screen.getByRole("button", { name: "Select connected backend preview" }));
  fireEvent.press(screen.getByRole("tab", { name: `${role} sample preview` }));
  await screen.findByText(role === "Guardian" ? "Parent Dashboard" : "Teacher Dashboard");
  if (artifact.recommendation) expect(screen.queryByText(artifact.recommendation.action)).toBeNull();
  fireEvent.press(screen.getByRole("tab", { name: "Learner sample preview" }));
  await screen.findByText("Hi, Reader!");
  expect(screen.getByText("Hi, Reader!")).toBeTruthy();
});
it("blocks connected selection and export in live and production contexts", async () => {
  const view = render(<LearnerProgressScreen periodDays={30} provider={unavailableLiveDashboardProvider} />);
  await act(async () => {});
  expect(screen.queryByRole("button", { name: "Open Reading Session Test" })).toBeNull();
  view.unmount();
  jest.replaceProperty(globalThis as typeof globalThis & { __DEV__: boolean }, "__DEV__", false);
  render(<LearnerProgressScreen periodDays={30} />);
  await screen.findByText("Hi, Reader!");
  expect(screen.queryByRole("button", { name: "Open Reading Session Test" })).toBeNull();
  await expect(exportDeveloperSessions(() => true)).rejects.toThrow();
  expect(sharing.shareAsync).not.toHaveBeenCalled();
});
it("explicitly exports saved validated samples through native sharing without uploading or exporting unsaved changes", async () => {
  mockDisk = JSON.stringify(example);
  const fetchSpy = jest.spyOn(globalThis, "fetch");
  render(<LearnerProgressScreen periodDays={30} />); await openTest();
  expect(sharing.shareAsync).not.toHaveBeenCalled();
  fireEvent.changeText(screen.getByLabelText("Words correct"), "1");
  if (screen.queryByRole("button", { name: "Developer Details" })) fireEvent.press(screen.getByRole("button", { name: "Developer Details" }));
  fireEvent.press(screen.getByRole("button", { name: "Export saved sample sessions" }));
  await screen.findByText("Export share sheet closed. Saving or cancelling is handled by your device; no exported copy is confirmed.");
  expect(JSON.parse(mockExport!)).toEqual(example);
  expect(sharing.shareAsync).toHaveBeenCalledWith("file://cache/readbuddy-component4-sample-sessions.json", expect.objectContaining({ mimeType: "application/json" }));
  expect(fetchSpy).not.toHaveBeenCalled();
});
it("rejects malformed export storage and unavailable sharing safely", async () => {
  mockDisk = "invalid";
  await expect(exportDeveloperSessions(() => true)).rejects.toThrow("Synthetic export unavailable. Check saved records and native file sharing.");
  expect(sharing.shareAsync).not.toHaveBeenCalled();
  mockDisk = JSON.stringify(example);
  jest.mocked(sharing.isAvailableAsync).mockResolvedValueOnce(false);
  await expect(exportDeveloperSessions(() => true)).rejects.toThrow();
  expect(sharing.shareAsync).not.toHaveBeenCalled();
});


it("replays actual backend prefixes through analytics, history, suggestions and report preparation", async () => {
  const fetchSpy = jest.spyOn(globalThis, "fetch");
  render(<LearnerProgressScreen periodDays={30} />); await openTest();
  fireEvent.press(screen.getByRole("button", { name: "Start Demo Reading Journey" }));
  fireEvent.press(screen.getByRole("tab", { name: "Home learner view" }));
  expect(screen.getByText(/0 eligible completed sessions/)).toBeTruthy();
  expect(screen.getByText("Recommendation unavailable")).toBeTruthy();
  if (replay.length > 1) {
    fireEvent.press(screen.getByRole("button", { name: "Add Next Sample" }));
    expect(screen.getByText(/1 eligible completed sessions/)).toBeTruthy();
    fireEvent.press(screen.getByRole("button", { name: "Next: Analytics" }));
  fireEvent.press(screen.getByRole("button", { name: "View Reading History" }));
  expect(screen.getByText(/S1.*Completed/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "View Reading Tips" })).toBeTruthy();
  }
  for (let index = 2; index < replay.length; index++) fireEvent.press(screen.getByRole("button", { name: "Add Next Sample" }));
  expect(screen.getByRole("button", { name: "Add Next Sample" })).toBeDisabled();
  fireEvent.press(screen.getByRole("button", { name: "Go to: Report" }));
  expect(screen.getByText("My Reading Report")).toBeTruthy();
  expect(screen.getByText("Reading Progress Summary")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Download AI Report PDF" })).toBeNull();
  fireEvent.press(screen.getByRole("button", { name: "Developer Details" }));
  for (const statement of replay.at(-1)!.reportStatements) expect(screen.getByText(statement)).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "Open Saved AI Report" }));
  expect(screen.getByText("This saved AI report is separate from your current reading journey.")).toBeTruthy();
  expect(screen.getByRole("button", { name: "Download AI Report PDF" })).toBeDisabled();
  fireEvent.press(screen.getByRole("button", { name: "Back to Reading Summary" }));
  fireEvent.press(screen.getByRole("button", { name: "Reset Journey" }));
  expect(screen.getByText(/0 eligible completed sessions/)).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "Reset connected demo" }));
  await screen.findByText("My Reading Report");
  fireEvent.press(screen.getByRole("button", { name: "Developer Details" }));
  expect(screen.getByText("AI GENERATION NOT CONNECTED")).toBeTruthy();
  expect(screen.queryByText(/eligible completed sessions/)).toBeNull();
  expect(mockDisk).toBeNull(); expect(fetchSpy).not.toHaveBeenCalled();
});

it("rejects changed replay artifacts and other roles before reading them", () => {
  expect(selection.selectConnectedReplay({ index: 0, development: true, demoMode: true, role: "learner", read: () => [] })).toBeNull();
  const read = jest.fn(() => replay);
  expect(selection.selectConnectedReplay({ index: 0, development: true, demoMode: true, role: "educator", read })).toBeNull();
  expect(read).not.toHaveBeenCalled();
});

it("invalid input and conflicting retries preserve prior saved observations", async () => {
  mockDisk = JSON.stringify(example);
  render(<LearnerProgressScreen periodDays={30} />); await openTest();
  fireEvent.press(screen.getByRole("button", { name: "Load" }));
  await screen.findByText(`Loaded ${example.records.length} synthetic records from device storage.`);
  const before = mockDisk;
  fireEvent.changeText(screen.getByLabelText("Words correct"), "101");
  fireEvent.press(screen.getByRole("button", { name: "Save" }));
  expect(screen.getByRole("alert")).toBeTruthy(); expect(mockDisk).toBe(before);
  fireEvent.press(screen.getByRole("button", { name: "Developer Details" }));
  fireEvent.changeText(screen.getByLabelText("Synthetic session UUID"), example.records[0]!.id);
  fireEvent.changeText(screen.getByLabelText("Words correct"), "1");
  fireEvent.press(screen.getByRole("button", { name: "Save" }));
  await screen.findByText("Duplicate synthetic session ID with conflicting measurements. Previous saved data is unchanged.");
  expect(mockDisk).toBe(before);
  fireEvent.press(screen.getByRole("tab", { name: "Analytics learner view" }));
  expect(screen.queryByText("Checking developer device storage...")).toBeNull();
});


it("rejects prepared replay in a release build even if caller flags claim development", () => {
  jest.replaceProperty(globalThis as typeof globalThis & { __DEV__: boolean }, "__DEV__", false);
  const read = jest.fn(() => replay);
  expect(selection.selectConnectedReplay({ index: 0, development: true, demoMode: true, role: "learner", read })).toBeNull();
  expect(selection.selectConnectedPreview({ ...gates, read: () => artifact })).toBeNull();
  expect(read).not.toHaveBeenCalled();
});


it("guides the child through one next step while keeping developer controls collapsed", async () => {
  render(<LearnerProgressScreen periodDays={30} />); await openTest();
  expect(screen.queryByRole("button", { name: "Export saved sample sessions" })).toBeNull();
  expect(screen.queryByLabelText("Synthetic session UUID")).toBeNull();
  fireEvent.press(screen.getByRole("button", { name: "Start Demo Reading Journey" }));
  expect(screen.getByText("Hi, Reader!")).toBeTruthy();
  expect(screen.getByText("0 completed sample sessions")).toBeTruthy();
  expect(screen.queryByText(/^Source digest:/)).toBeNull();
  expect(screen.getByRole("button", { name: "Next: Analytics" })).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "Next: Analytics" }));
  expect(screen.getByText("My Reading Analytics")).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "View Reading Tips" }));
  expect(screen.getByRole("button", { name: "Next: Report" })).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "Next: Report" }));
  expect(screen.getByText("My Reading Report")).toBeTruthy();
  expect(screen.getByText("The saved Qwen3 AI report is independent and is not derived from these sessions.")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Download AI Report PDF" })).toBeNull();
});


it("shows labelled sample identity and temporary preferences beside connected observations", async () => {
  render(<LearnerProgressScreen periodDays={30} />); await openTest();
  fireEvent.press(screen.getByRole("button", { name: "Start Demo Reading Journey" }));
  fireEvent.press(screen.getByRole("button", { name: "Add Next Sample" }));
  fireEvent.press(screen.getByRole("tab", { name: "Profile learner view" }));
  expect(screen.getByText("Demo Learner")).toBeTruthy();
  expect(screen.getByText("Sample age: 10 years")).toBeTruthy();
  expect(screen.getByText(/not a real learner record/)).toBeTruthy();
  expect(screen.getByText(/Your profile name is separate/)).toBeTruthy();
  for (const metric of replay[1]!.metrics) expect(screen.getByText(metric.display_label)).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "Reading Settings" }));
  fireEvent.press(screen.getByRole("radio", { name: "Reading font size: XL" }));
  fireEvent.press(screen.getByRole("tab", { name: "Profile learner view" }));
  expect(screen.getByText(/Font size: Extra large/)).toBeTruthy();
  expect(screen.getByText(/no reading support changes/)).toBeTruthy();
  expect(screen.getByText(/1 eligible completed sessions/)).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "Reading Settings" }));
  fireEvent.press(screen.getByRole("button", { name: "Reset Settings" }));
  fireEvent.press(screen.getByRole("tab", { name: "Profile learner view" }));
  expect(screen.getByText(/Font size: Comfortable/)).toBeTruthy();
});

it("labels the same sample identity in role demos without carrying learner drafts", async () => {
  render(<App />); await screen.findByText("Demo Learner");
  expect(screen.getByText("Demo Mode \u00b7 Fictional data")).toBeTruthy();
  for (const role of ["Guardian", "Educator"]) {
    fireEvent.press(screen.getByRole("tab", { name: `${role} sample preview` }));
    if (role === "Educator") fireEvent.press(await screen.findByRole("button", { name: "View separate example" }));
  await screen.findByText(role === "Guardian" ? "Guardian progress summary" : "Educator reading analytics");
    expect(screen.getByText("Demo Learner")).toBeTruthy();
    expect(screen.queryByText("Your demo reading preferences")).toBeNull();
  }
});


it("exports custom calculation inputs honestly and never substitutes prepared results", async () => {
  render(<LearnerProgressScreen periodDays={30} />); await openTest();
  fireEvent.changeText(screen.getByLabelText("Words correct"), "55");
  fireEvent.press(screen.getByRole("button", { name: "Calculate My Results" }));
  await screen.findByText(/Next: save the shared file/);
  expect(JSON.parse(mockExport!).records[0].correct).toBe(55);
  expect(screen.queryByText("Your Reading Journey")).toBeNull();
  fireEvent.press(screen.getByRole("button", { name: "New sample session" }));
  fireEvent.changeText(screen.getByLabelText("Words correct"), "40");
  fireEvent.press(screen.getByRole("button", { name: "Calculate My Results" }));
  await screen.findByText(/Next: save the shared file/);
  expect(JSON.parse(mockExport!).records).toHaveLength(2);
  const shared = jest.mocked(sharing.shareAsync).mock.calls.length;
  fireEvent.changeText(screen.getByLabelText("Words correct"), "999");
  fireEvent.press(screen.getByRole("button", { name: "Calculate My Results" }));
  await screen.findByText(/Invalid input/);
  expect(jest.mocked(sharing.shareAsync).mock.calls).toHaveLength(shared);
  expect(JSON.parse(mockDisk!).records).toHaveLength(2);
});


it("presents exact connected latest measurements across Home, Progress and Profile", async () => {
  render(<LearnerProgressScreen periodDays={30} />); await openTest();
  fireEvent.press(screen.getByRole("button", { name: "Developer Details" }));
  fireEvent.press(screen.getByRole("button", { name: "Select connected backend preview" }));
  for (const tab of ["Home", "Analytics", "Profile"]) {
    fireEvent.press(screen.getByRole("tab", { name: `${tab} learner view` }));
    expect(screen.getByText(tab === "Home" ? "Demo Mode \u00b7 Fictional data" : tab === "Analytics" ? "Demo \u00b7 Fictional data" : "Sample Data")).toBeTruthy();
    if (tab === "Analytics") {
      for (const metric of artifact.metrics) {
        const scale = metric.unit === "words_per_minute" ? 1 : 100;
        const expected = metric.latest_value === null ? "Unavailable" : String(Number((Number(metric.latest_value) * scale).toFixed(2)));
        expect(screen.getAllByText(expected).length).toBeGreaterThan(0);
      }
      expect(screen.getByText("per 100 attempted words")).toBeTruthy();
      continue;
    }
    for (const metric of artifact.metrics) {
      const expected = metric.latest_value === null ? "Unavailable"
        : metric.unit === "proportion" ? `${Number((Number(metric.latest_value) * 100).toFixed(2))}%`
        : metric.unit === "words_per_minute" ? `${Number(metric.latest_value)} words/minute` : `${Number((Number(metric.latest_value) * 100).toFixed(2))} hesitations per 100 attempted words`;
      expect(screen.getAllByText(expected).length).toBeGreaterThan(0);
    }
    expect(screen.getByText("ADVISORY ONLY")).toBeTruthy();
    expect(screen.getByText("The saved Qwen3 AI report is independent and is not derived from these sessions.")).toBeTruthy();
  }
});

afterEach(() => { delete process.env.EXPO_PUBLIC_COMPONENT4_DEVELOPER_TOOLS; });


it("keeps normal scenario selection separate from developer input tooling", async () => {
  delete process.env.EXPO_PUBLIC_COMPONENT4_DEVELOPER_TOOLS;
  render(<LearnerProgressScreen periodDays={30} />); await screen.findByText("Hi, Reader!");
  expect(screen.getAllByRole("button", { name: "Reading Results" })).toHaveLength(1);
  fireEvent.press(screen.getByRole("button", { name: "Reading Results" }));
  expect(screen.queryByRole("button", { name: "Developer Details" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Calculate My Results" })).toBeNull();
  fireEvent.press(screen.getByRole("radio", { name: "Sample scenario: Sample 1" }));
  fireEvent.press(screen.getByRole("button", { name: "Update My Progress" }));
  fireEvent.press(screen.getByRole("button", { name: "View Analytics" }));
  fireEvent.press(screen.getByRole("button", { name: "View Reading Tips" }));
  fireEvent.press(screen.getByRole("button", { name: "Next: My Reading Report" }));
  fireEvent.press(screen.getByRole("button", { name: "Read Current Summary" }));
  for (const text of replay[1]!.reportStatements) expect(screen.getByText(text)).toBeTruthy();
  expect(sharing.shareAsync).not.toHaveBeenCalled();
});

it("shows the backend action first and keeps full explanation optional", async () => {
  delete process.env.EXPO_PUBLIC_COMPONENT4_DEVELOPER_TOOLS;
  render(<LearnerProgressScreen periodDays={30} />); await screen.findByText("Hi, Reader!");
  fireEvent.press(screen.getByRole("button", { name: "Reading Results" }));
  fireEvent.press(screen.getByRole("radio", { name: `Sample scenario: Sample ${replay.length - 1}` }));
  fireEvent.press(screen.getByRole("button", { name: "Update My Progress" }));
  fireEvent.press(screen.getByRole("button", { name: "View Analytics" }));
  fireEvent.press(screen.getByRole("button", { name: "View Reading Tips" }));
  expect(screen.getByText(replay.at(-1)!.recommendation!.action)).toBeTruthy();
  const why = screen.getByRole("button", { name: "Why This Tip?" });
  expect(why.props.accessibilityState.expanded).toBe(false); fireEvent.press(why);
  for (const text of replay.at(-1)!.recommendationExplanation) expect(screen.getByText(text)).toBeTruthy();
  fireEvent.press(why); expect(why.props.accessibilityState.expanded).toBe(false);
  expect(screen.getByText("ADVISORY ONLY")).toBeTruthy();
});

it("keeps saved inputs pending when native export fails, without showing prepared results as calculations", async () => {
  jest.mocked(sharing.shareAsync).mockRejectedValueOnce(Error("private platform detail"));
  render(<LearnerProgressScreen periodDays={30} />); await openTest();
  fireEvent.changeText(screen.getByLabelText("Words correct"), "55");
  fireEvent.press(screen.getByRole("button", { name: "Calculate My Results" }));
  await screen.findByText("Your inputs are saved, but sharing did not open. Try Calculate My Results again.");
  expect(JSON.parse(mockDisk!).records[0].correct).toBe(55);
  expect(screen.queryByText(/Next: save the shared file/)).toBeNull();
  expect(screen.queryByText("private platform detail")).toBeNull();
  expect(screen.queryByText("Hi, Reader!")).toBeNull();
  expect(screen.getByText(/Otherwise, this shows the separate bundled example/)).toBeTruthy();
});
