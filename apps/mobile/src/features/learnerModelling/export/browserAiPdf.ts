/** Local browser printing only. No requests, model calls or native PDF APIs. */
export class BrowserReportError extends Error {
  constructor(readonly reason: "popup" | "printing" | "cancelled") {
    super("Browser report printing is unavailable.");
  }
}
export interface ReportBrowser {
  open(): Window | null;
}
export function openBrowserReport(html: string, isCurrent = () => true, browser: ReportBrowser = {
  open: () => typeof window === "undefined" ? null : window.open("", "_blank"),
}): void {
  if (!isCurrent()) throw new BrowserReportError("cancelled");
  let target: Window | null = null;
  try {
    // Open synchronously from the user's click, before awaiting anything.
    target = browser.open();
    if (!target) throw new BrowserReportError("popup");
    target.opener = null;
    if (!isCurrent()) throw new BrowserReportError("cancelled");
    const reportWindow = target;
    const doc = reportWindow.document;
    doc.open(); doc.write(html); doc.close();
    const controls = doc.createElement("aside");
    controls.className = "browser-print-controls";
    const print = doc.createElement("button");
    print.type = "button"; print.textContent = "Print / Save as PDF";
    print.style.cssText = "min-height:44px;padding:12px 18px;background:#1D4ED8;color:white;border:0;border-radius:12px;font-size:16px;cursor:pointer";
    const status = doc.createElement("p");
    status.setAttribute("role", "status");
    status.textContent = 'Choose "Save as PDF" in your browser print dialog. Saving is not confirmed by ReadBuddy.';
    print.onclick = () => {
      try {
        if (!isCurrent()) { print.disabled = true; status.textContent = "Report selection changed. Close this window and open the report again."; return; }
        reportWindow.focus(); reportWindow.print();
      } catch {
        status.setAttribute("role", "alert");
        status.textContent = "Printing could not open. Try your browser Print menu and select Save as PDF.";
      }
    };
    controls.append(print, status);
    doc.body.prepend(controls);
    const style = doc.createElement("style");
    style.textContent = ".browser-print-controls{padding:12px;margin-bottom:16px;background:#EEF5FF}@media print{.browser-print-controls{display:none!important}}";
    doc.head.append(style);
  } catch (error) {
    try { target?.close(); } catch { /* Sanitized failure below. */ }
    if (error instanceof BrowserReportError) throw error;
    throw new BrowserReportError("printing");
  }
}
