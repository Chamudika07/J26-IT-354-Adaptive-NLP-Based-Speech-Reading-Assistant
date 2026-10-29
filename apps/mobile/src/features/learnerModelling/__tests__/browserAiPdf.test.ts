import { BrowserReportError, openBrowserReport } from "../export/browserAiPdf";
import { buildLocalAiReportHtml, escapeHtml, exportLocalAiPdf } from "../export/localAiPdf";
import * as browserPdf from "../export/browserAiPdf";
import snapshot from "../preview/localReportSnapshot.json";

const selection = { development: true, demoMode: true, enabled: true, role: "learner" as const };
function setup() {
  const nodes: Record<string, unknown>[] = [];
  const createElement = jest.fn((tag: string) => {
    const node = { tag, textContent: "", style: { cssText: "" }, setAttribute: jest.fn(), append: jest.fn(), onclick: undefined as undefined | (() => void), disabled: false };
    nodes.push(node); return node;
  });
  const target = { opener: {}, document: { open: jest.fn(), write: jest.fn(), close: jest.fn(), createElement, body: { prepend: jest.fn() }, head: { append: jest.fn() } }, focus: jest.fn(), print: jest.fn(), close: jest.fn() };
  const browser = { open: jest.fn(() => target as unknown as Window) };
  return { target, browser, nodes, createElement };
}
afterEach(() => jest.restoreAllMocks());
it("prints only the identical validated report HTML and preserves every source statement and measurement", () => {
  const f = setup(); const html = buildLocalAiReportHtml(snapshot, selection);
  openBrowserReport(html, () => true, f.browser);
  expect(f.target.document.write).toHaveBeenCalledWith(html);
  for (const statement of snapshot.statements) expect(html).toContain(escapeHtml(statement));
  expect(html).toContain("Reading accuracy"); expect(html).toContain("Words per minute");
  expect(f.target.opener).toBeNull();
  const print = f.createElement.mock.results.find(r => r.value.tag === "button")!.value;
  expect(print.textContent).toBe("Print / Save as PDF");
  expect(f.target.print).not.toHaveBeenCalled();
  print.onclick!(); expect(f.target.print).toHaveBeenCalledTimes(1);
  expect(f.createElement.mock.results.find(r => r.value.tag === "style")!.value.textContent).toContain("@media print");
});
it("reports blocked popups and sanitizes document creation failures", () => {
  expect(() => openBrowserReport("report", () => true, { open: () => null })).toThrow(BrowserReportError);
  const f = setup(); f.target.document.write.mockImplementation(() => { throw new Error("PRIVATE"); });
  expect(() => openBrowserReport("report", () => true, f.browser)).toThrow("Browser report printing is unavailable.");
  expect(f.target.close).toHaveBeenCalled();
});
it("reports printing failures in the dedicated report window without claiming a saved PDF", () => {
  const f = setup(); openBrowserReport("report", () => true, f.browser);
  f.target.print.mockImplementation(() => { throw new Error("PRIVATE"); });
  f.createElement.mock.results.find(r => r.value.tag === "button")!.value.onclick!();
  const status = f.createElement.mock.results.find(r => r.value.tag === "p")!.value;
  expect(status.textContent).toContain("Printing could not open");
  expect(status.textContent).not.toContain("PRIVATE");
  expect(status.setAttribute).toHaveBeenCalledWith("role", "alert");
});
it("blocks stale selections before opening and before later printing", () => {
  const f = setup(); let current = false;
  expect(() => openBrowserReport("report", () => current, f.browser)).toThrow(BrowserReportError);
  expect(f.browser.open).not.toHaveBeenCalled();
  current = true; openBrowserReport("report", () => current, f.browser); current = false;
  const print = f.createElement.mock.results.find(r => r.value.tag === "button")!.value;
  print.onclick!(); expect(f.target.print).not.toHaveBeenCalled(); expect(print.disabled).toBe(true);
});
it("routes web exports to the browser without native APIs and rejects invalid snapshots first", async () => {
  const browser = jest.spyOn(browserPdf, "openBrowserReport").mockImplementation(() => {});
  const native = { isAvailableAsync: jest.fn(), printToFileAsync: jest.fn(), shareAsync: jest.fn() };
  await exportLocalAiPdf({ snapshot, selection, platform: "web", modules: native });
  expect(browser).toHaveBeenCalledWith(buildLocalAiReportHtml(snapshot, selection), expect.any(Function));
  expect(native.printToFileAsync).not.toHaveBeenCalled(); expect(native.shareAsync).not.toHaveBeenCalled();
  browser.mockClear();
  await expect(exportLocalAiPdf({ snapshot: { ...snapshot, validated: false }, selection, platform: "web" })).rejects.toMatchObject({ reason: "unavailable" });
  await expect(exportLocalAiPdf({ snapshot, selection: { ...selection, role: "guardian" }, platform: "web" })).rejects.toMatchObject({ reason: "unavailable" });
  await expect(exportLocalAiPdf({ snapshot, selection: { ...selection, demoMode: false }, platform: "web" })).rejects.toMatchObject({ reason: "unavailable" });
  expect(browser).not.toHaveBeenCalled();
});
