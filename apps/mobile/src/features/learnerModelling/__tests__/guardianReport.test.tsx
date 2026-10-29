import * as browserPdf from "../export/browserAiPdf";
import { GuardianReportButton } from "../components/GuardianReportButton";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import { Platform } from "react-native";
import * as Print from "expo-print";
import * as Sharing from "expo-sharing";
import * as Files from "expo-file-system/legacy";
import { ParentDashboard } from "../components/ParentDashboard";
import { buildGuardianReport, exportGuardianReport, type GuardianReportData } from "../export/guardianReport";
import { selectRoleScenario } from "../preview/roleScenarioResults";
import { selectConnectedReplay } from "../preview/connectedSessionPreview";
import { scenarioId } from "../preview/selectedScenario";
import { escapeHtml } from "../export/localAiPdf";
jest.mock("expo-print", () => ({ printToFileAsync: jest.fn() }));
jest.mock("expo-sharing", () => ({ isAvailableAsync: jest.fn(), shareAsync: jest.fn() }));
jest.mock("expo-file-system/legacy", () => ({ cacheDirectory: "file:///cache/", copyAsync: jest.fn(), deleteAsync: jest.fn() }));
const projection = (i: number) => selectRoleScenario("guardian", scenarioId(i, selectConnectedReplay({ index: i, development: true, demoMode: true, role: "learner" })!))!.projection;
beforeEach(() => {
  jest.clearAllMocks(); jest.replaceProperty(Platform, "OS", "ios");
  jest.mocked(Print.printToFileAsync).mockResolvedValue({ uri: "file:///cache/source.pdf", numberOfPages: 1 });
  jest.mocked(Sharing.isAvailableAsync).mockResolvedValue(true); jest.mocked(Sharing.shareAsync).mockResolvedValue(undefined);
  jest.mocked(Files.copyAsync).mockResolvedValue(undefined); jest.mocked(Files.deleteAsync).mockResolvedValue(undefined);
});
afterEach(() => jest.restoreAllMocks());
it("exports the currently displayed Guardian scenario after switching Samples 1, 3 and 6", async () => {
  const view = render(<ParentDashboard projection={projection(1)} selection="Sample 1" />);
  for (const i of [1, 3, 6]) {
    const p = projection(i); view.rerender(<ParentDashboard projection={p} selection={`Sample ${i}`} />);
    fireEvent.press(screen.getByRole("button", { name: "Download Progress Report" }));
    await waitFor(() => expect(Sharing.shareAsync).toHaveBeenCalledTimes([1, 3, 6].indexOf(i) + 1));
    await waitFor(() => expect(screen.getByRole("button", { name: "Download Progress Report" })).toBeEnabled());
    const html = jest.mocked(Print.printToFileAsync).mock.calls.at(-1)![0]!.html!;
    expect(html).toContain(`Selected reading scenario: Sample ${i}`);
    expect(html).toContain(`${i} ${i === 1 ? "session" : "sessions"} completed`);
    expect(html.match(/Fictional Demonstration Data/g)).toHaveLength(1);
    expect(html).toContain("Name unavailable"); expect(html).toContain("1 January 2026");
    for (const c of p.contexts) for (const m of c.metrics) {
      expect(html).toContain(escapeHtml(m.explanation));
      if (m.latest_value !== null) expect(html).toContain(String(Number((Number(m.latest_value) * (m.metric_name === "reading_fluency_wpm" ? 1 : 100)).toFixed(2))));
    }
    for (const s of p.support_exposures) expect(html).toContain(escapeHtml(s.support_label));
    if (i === 1) { expect(html).toContain("More reading sessions are needed to see a trend"); expect(html).not.toContain("<th>First</th>"); }
    expect(html).not.toMatch(/Qwen3|PostgreSQL|experimental engagement|Recommended action/);
    expect(Sharing.shareAsync).toHaveBeenLastCalledWith(expect.stringMatching(/^file:\/\/\/cache\/ReadBuddy-Parent-Progress-.*\.pdf$/), expect.objectContaining({ mimeType: "application/pdf", UTI: "com.adobe.pdf" }));
  }
});
it("exports zero sessions and missing metrics without inventing values or comparison charts", async () => {
  const view = render(<ParentDashboard projection={projection(0)} selection="Before Reading" />);
  fireEvent.press(screen.getByRole("button", { name: "Download Progress Report" }));
  await screen.findByRole("alert");
  let html = jest.mocked(Print.printToFileAsync).mock.calls.at(-1)![0]!.html!;
  expect(html).toContain("0 sessions completed"); expect(html).toContain("Unavailable"); expect(html).not.toContain("<th>First</th>");
  const p = projection(1); p.contexts[0]!.metrics.splice(0, 1);
  view.rerender(<ParentDashboard projection={p} selection="Sample 1" />);
  fireEvent.press(screen.getByRole("button", { name: "Download Progress Report" })); await screen.findByRole("alert");
  html = jest.mocked(Print.printToFileAsync).mock.calls.at(-1)![0]!.html!;
  expect(html).toContain("<th>Reading Accuracy</th><td>Unavailable</td>");
});
it.each(["print", "share", "unavailable"])("handles %s errors without exposing native error details", async phase => {
  if (phase === "print") jest.mocked(Print.printToFileAsync).mockRejectedValue(Error("private error"));
  if (phase === "share") jest.mocked(Sharing.shareAsync).mockRejectedValue(Error("private error"));
  if (phase === "unavailable") jest.mocked(Sharing.isAvailableAsync).mockResolvedValue(false);
  render(<ParentDashboard projection={projection(3)} />);
  fireEvent.press(screen.getByRole("button", { name: "Download Progress Report" }));
  await screen.findByText("Could not share your progress report. Please try again.");
  expect(screen.queryByText(/private error/)).toBeNull();
  expect(screen.getByRole("button", { name: "Download Progress Report" })).toBeEnabled();
});
it("cancels pending export on scenario change and prevents duplicate taps", async () => {
  let finish!: (value: { uri: string; numberOfPages: number }) => void;
  jest.mocked(Print.printToFileAsync).mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  const view = render(<ParentDashboard projection={projection(1)} selection="Sample 1" />);
  const button = screen.getByRole("button", { name: "Download Progress Report" }); fireEvent.press(button); fireEvent.press(button);
  await waitFor(() => expect(Print.printToFileAsync).toHaveBeenCalledTimes(1));
  view.rerender(<ParentDashboard projection={projection(6)} selection="Sample 6" />);
  await act(async () => finish({ uri: "file:///cache/stale.pdf", numberOfPages: 1 }));
  expect(Sharing.shareAsync).not.toHaveBeenCalled(); expect(screen.queryByRole("alert")).toBeNull();
  expect(Files.deleteAsync).toHaveBeenCalledWith("file:///cache/stale.pdf", { idempotent: true });
});
it("escapes available names and does not enable export for unavailable Guardian evidence", () => {
  const data: GuardianReportData = { source: "Independent example", learnerName: "Fictional <Reader>", start: "2026-01-01T00:00:00Z", end: "2026-01-31T00:00:00Z", completed: 0, status: "More reading sessions are needed to see a trend", latest: [], contexts: [], support: [], notes: [] };
  expect(buildGuardianReport(data).html).toContain("Fictional &lt;Reader&gt;");
  render(<ParentDashboard projection={null} selection="Sample 3" />);
  expect(screen.queryByRole("button", { name: "Download Progress Report" })).toBeNull();
});
it("rejects non-native platforms before generating a PDF", async () => {
  const data: GuardianReportData = { source: "Independent example", start: "2026-01-01T00:00:00Z", end: "2026-01-31T00:00:00Z", completed: 0, status: "More reading sessions are needed to see a trend", latest: [], contexts: [], support: [], notes: [] };
  await expect(exportGuardianReport({ data, platform: "windows" })).rejects.toMatchObject({ reason: "platform" }); expect(Print.printToFileAsync).not.toHaveBeenCalled();
});

it.each([0, 1, 3, 6])("opens the identical Guardian scenario %s HTML on web without native calls", async index => {
  jest.replaceProperty(Platform, "OS", "web");
  const open = jest.spyOn(browserPdf, "openBrowserReport").mockImplementation(() => {});
  const network = jest.spyOn(globalThis, "fetch");
  render(<ParentDashboard projection={projection(index)} selection={`Sample ${index}`} />);
  fireEvent.press(screen.getByRole("button", { name: "Print / Save Guardian Report as PDF" }));
  await screen.findByText(/Report opened. Select Print/);
  const html = open.mock.calls[0]![0];
  expect(html).toContain(`Selected reading scenario: Sample ${index}`);
  expect(html).toContain(`${index} ${index === 1 ? "session" : "sessions"} completed`);
  expect(html).toContain("Fictional Demonstration Data");
  for (const c of projection(index).contexts) for (const m of c.metrics) expect(html).toContain(escapeHtml(m.explanation));
  if (index === 0) { expect(html).toContain("Unavailable"); expect(html).toContain("More reading sessions are needed to see a trend"); expect(html).not.toContain("<th>First</th>"); }
  expect(Print.printToFileAsync).not.toHaveBeenCalled(); expect(Sharing.shareAsync).not.toHaveBeenCalled(); expect(network).not.toHaveBeenCalled();
});
it("rejects invalid or unauthorized Guardian web selections and unavailable evidence", async () => {
  const open = jest.spyOn(browserPdf, "openBrowserReport").mockImplementation(() => {});
  const data: GuardianReportData = { source: "Independent example", start: "2026-01-01T00:00:00Z", end: "2026-01-31T00:00:00Z", completed: 0, status: "More reading sessions are needed to see a trend", latest: [], contexts: [], support: [], notes: [] };
  for (const selection of [undefined, { development: true, demoMode: true, role: "learner" }, { development: true, demoMode: true, role: "educator" }, { development: true, demoMode: false, role: "guardian" }, { development: false, demoMode: true, role: "guardian" }]) {
    await expect(exportGuardianReport({ data, selection, platform: "web" })).rejects.toMatchObject({ reason: "unavailable" });
  }
  const selection = { development: true, demoMode: true, role: "guardian" };
  for (const invalid of [{ completed: -1 }, { start: "invalid" }, { end: data.start }, { latest: [{ label: "Accuracy", unit: "%", value: "95" }] }]) await expect(exportGuardianReport({ data: { ...data, ...invalid }, selection, platform: "web" })).rejects.toMatchObject({ reason: "unavailable" });
  expect(open).not.toHaveBeenCalled();
  jest.replaceProperty(Platform, "OS", "web");
  render(<GuardianReportButton data={data} />); expect(screen.getByRole("button")).toBeDisabled();
});
it("handles blocked Guardian popups and invalidates old browser reports on scenario changes", async () => {
  jest.replaceProperty(Platform, "OS", "web");
  const open = jest.spyOn(browserPdf, "openBrowserReport").mockImplementation(() => { throw new browserPdf.BrowserReportError("popup"); });
  const view = render(<ParentDashboard projection={projection(1)} selection="Sample 1" />);
  fireEvent.press(screen.getByRole("button", { name: "Print / Save Guardian Report as PDF" }));
  await screen.findByText("Your browser blocked the report window. Allow popups for ReadBuddy and try again.");
  open.mockImplementation(() => {});
  fireEvent.press(screen.getByRole("button", { name: "Print / Save Guardian Report as PDF" }));
  await screen.findByText(/Report opened. Select Print/);
  const current = open.mock.calls.at(-1)![1]!; expect(current()).toBe(true);
  view.rerender(<ParentDashboard projection={projection(6)} selection="Sample 6" />);
  expect(current()).toBe(false); expect(screen.queryByText(/Report opened/)).toBeNull();
  view.rerender(<ParentDashboard projection={null} selection="Missing" />);
  expect(screen.queryByRole("button", { name: "Print / Save Guardian Report as PDF" })).toBeNull();
});
it("preserves Android Guardian generation and sharing", async () => {
  jest.replaceProperty(Platform, "OS", "android");
  render(<ParentDashboard projection={projection(1)} selection="Sample 1" />);
  fireEvent.press(screen.getByRole("button", { name: "Download Progress Report" }));
  await waitFor(() => expect(Sharing.shareAsync).toHaveBeenCalledTimes(1));
  expect(Print.printToFileAsync).toHaveBeenCalledTimes(1);
});
