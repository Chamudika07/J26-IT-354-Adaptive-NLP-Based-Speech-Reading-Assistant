import { act, fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import { Platform, Text } from "react-native";
import { EducatorStudents } from "../components/EducatorStudents";
import { EducatorReportButton } from "../components/EducatorReportButton";
import { buildEducatorReport, educatorClassOverview, educatorReportStudents, educatorReportingPeriod, exportEducatorReport, type EducatorPdfFiles, type EducatorReportSelection } from "../export/educatorReports";
import type { ExpoPdfModules } from "../export/localAiPdf";
import { selectConnectedReplay } from "../preview/connectedSessionPreview";
import { publishScenario, scenarioId } from "../preview/selectedScenario";
import * as Print from "expo-print";
import * as Sharing from "expo-sharing";
import { EducatorAnalyticsScreen } from "../screens/EducatorAnalyticsScreen";
import { unavailableLiveDashboardProvider } from "../data/dashboardProvider";

jest.mock("expo-print", () => ({ printToFileAsync: jest.fn() }));
jest.mock("expo-sharing", () => ({ isAvailableAsync: jest.fn(), shareAsync: jest.fn() }));
jest.mock("expo-file-system/legacy", () => ({ cacheDirectory: "file:///cache/", copyAsync: jest.fn(), deleteAsync: jest.fn() }));

const sample = (index: number) => selectConnectedReplay({ index, development: true, demoMode: true, role: "learner" })!;
const selection = (student: number | null, index = 3): EducatorReportSelection => ({ development: true, demoMode: true, role: "educator", scenarioId: scenarioId(index, sample(index)), student });
const date = new Date("2026-10-21T10:00:00Z");
function native() {
  const modules: jest.Mocked<ExpoPdfModules> = { printToFileAsync: jest.fn().mockResolvedValue({ uri: "file:///cache/generated.pdf" }), isAvailableAsync: jest.fn().mockResolvedValue(true), shareAsync: jest.fn().mockResolvedValue(undefined) };
  const files: jest.Mocked<EducatorPdfFiles> = { cacheDirectory: "file:///cache/", copyAsync: jest.fn().mockResolvedValue(undefined), deleteAsync: jest.fn().mockResolvedValue(undefined) };
  return { modules, files };
}
beforeEach(() => { publishScenario(null); jest.clearAllMocks(); });
afterEach(() => { publishScenario(null); jest.restoreAllMocks(); });

it.each([0, 1, 2])("exports only student %s with permitted measurements, period and support history", student => {
  const students = educatorReportStudents(selection(student));
  const report = buildEducatorReport(selection(student), date);
  expect(report.filename).toBe(`ReadBuddy-${students[student]!.name.replaceAll(" ", "-")}-Analytics-2026-10-21.pdf`);
  expect(report.html).toContain("Individual Student Analytics Report");
  expect(report.html).toContain(students[student]!.name);
  for (const s of students.filter(s => s.index !== student)) expect(report.html).not.toContain(s.name);
  expect(report.html).toContain("1–30 January 2026");
  expect(report.html).toContain("Reading Support History");
  expect(report.html).toContain("per 100 attempted words");
  expect(report.html).toContain("WPM");
  expect(report.html).toContain("Sample Data");
  expect(report.html).toContain("21 October 2026 (UTC)");
  expect(report.html).not.toMatch(/learner_id|client_session_id|engagement|recommendation|Qwen|qwen|<script|https?:|src=/);
  expect(report.html).not.toContain("page-break-before:always");
  if (student === 2) expect(report.html).toContain("Not measured");
});

it("keeps class totals, all three student periods and Alex's scenario synchronized without pooling metrics", () => {
  const old = buildEducatorReport(selection(null), date);
  expect(old.filename).toBe("ReadBuddy-Class-Analytics-2026-10-21.pdf");
  for (const s of educatorReportStudents(selection(null))) expect(old.html).toContain(s.name);
  expect(old.html).toContain("11 completed sessions in available records");
  expect(old.html).toContain("no class averages or cross-student trend comparisons");
  expect(old.html).toContain("1 students with missing measurements");
  expect(old.html).toContain("1 students with at least one supported trend");
  const next = buildEducatorReport(selection(null, 6), date);
  expect(next.html).toContain("14 completed sessions in available records");
  expect(next.html).toContain("2 students with at least one supported trend");
  expect(buildEducatorReport(selection(1, 6), date)).toEqual(buildEducatorReport(selection(1, 3), date));
  expect(buildEducatorReport(selection(2, 6), date)).toEqual(buildEducatorReport(selection(2, 3), date));
});

it("fails closed for missing student evidence, reports incomplete class totals, and enforces context gates", () => {
  const missing = { ...selection(null), scenarioId: "mismatched" };
  expect(educatorClassOverview(educatorReportStudents(missing))).toEqual({ students: 3, sessions: 8, trends: 1, missing: 1, unavailable: 1 });
  const html = buildEducatorReport(missing, date).html;
  expect(html).toContain("Session totals are incomplete");
  expect(html).toContain("Alex Storybook</h2><p>Reading results unavailable");
  expect(() => buildEducatorReport({ ...missing, student: 0 }, date)).toThrow();
  for (const invalid of [{ role: "learner" }, { role: "guardian" }, { demoMode: false }, { development: false }, { student: -1 }, { student: 3 }, { student: 0.5 }]) {
    expect(() => buildEducatorReport({ ...selection(null), ...invalid } as EducatorReportSelection)).toThrow();
  }
  jest.replaceProperty(globalThis as typeof globalThis & { __DEV__: boolean }, "__DEV__", false);
  expect(() => buildEducatorReport(missing)).toThrow();
});

it.each(["ios", "android"])("uses on-device Print and native sharing on %s with a named PDF and safe cache handling", async platform => {
  const { modules, files } = native();
  const network = jest.spyOn(globalThis, "fetch").mockRejectedValue(Error("Network prohibited"));
  await exportEducatorReport({ selection: selection(1), platform, modules, files });
  expect(modules.printToFileAsync).toHaveBeenCalledWith(expect.objectContaining({ base64: false, width: 595, height: 842 }));
  const target = files.copyAsync.mock.calls[0]![0].to;
  expect(target).toMatch(/^file:\/\/\/cache\/ReadBuddy-Robin-Page-Analytics-\d{4}-\d{2}-\d{2}-\d+\.pdf$/);
  expect(modules.shareAsync).toHaveBeenCalledWith(target, { mimeType: "application/pdf", UTI: "com.adobe.pdf", dialogTitle: "Save ReadBuddy analytics report" });
  expect(files.deleteAsync).not.toHaveBeenCalledWith(target, { idempotent: true });
  expect(files.deleteAsync).toHaveBeenCalledWith("file:///cache/generated.pdf", { idempotent: true });
  expect(network).not.toHaveBeenCalled();
});

it("sanitizes generation, storage, sharing and cancellation failures without sharing stale results", async () => {
  for (const phase of ["print", "copy", "share", "unavailable", "cancelled", "uri"] as const) {
    const { modules, files } = native();
    if (phase === "print") modules.printToFileAsync.mockRejectedValue(Error("private provider details"));
    if (phase === "copy") files.copyAsync.mockRejectedValue(Error("private storage path"));
    if (phase === "share") modules.shareAsync.mockRejectedValue(Error("private error"));
    if (phase === "unavailable") modules.isAvailableAsync.mockResolvedValue(false);
    if (phase === "uri") modules.printToFileAsync.mockResolvedValue({ uri: "https://untrusted/report.pdf" });
    await expect(exportEducatorReport({ selection: selection(0), platform: "ios", modules, files, isCurrent: () => phase !== "cancelled" })).rejects.toThrow("The synthetic report PDF could not be exported.");
    if (phase !== "share") expect(modules.shareAsync).not.toHaveBeenCalled();
  }
  const { modules, files } = native();
  await expect(exportEducatorReport({ selection: selection(0), platform: "web", modules, files })).rejects.toMatchObject({ reason: "platform" });
  expect(modules.printToFileAsync).not.toHaveBeenCalled();
});

it("shows class and individual actions, updates class counts, and opens the mocked iPhone share sheet", async () => {
  jest.replaceProperty(Platform, "OS", "ios");
  jest.mocked(Print.printToFileAsync).mockResolvedValue({ uri: "file:///cache/generated.pdf", numberOfPages: 1 });
  jest.mocked(Sharing.isAvailableAsync).mockResolvedValue(true);
  jest.mocked(Sharing.shareAsync).mockResolvedValue(undefined);
  publishScenario(3, sample(3));
  render(<EducatorStudents><Text>Independent example</Text></EducatorStudents>);
  expect(screen.getByLabelText("Completed Sessions: 11")).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "Download Class Analytics Report" }));
  await waitFor(() => expect(Sharing.shareAsync).toHaveBeenCalledTimes(1));
  await screen.findByRole("alert", { name: /Share sheet closed/ });
  act(() => publishScenario(4, sample(4)));
  expect(screen.getByLabelText("Completed Sessions: 12")).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "View Alex Storybook" }));
  fireEvent.press(screen.getByRole("button", { name: "Download Student Analytics Report" }));
  await waitFor(() => expect(Sharing.shareAsync).toHaveBeenCalledTimes(2));
  const html = jest.mocked(Print.printToFileAsync).mock.calls[1]![0]!.html!;
  expect(html).toContain("Alex Storybook"); expect(html).toContain("4 completed sessions");
  expect(html).not.toContain("Robin Page");
});

it("shows disabled unavailable PDF actions and sanitized failures", async () => {
  jest.replaceProperty(Platform, "OS", "ios");
  const view = render(<EducatorReportButton selection={selection(0)} unavailable />);
  expect(screen.getByRole("button").props.accessibilityState.disabled).toBe(true);
  expect(screen.getByText("Reading results are unavailable for this report.")).toBeTruthy();
  view.rerender(<EducatorReportButton selection={selection(0)} />);
  jest.mocked(Sharing.isAvailableAsync).mockRejectedValue(Error("secret"));
  fireEvent.press(screen.getByRole("button"));
  await screen.findByText("Could not share this PDF. Please try again. No saved copy is confirmed.");
  expect(screen.queryByText(/secret/)).toBeNull();
});

it("does not share an in-flight report after the selected scenario changes", async () => {
  jest.replaceProperty(Platform, "OS", "ios");
  let finish!: (value: { uri: string; numberOfPages: number }) => void;
  jest.mocked(Print.printToFileAsync).mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  jest.mocked(Sharing.isAvailableAsync).mockResolvedValue(true);
  publishScenario(3, sample(3));
  render(<EducatorStudents><Text>Independent example</Text></EducatorStudents>);
  fireEvent.press(screen.getByRole("button", { name: "Download Class Analytics Report" }));
  await waitFor(() => expect(Print.printToFileAsync).toHaveBeenCalledTimes(1));
  act(() => publishScenario(4, sample(4)));
  await act(async () => { finish({ uri: "file:///cache/old.pdf", numberOfPages: 1 }); });
  expect(Sharing.shareAsync).not.toHaveBeenCalled();
  expect(screen.queryByText(/Share sheet closed/)).toBeNull();
});

it("does not expose class reports through an unavailable live provider", async () => {
  publishScenario(3, sample(3));
  render(<EducatorAnalyticsScreen periodDays={30} provider={unavailableLiveDashboardProvider} />);
  await screen.findByText("Report temporarily unavailable");
  expect(screen.queryByRole("button", { name: "Download Class Analytics Report" })).toBeNull();
  expect(screen.queryByText("My Students")).toBeNull();
});


it("uses compact A4 typography and keep-together blocks without forced pages", () => {
  const html = buildEducatorReport(selection(0), date).html;
  expect(html).toContain("@page{size:A4;margin:14mm}");
  expect(html).toContain("font:11pt Arial");
  expect(html).toContain("small,.note,.metadata{font-size:10pt}");
  expect(html).toContain("h2,h3{break-after:avoid;page-break-after:avoid}");
  expect(html).toContain("tr,header,.student-intro,.measurements,.progress,.support-history,.report-notes{break-inside:avoid;page-break-inside:avoid}");
  expect(html).toContain("thead{display:table-header-group");
  expect(html).toContain(".student{break-inside:auto;page-break-inside:auto}");
  expect(html).not.toMatch(/break-(before|after):\s*(always|page)|height:\s*(100vh|297mm)/);
  expect(html.match(/Not enough reading sessions to show a reliable trend yet\./g)).toHaveLength(1);
  expect(html.match(/Sample Data/g)).toHaveLength(1);
  expect(html.match(/Fictional students, not real learner records/g)).toHaveLength(1);
  expect(html).toContain("<td>93%</td>");
  expect(html).toContain("<td>85.71 WPM</td>");
  expect(html).toContain("<td>5 per 100 attempted words</td>");
  expect(html).toContain("3 measured; 0 unavailable");
  expect(html).toContain("Active reading: 197 seconds; total session time: 220 seconds");
  const classHtml = buildEducatorReport(selection(null), date).html;
  expect(classHtml).toContain(".student+.student");
  expect(classHtml.match(/Sample Data/g)).toHaveLength(1);
  expect(classHtml.match(/class=\"student\"/g)).toHaveLength(3);
});

it("keeps supported comparisons and missing-data explanations while removing repeated cautions", () => {
  const sufficient = buildEducatorReport(selection(0, 6), date).html;
  expect(sufficient).toContain("Reading Accuracy increased between comparison periods.");
  expect(sufficient).toContain("Earlier average: 94%; recent average: 96%.");
  const missing = buildEducatorReport(selection(2), date).html;
  expect(missing).toContain("Not measured");
  expect(missing).toContain("Unavailable measurements are not zero and are excluded from metric comparisons.");
  expect(missing).toContain("0 measured; 2 unavailable");
  expect(missing).toContain("Support history shows recorded modes, not exact settings or recommended changes.");
});

it("formats half-open UTC periods accurately across months, years and partial days", () => {
  expect(educatorReportingPeriod("2026-01-01T00:00:00Z", "2026-01-31T00:00:00Z")).toBe("1\u201330 January 2026");
  expect(educatorReportingPeriod("2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z")).toBe("1 January 2026");
  expect(educatorReportingPeriod("2026-01-30T00:00:00Z", "2026-02-03T00:00:00Z")).toBe("30 January\u20132 February 2026");
  expect(educatorReportingPeriod("2025-12-31T00:00:00Z", "2026-01-02T00:00:00Z")).toBe("31 December 2025\u20131 January 2026");
  expect(educatorReportingPeriod("2026-01-01T00:00:00Z", "2026-01-02T09:00:00Z")).toBe("1 January 2026, 00:00:00.000 UTC to before 2 January 2026, 09:00:00.000 UTC");
  expect(() => educatorReportingPeriod("invalid", "2026-01-02T00:00:00Z")).toThrow();
});
