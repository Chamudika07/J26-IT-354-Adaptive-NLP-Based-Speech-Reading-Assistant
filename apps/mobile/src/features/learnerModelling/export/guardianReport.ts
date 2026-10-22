import * as Files from "expo-file-system/legacy";
import { escapeHtml as e, installedPdfModules, ReportPdfError, type ExpoPdfModules } from "./localAiPdf";
export interface GuardianReportData {
  source: string; learnerName?: string; start: string; end: string; completed: number; status: string;
  latest: { label: string; value: string; unit: string }[];
  contexts: { label: string; sessions: number; metrics: { label: string; unit: string; first: string; latest: string; comparable: boolean; trend: string | null; explanation: string }[] }[];
  support: string[]; notes: string[];
}
const date = (value: string) => new Date(value).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
const sessionText = (n: number) => `${n} ${n === 1 ? "session" : "sessions"}`;
export function buildGuardianReport(data: GuardianReportData, now = new Date()) {
  if (!__DEV__ || !Number.isFinite(Date.parse(data.start)) || !Number.isFinite(Date.parse(data.end)) || !Number.isFinite(now.getTime())) throw new ReportPdfError("unavailable");
  const measurement = (value: string, unit: string) => value === "Unavailable" ? value : `${value}${unit === "%" ? "" : " "}${unit}`;
  const html = `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>ReadBuddy Progress Report</title><style>
    @page{size:A4;margin:14mm}body{font:11pt Arial,sans-serif;color:#183149;line-height:1.35;margin:0}header{background:#edf6ff;border-top:4px solid #0865c5;padding:12px;border-radius:10px}h1{font-size:21pt;margin:5px 0}h2{font-size:15pt;color:#164f80;margin:14px 0 6px}h3{font-size:12pt;margin:8px 0}h2,h3{break-after:avoid}p{margin:5px 0;orphans:2;widows:2}table{border-collapse:collapse;width:100%}th,td{padding:7px;text-align:left;border-bottom:1px solid #cbdce9;vertical-align:top}thead{display:table-header-group}tr,header{break-inside:avoid}small{font-size:10pt}section{margin-bottom:10px}
    </style></head><body><header><strong>ReadBuddy</strong><h1>Progress Report</h1><p>Fictional Demonstration Data</p><small>Generated: ${e(date(now.toISOString()))} (UTC)</small></header>
    <p><strong>Learner:</strong> ${e(data.learnerName ?? "Name unavailable")}</p><p>${e(data.source)}</p>
    <p><strong>Reporting period:</strong> ${e(date(data.start))} to ${e(date(data.end))} (end not included)</p>
    <h2>Current Reading Results</h2><p>${sessionText(data.completed)} completed</p><table><tbody>${data.latest.map(m => `<tr><th>${e(m.label)}</th><td>${e(measurement(m.value, m.unit))}</td></tr>`).join("")}</tbody></table>
    <h2>Progress Summary</h2><p>${e(data.status)}</p>
    ${data.contexts.map(c => `<section><h3>${e(c.label)}</h3><p>${sessionText(c.sessions)}</p>${c.metrics.some(m => m.comparable) ? `<table><thead><tr><th>Measurement</th><th>First</th><th>Latest</th></tr></thead><tbody>${c.metrics.filter(m => m.comparable).map(m => `<tr><th>${e(m.label)}</th><td>${e(measurement(m.first, m.unit))}</td><td>${e(measurement(m.latest, m.unit))}</td></tr>`).join("")}</tbody></table>` : ""}${c.metrics.map(m => `<p><strong>${e(m.label)}:</strong> ${m.trend ? `${e(m.trend)}. ` : ""}${e(m.explanation)}</p>`).join("")}</section>`).join("")}
    <h2>Support Used During Reading</h2>${data.support.length ? data.support.map(s => `<p>${e(s)}</p>`).join("") : "<p>Support history: Unavailable</p>"}<p>Observed support, not a recommendation.</p>
    <h2>About These Results</h2>${[...new Set(data.notes)].map(s => `<p>${e(s)}</p>`).join("")}<p><small>Factual progress summary; not AI-generated.</small></p></body></html>`;
  return { html, filename: `ReadBuddy-Parent-Progress-${now.toISOString().slice(0, 10)}.pdf` };
}
export async function exportGuardianReport({ data, platform, modules = installedPdfModules(), files = Files, isCurrent = () => true }: {
  data: GuardianReportData; platform: string; modules?: ExpoPdfModules | null; files?: Pick<typeof Files, "cacheDirectory" | "copyAsync" | "deleteAsync">; isCurrent?: () => boolean;
}) {
  const report = buildGuardianReport(data);
  if (platform !== "ios" && platform !== "android") throw new ReportPdfError("platform");
  if (!modules) throw new ReportPdfError("dependencies");
  const current = () => { if (!isCurrent()) throw new ReportPdfError("cancelled"); };
  let original: string | undefined; let named: string | undefined; let shared = false;
  try {
    current(); if (!await modules.isAvailableAsync()) throw new ReportPdfError("sharing"); current();
    if (!files.cacheDirectory || !/^file:\/\/\/[^\r\n]+\/$/.test(files.cacheDirectory)) throw new ReportPdfError("generation");
    const result = await modules.printToFileAsync({ html: report.html, base64: false, width: 595, height: 842 });
    if (!/^file:\/\/\/[^\r\n]+\.pdf$/i.test(result.uri)) throw new ReportPdfError("generation");
    original = result.uri; current(); named = `${files.cacheDirectory}${report.filename.replace(/\.pdf$/, `-${Date.now()}.pdf`)}`;
    await files.copyAsync({ from: original, to: named }); current();
    await modules.shareAsync(named, { mimeType: "application/pdf", UTI: "com.adobe.pdf", dialogTitle: "Save ReadBuddy progress report" }); shared = true;
  } catch (error) { if (error instanceof ReportPdfError) throw error; throw new ReportPdfError("generation"); }
  finally { for (const uri of new Set([original, shared ? undefined : named])) if (uri) { try { await files.deleteAsync(uri, { idempotent: true }); } catch { /* Cache cleanup is best effort. */ } } }
}
