import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react-native";
import { Platform, ScrollView } from "react-native";
import * as Print from "expo-print";
import * as Sharing from "expo-sharing";

import { LocalAiPdfButton } from "../components/LocalAiPdfButton";
import * as pdf from "../export/localAiPdf";
import type { ExpoPdfModules } from "../export/localAiPdf";
import saved from "../preview/localReportSnapshot.json";
import contract from "../preview/syntheticReportDisplayContract.json";
import { buildSyntheticDashboard } from "../preview/syntheticData";
import { AIProgressReportScreen } from "../screens/AIProgressReportScreen";
import * as local from "../preview/localReportSnapshot";

jest.mock("expo-print", () => ({ printToFileAsync: jest.fn() }));
jest.mock("expo-sharing", () => ({ isAvailableAsync: jest.fn(), shareAsync: jest.fn() }));

const selection: pdf.PdfSelection = { development: true, demoMode: true, enabled: true, role: "learner" };
function snapshot() {
  return { schemaVersion: "synthetic-local-report-v1", synthetic: true, validated: true,
    source: "local-ollama", model: "qwen3:4b",
    generatedAt: "2026-01-02T00:00:00+00:00", ...contract, statements: [...contract.statements] };
}
function modules(): jest.Mocked<ExpoPdfModules> {
  return { printToFileAsync: jest.fn().mockResolvedValue({ uri: "file:///cache/report.pdf" }),
    isAvailableAsync: jest.fn().mockResolvedValue(true), shareAsync: jest.fn().mockResolvedValue(undefined) };
}
afterEach(() => jest.restoreAllMocks());

it("prepares only the validated January projection, with exact statements and friendly units", () => {
  const html = pdf.buildLocalAiReportHtml(snapshot(), selection);
  expect(html).toContain("ReadBuddy");
  expect(html).toContain("AI Progress Report");
  expect(html).toContain("2026-01-01 to 2026-01-31 (end exclusive, UTC)");
  expect(html).toContain("6 recorded synthetic sessions");
  expect(html).toContain("Correct words (%)");
  expect(html).toContain("<td>65</td><td>85</td>");
  expect(html).toContain("Words per minute");
  expect(html).toContain("<td>100</td><td>100</td>");
  expect(html).toContain("Hesitations per 100 words attempted");
  expect(html).toContain("<td>9</td><td>5</td>");
  expect(html).toContain("Not enough comparable evidence for a trend.");
  expect(html).toContain("SYNTHETIC LOCAL AI PREVIEW - NOT REAL LEARNER DATA");
  expect(html).toContain("ADVISORY ONLY");
  expect(html).toContain("local-ollama");
  expect(html).toContain("qwen3:4b");
  expect(html).toContain("2026-01-02 00:00:00 UTC");
  for (const text of contract.statements) expect(html).toContain(pdf.escapeHtml(text));
  const dashboard = buildSyntheticDashboard("learner", 30);
  expect(html).not.toContain(dashboard.reportingStartUtc.slice(0, 10));
  expect(html).not.toContain(dashboard.reportingEndUtc.slice(0, 10));
  for (const forbidden of ["learner_id", "session_id", "evidence_ref", "report_fingerprint", "API_KEY", "<script", "http://", "https://", "src="]) {
    expect(html).not.toContain(forbidden);
  }
  expect(html).not.toContain("page-break-before: always");
  expect(html).not.toContain("break-before: page");
});

it("can validate the saved snapshot without trusting its validated flag alone", () => {
  if (saved !== null) expect(() => pdf.buildLocalAiReportHtml(saved, selection)).not.toThrow();
  expect(() => pdf.buildLocalAiReportHtml({ ...snapshot(), statements: ["Accuracy is 999%"] }, selection)).toThrow(pdf.ReportPdfError);
});

it("escapes text before inserting it into HTML", () => {
  expect(pdf.escapeHtml('<script>"private" & \'data\'</script>')).toBe("&lt;script&gt;&quot;private&quot; &amp; &#39;data&#39;&lt;/script&gt;");
});

it.each([
  { role: "guardian" as const }, { role: "educator" as const }, { development: false },
  { demoMode: false }, { enabled: false },
])("rejects unauthorized selection before any native operation: %j", async (gate) => {
  const native = modules();
  await expect(pdf.exportLocalAiPdf({ snapshot: snapshot(), selection: { ...selection, ...gate }, platform: "ios", modules: native })).rejects.toMatchObject({ reason: "unavailable" });
  expect(native.printToFileAsync).not.toHaveBeenCalled();
  expect(native.shareAsync).not.toHaveBeenCalled();
});

it.each([null, {}, { ...snapshot(), validated: false }, { ...snapshot(), role: "guardian" },
  { ...snapshot(), statements: contract.statements.slice(1) }, { ...snapshot(), secret: "PRIVATE" },
  { ...snapshot(), reportingStartUtc: "2026-09-15T00:00:00+00:00" },
])("rejects unavailable or invalid snapshots without creating a file %#", async (value) => {
  const native = modules();
  await expect(pdf.exportLocalAiPdf({ snapshot: value, selection, platform: "android", modules: native })).rejects.toMatchObject({ reason: "unavailable" });
  expect(native.isAvailableAsync).not.toHaveBeenCalled();
});

it.each(["ios", "android"])("uses native PDF and local-file share options on %s", async (platform) => {
  const native = modules();
  const fetch = jest.spyOn(globalThis, "fetch");
  await pdf.exportLocalAiPdf({ snapshot: snapshot(), selection, platform, modules: native });
  expect(native.printToFileAsync).toHaveBeenCalledWith({ html: expect.stringContaining("AI Progress Report"), base64: false, width: 595, height: 842 });
  expect(native.shareAsync).toHaveBeenCalledWith("file:///cache/report.pdf", { mimeType: "application/pdf", UTI: "com.adobe.pdf", dialogTitle: "Save ReadBuddy synthetic AI report" });
  expect(fetch).not.toHaveBeenCalled();
});

it.each(["ios", "android"] as const)("connects the installed Expo adapter to the opted-in screen on %s", async (platform) => {
  jest.replaceProperty(Platform, "OS", platform);
  jest.spyOn(local, "readBundledLocalSnapshot").mockReturnValue(snapshot());
  jest.mocked(Print.printToFileAsync).mockResolvedValue({ uri: "file:///cache/native.pdf", numberOfPages: 2 });
  jest.mocked(Sharing.isAvailableAsync).mockResolvedValue(true);
  jest.mocked(Sharing.shareAsync).mockResolvedValue(undefined);
  expect(pdf.installedPdfModules()?.printToFileAsync).toBe(Print.printToFileAsync);
  expect(pdf.installedPdfModules()?.shareAsync).toBe(Sharing.shareAsync);
  const view = render(<AIProgressReportScreen dashboard={buildSyntheticDashboard("learner", 30)} demoMode periodDays={30} />);
  expect(screen.queryByRole("button", { name: "Download AI Report PDF" })).toBeNull();
  fireEvent.press(screen.getByRole("button", { name: "View Saved AI Report" }));
  const button = screen.getByRole("button", { name: "Download AI Report PDF" });
  expect(button).not.toBeDisabled();
  expect(button).toBeVisible();
  const scroll = screen.UNSAFE_getByType(ScrollView);
  expect(scroll.props.stickyHeaderIndices).toBeUndefined();
  expect(within(screen.getByTestId("previously-saved-ai-report")).getByRole("button", { name: "Download AI Report PDF" })).toBe(button);
  const source = screen.getByTestId("saved-ai-report-content");
  const tree = JSON.stringify(view.toJSON());
  expect(tree.indexOf(JSON.stringify(snapshot().statements.at(-1)))).toBeLessThan(tree.indexOf("Download AI Report PDF"));
  expect(within(source).getByText(snapshot().statements.at(-1)!)).toBeTruthy();
  fireEvent.press(button);
  await waitFor(() => expect(Sharing.shareAsync).toHaveBeenCalledWith("file:///cache/native.pdf", {
    mimeType: "application/pdf", UTI: "com.adobe.pdf", dialogTitle: "Save ReadBuddy synthetic AI report",
  }));
  await screen.findByRole("alert");
  const html = jest.mocked(Print.printToFileAsync).mock.calls.at(-1)![0]!.html!;
  for (const statement of snapshot().statements) expect(html).toContain(pdf.escapeHtml(statement));
  expect(html).toContain("2026-01-01 to 2026-01-31");
  expect(html).not.toContain("2026-10-15");
});

it.each(["web", "windows"])("does not substitute web downloads on %s", async (platform) => {
  const native = modules();
  await expect(pdf.exportLocalAiPdf({ snapshot: snapshot(), selection, platform, modules: native })).rejects.toMatchObject({ reason: "platform" });
  expect(native.isAvailableAsync).not.toHaveBeenCalled();
});

it("safely reports missing packages and unavailable sharing", async () => {
  await expect(pdf.exportLocalAiPdf({ snapshot: snapshot(), selection, platform: "ios", modules: null })).rejects.toMatchObject({ reason: "dependencies" });
  const native = modules();
  native.isAvailableAsync.mockResolvedValue(false);
  await expect(pdf.exportLocalAiPdf({ snapshot: snapshot(), selection, platform: "ios", modules: native })).rejects.toMatchObject({ reason: "sharing" });
  expect(native.printToFileAsync).not.toHaveBeenCalled();
});

it.each(["print", "share", "availability"])("sanitizes %s failures without raw errors or retries", async (phase) => {
  const native = modules();
  if (phase === "print") native.printToFileAsync.mockRejectedValue(new Error("PRIVATE file storage failure"));
  if (phase === "share") native.shareAsync.mockRejectedValue(new Error("PRIVATE share failure"));
  if (phase === "availability") native.isAvailableAsync.mockRejectedValue(new Error("PRIVATE error"));
  await expect(pdf.exportLocalAiPdf({ snapshot: snapshot(), selection, platform: "ios", modules: native })).rejects.toThrow("The synthetic report PDF could not be exported.");
  expect(native.printToFileAsync.mock.calls.length).toBeLessThanOrEqual(1);
  expect(native.shareAsync.mock.calls.length).toBeLessThanOrEqual(1);
});

it.each(["https://external.test/report.pdf", "file:///cache/report.html"])("rejects nonlocal/non-PDF file URI: %s", async (uri) => {
  const native = modules();
  native.printToFileAsync.mockResolvedValue({ uri });
  await expect(pdf.exportLocalAiPdf({ snapshot: snapshot(), selection, platform: "android", modules: native })).rejects.toMatchObject({ reason: "generation" });
  expect(native.shareAsync).not.toHaveBeenCalled();
});

it("does not open sharing after role/selection changes while PDF generation is pending", async () => {
  const native = modules();
  let current = true;
  native.printToFileAsync.mockImplementation(async () => { current = false; return { uri: "file:///cache/report.pdf" }; });
  await expect(pdf.exportLocalAiPdf({ snapshot: snapshot(), selection, platform: "ios", modules: native, isCurrent: () => current })).rejects.toMatchObject({ reason: "cancelled" });
  expect(native.shareAsync).not.toHaveBeenCalled();
});

it("disables the action until opt-in, a valid snapshot and native dependencies exist", () => {
  jest.spyOn(pdf, "installedPdfModules").mockReturnValue(null);
  const read = jest.spyOn(local, "readBundledLocalSnapshot").mockReturnValue(snapshot());
  render(<AIProgressReportScreen dashboard={buildSyntheticDashboard("learner", 30)} demoMode periodDays={30} />);
  expect(screen.queryByRole("button", { name: "Download AI Report PDF" })).toBeNull();
  expect(read).not.toHaveBeenCalled();
  fireEvent.press(screen.getByRole("button", { name: "View Saved AI Report" }));
  expect(screen.getByRole("button", { name: "Download AI Report PDF" })).toBeDisabled();
  expect(screen.getByText(/PDF download is not available in this build/)).toBeTruthy();
});

it("exposes the native action, blocks duplicate taps and never claims the file was saved", async () => {
  const native = modules();
  let resolve!: () => void;
  native.shareAsync.mockReturnValue(new Promise<void>((done) => { resolve = done; }));
  jest.spyOn(pdf, "installedPdfModules").mockReturnValue(native);
  jest.replaceProperty(Platform, "OS", "ios");
  render(<LocalAiPdfButton snapshot={snapshot()} selection={selection} />);
  const button = screen.getByRole("button", { name: "Download AI Report PDF" });
  fireEvent.press(button);
  fireEvent.press(button);
  expect(button).toBeDisabled();
  await waitFor(() => expect(native.shareAsync).toHaveBeenCalledTimes(1));
  await act(async () => resolve());
  expect(screen.getByRole("alert")).toHaveTextContent(/no saved copy is confirmed/);
});

it("shows sanitized native generation errors", async () => {
  const native = modules();
  native.printToFileAsync.mockRejectedValue(new Error("PRIVATE"));
  jest.spyOn(pdf, "installedPdfModules").mockReturnValue(native);
  jest.replaceProperty(Platform, "OS", "android");
  render(<LocalAiPdfButton snapshot={snapshot()} selection={selection} />);
  fireEvent.press(screen.getByRole("button", { name: "Download AI Report PDF" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(/PDF export unavailable/);
  expect(screen.queryByText(/PRIVATE/)).toBeNull();
});

it.each(["guardian", "educator"] as const)("does not expose any PDF action to %s", (role) => {
  render(<LocalAiPdfButton snapshot={snapshot()} selection={{ ...selection, role }} />);
  expect(screen.queryByRole("button")).toBeNull();
});

it("blocks release builds even if a caller supplies development=true", () => {
  jest.replaceProperty(globalThis as typeof globalThis & { __DEV__: boolean }, "__DEV__", false);
  expect(() => pdf.buildLocalAiReportHtml(snapshot(), selection)).toThrow(pdf.ReportPdfError);
  render(<LocalAiPdfButton snapshot={snapshot()} selection={selection} />);
  const button = screen.getByRole("button", { name: "Download AI Report PDF" });
  expect(button).toBeVisible();
  expect(button).toBeDisabled();
  expect(screen.getByText(/only in the demo development build/)).toBeVisible();
});

it.each([
  { development: false }, { enabled: false },
])("keeps the PDF action visible but disabled when a learner preview gate fails: %j", (gate) => {
  const native = modules();
  jest.spyOn(pdf, "installedPdfModules").mockReturnValue(native);
  render(<LocalAiPdfButton snapshot={snapshot()} selection={{ ...selection, ...gate }} compact />);
  const button = screen.getByRole("button", { name: "Download AI Report PDF" });
  expect(button).toBeVisible();
  expect(button).toBeDisabled();
  fireEvent.press(button);
  expect(native.printToFileAsync).not.toHaveBeenCalled();
  expect(native.shareAsync).not.toHaveBeenCalled();
});

it("keeps a missing native adapter visible with a reason instead of hiding or crashing", () => {
  jest.spyOn(pdf, "installedPdfModules").mockImplementation(() => { throw new Error("PRIVATE"); });
  render(<LocalAiPdfButton snapshot={snapshot()} selection={selection} compact />);
  expect(screen.getByRole("button", { name: "Download AI Report PDF" })).toBeDisabled();
  expect(screen.getByText("PDF download is not available in this build.")).toBeVisible();
  expect(screen.queryByText(/PRIVATE/)).toBeNull();
});

it("shows invalid snapshots and unsupported platforms as disabled actions with reasons", () => {
  jest.replaceProperty(Platform, "OS", "web");
  render(<LocalAiPdfButton snapshot={{ ...snapshot(), validated: false }} selection={selection} compact />);
  expect(screen.getByRole("button", { name: "Download AI Report PDF" })).toBeDisabled();
  expect(screen.getByText(/Open a saved AI report first/)).toBeVisible();
  expect(screen.getByText("PDF export requires the Android or iOS app.")).toBeVisible();
});


it("uses a flowing source section with a grouped closing disclosure instead of a forced disclaimer page", () => {
  const html = pdf.buildLocalAiReportHtml(snapshot(), selection);
  expect(html).toContain("@page { size: A4; margin: 16mm; }");
  expect(html).not.toMatch(/(?:page-break-before:\s*always|break-before:\s*page|height:\s*100vh)/);
  expect(html).toContain("header, .student, tr, .source-intro, .closing { break-inside: avoid; page-break-inside: avoid; }");
  expect(html).toContain("orphans: 3; widows: 3;");
  expect(html).toMatch(/<div class="closing">[\s\S]*class="statement"[\s\S]*<footer>[\s\S]*<\/footer>\s*<\/div>/);
  expect(html.match(/<footer>/g)).toHaveLength(1);
});
it("adds fixed display-only demo student labels after validation, never accepts a real identity", () => {
  const html = pdf.buildLocalAiReportHtml(snapshot(), selection);
  expect(html).toContain("Student Information");
  expect(html).toContain("<dt>Student Name</dt><dd>Demo Learner</dd>");
  expect(html).toContain("<dt>Student ID</dt><dd>DEMO-001</dd>");
  expect(html).toContain("<dt>Data Type</dt><dd>Sample Data</dd>");
  expect(html).toContain("Display-only demo identifiers - not an authoritative learner identity. No identity is inferred from reading sessions.");
  expect(html.indexOf("Student Information")).toBeLessThan(html.indexOf("Your reading measurements"));
  expect(() => pdf.buildLocalAiReportHtml({ ...snapshot(), studentName: "PRIVATE", studentId: "PRIVATE" }, selection)).toThrow(pdf.ReportPdfError);
  expect(snapshot().statements.join(" ")).not.toContain("DEMO-001");
  expect(snapshot().statements.join(" ")).not.toContain("Demo Learner");
});
it("separates friendly display explanations from every unchanged source statement and preserves insufficient evidence", () => {
  const original = snapshot();
  const before = JSON.stringify(original);
  const html = pdf.buildLocalAiReportHtml(original, selection);
  const display = html.slice(html.indexOf("<table"), html.indexOf("<section class=\"source-statements\""));
  expect(display).not.toContain("reading_accuracy");
  expect(display).not.toContain("reading_fluency_wpm");
  expect(display).not.toContain("hesitation_rate_per_word");
  expect(display).toContain("Measurements increased in comparable observations; this does not establish improvement in ability.");
  expect(display).toContain("Insufficient comparable evidence for a trend.");
  expect(display).not.toMatch(/unlocked|improved ability|reduced difficulty/i);
  const source = html.slice(html.indexOf("<section class=\"source-statements\""));
  for (const text of original.statements) expect(source).toContain(pdf.escapeHtml(text));
  expect(JSON.stringify(original)).toBe(before);
  expect(html).toContain("Friendly labels and unit conversions above are display-only.");
});
