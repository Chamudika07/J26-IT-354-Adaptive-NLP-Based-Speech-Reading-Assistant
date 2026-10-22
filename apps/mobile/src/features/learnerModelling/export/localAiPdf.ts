import { printToFileAsync } from "expo-print";
import { isAvailableAsync, shareAsync } from "expo-sharing";

import { selectLocalReportSnapshot, type LocalReportSnapshot } from "../preview/localReportSnapshot";
import type { PreviewRole } from "../types";

export interface PdfSelection {
  development: boolean;
  demoMode: boolean;
  enabled: boolean;
  role: PreviewRole;
}

export class ReportPdfError extends Error {
  constructor(readonly reason: "unavailable" | "dependencies" | "platform" | "sharing" | "generation" | "cancelled") {
    super("The synthetic report PDF could not be exported.");
    this.name = "ReportPdfError";
  }
}

function selected(value: unknown, context: PdfSelection): LocalReportSnapshot {
  if (!__DEV__) throw new ReportPdfError("unavailable");
  const report = selectLocalReportSnapshot({ ...context, read: () => value });
  if (!report) throw new ReportPdfError("unavailable");
  return report;
}

export function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]!);
}

function metricRows(report: LocalReportSnapshot): string {
  const definitions = [
    { key: "reading_accuracy", name: "Reading accuracy", unit: "Correct words (%)", multiplier: 100 },
    { key: "reading_fluency_wpm", name: "Reading fluency", unit: "Words per minute", multiplier: 1 },
    { key: "hesitation_rate_per_word", name: "Hesitation frequency", unit: "Hesitations per 100 words attempted", multiplier: 100 },
  ];
  return definitions.map(({ key, name, unit, multiplier }) => {
    // Parse only text already accepted by the unchanged exact-catalogue validator.
    const statement = report.statements.find((text) => text.startsWith(`Context 1, ${key}: first `));
    const match = statement?.match(/: first ([0-9.]+), latest ([0-9.]+); unit /);
    if (!match) return "";
    const display = (value: string) => String(Number((Number(value) * multiplier).toFixed(6)));
    const insufficient = report.statements.includes(`Context 1, ${key}: insufficient comparable evidence for a trend.`);
    const explanation = report.statements.find((text) => text.startsWith(`Context 1, ${key}: `) && text !== statement);
    // Display-only prefix replacement. The explanation's factual wording is retained;
    // all full original statements are printed unchanged in the source section.
    const friendlyExplanation = explanation?.slice(`Context 1, ${key}: `.length);
    return `<tr><th scope="row">${name}<small>${unit}</small>${insufficient ? '<small class="note">Not enough comparable evidence for a trend.</small>' : ""}</th><td>${display(match[1]!)}</td><td>${display(match[2]!)}</td><td class="insight">${friendlyExplanation ? escapeHtml(friendlyExplanation.charAt(0).toUpperCase() + friendlyExplanation.slice(1)) : "Explanation unavailable."}</td></tr>`;
  }).join("");
}

/** Offline HTML only. Demo identity labels are fixed display text, never input or telemetry. */
export function buildLocalAiReportHtml(value: unknown, context: PdfSelection): string {
  const report = selected(value, context);
  const sessionStatement = report.statements.find((text) => /^The reporting period contains \d+ recorded sessions\.$/.test(text));
  const sessions = sessionStatement?.match(/contains (\d+) recorded sessions/)?.[1];
  const period = `${report.reportingStartUtc.slice(0, 10)} to ${report.reportingEndUtc.slice(0, 10)} (end exclusive, UTC)`;
  const metadata = `<p class="metadata">Source: ${escapeHtml(report.source)} | Model: ${escapeHtml(report.model)}<br>Generated on computer: ${escapeHtml(report.generatedAt.replace("T", " ").replace("+00:00", " UTC"))}</p>`;
  const disclosure = "SYNTHETIC LOCAL AI PREVIEW - NOT REAL LEARNER DATA";
  const statement = (text: string) => `<p class="statement">${escapeHtml(text)}</p>`;
  const firstStatement = report.statements[0];
  const remaining = report.statements.slice(1);
  return `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>ReadBuddy - AI Progress Report</title><style>
    @page { size: A4; margin: 16mm; }
    * { box-sizing: border-box; }
    body { font-family: Arial, Helvetica, sans-serif; color: #183149; font-size: 12pt; line-height: 1.45; margin: 0; }
    header { background: #edf6ff; border-top: 5px solid #0865c5; padding: 16px 18px; border-radius: 12px; }
    .brand { color: #0865c5; font-size: 16pt; font-weight: bold; margin: 0; letter-spacing: .3px; }
    h1 { font-size: 26pt; margin: 3px 0 5px; line-height: 1.2; }
    h2 { font-size: 16pt; color: #164f80; margin: 17px 0 7px; break-after: avoid; page-break-after: avoid; }
    p { margin: 6px 0; orphans: 3; widows: 3; }
    .tagline { margin: 0; }
    .disclosure { color: #19563b; font-size: 10pt; font-weight: bold; margin-top: 10px; }
    .advisory { font-size: 10pt; margin-bottom: 0; }
    .student { border: 1px solid #cbdce9; border-radius: 10px; padding: 10px 14px; margin: 14px 0; }
    .student h2 { margin-top: 0; }
    .student p, .metadata, .muted { font-size: 10.5pt; }
    .student dl { display: table; width: 100%; margin: 0; }
    .student dl div { display: table-cell; width: 33.33%; padding-right: 8px; }
    dt { color: #36556e; font-size: 10pt; } dd { margin: 3px 0 6px; font-weight: bold; }
    .period { font-weight: bold; }
    small { display: block; font-size: 10pt; font-weight: normal; margin-top: 3px; }
    .note { color: #684700; }
    table { width: 100%; border-collapse: collapse; margin: 8px 0; table-layout: fixed; }
    th, td { padding: 10px 8px; border-bottom: 1px solid #cbdce9; text-align: left; vertical-align: top; }
    thead { display: table-header-group; background: #edf6ff; font-size: 10.5pt; }
    .measure { width: 28%; } .value { width: 12%; } .meaning { width: 48%; }
    tbody th, td { font-size: 11pt; } .insight { font-size: 10.5pt; }
    header, .student, tr, .source-intro, .closing { break-inside: avoid; page-break-inside: avoid; }
    .source-statements { margin-top: 16px; }
    .statement { font-size: 10.5pt; margin: 7px 0; padding: 5px 0 5px 10px; border-left: 3px solid #c9e4ff; overflow-wrap: anywhere; break-inside: avoid; page-break-inside: avoid; }
    footer { border-top: 1px solid #cbdce9; margin-top: 12px; padding-top: 8px; font-size: 10pt; }
  </style></head><body>
  <header><p class="brand">ReadBuddy</p><h1>AI Progress Report</h1><p class="tagline">Reading practice, explained clearly</p>
    <p class="disclosure">${disclosure}</p>
    <p class="advisory"><strong>ADVISORY ONLY</strong> - Educational observations, not a diagnosis. No support or difficulty settings are changed.</p>
  </header>
  <section class="student" aria-label="Demo student information"><h2>Student Information</h2>
    <dl><div><dt>Student Name</dt><dd>Demo Learner</dd></div><div><dt>Student ID</dt><dd>DEMO-001</dd></div><div><dt>Data Type</dt><dd>Sample Data</dd></div></dl>
    <p>Display-only demo identifiers - not an authoritative learner identity. No identity is inferred from reading sessions.</p>
  </section>
  <p class="period">Reporting period: ${escapeHtml(period)}</p>
  <p>${sessions === undefined ? "Session count unavailable." : `${sessions} recorded synthetic sessions.`}</p>
  ${metadata}
  <p class="muted">OFFLINE SNAPSHOT - Downloading does not generate a new report. This January fixture is separate from dashboard and newly entered sample sessions.</p>
  <h2>Your reading measurements</h2>
  <table aria-label="Reading measurements and validated explanations"><thead><tr><th class="measure">Measurement</th><th class="value">First</th><th class="value">Latest</th><th class="meaning">What the measurements say</th></tr></thead><tbody>${metricRows(report)}</tbody></table>
  <p class="muted">Friendly labels and unit conversions above are display-only. They describe recorded reading, not ability. Missing measurements are not zero. Full source statements below keep their original wording and units.</p>
  <section class="source-statements" aria-label="Unchanged validated source statements">
    <div class="source-intro"><h2>Validated AI report statements</h2><p class="muted">Original source text, unchanged. Technical metric identifiers belong to these source statements; the table above provides readable labels.</p>
    ${firstStatement === undefined ? "" : statement(firstStatement)}</div>
    ${remaining.slice(0, -2).map(statement).join("")}
    <div class="closing">${remaining.slice(-2).map(statement).join("")}
      <footer><strong>ADVISORY ONLY</strong> - Sample data, not a real learner record. Saved synthetic local AI report; no additional AI content or recommendations were generated for this PDF. Production learner reports remain inactive.</footer>
    </div>
  </section>
  </body></html>`;
}

/** Public Expo Print / Sharing methods, injectable for network-free native-flow tests. */
export interface ExpoPdfModules {
  printToFileAsync(options: { html: string; base64: false; width: number; height: number }): Promise<{ uri: string }>;
  isAvailableAsync(): Promise<boolean>;
  shareAsync(uri: string, options: { mimeType: string; UTI: string; dialogTitle: string }): Promise<void>;
}

export function installedPdfModules(): ExpoPdfModules | null {
  return { printToFileAsync, isAvailableAsync, shareAsync };
}

export async function exportLocalAiPdf({ snapshot, selection, platform, modules = installedPdfModules(), isCurrent = () => true }: {
  snapshot: unknown; selection: PdfSelection; platform: string; modules?: ExpoPdfModules | null;
  isCurrent?: () => boolean;
}): Promise<void> {
  const html = buildLocalAiReportHtml(snapshot, selection);
  if (platform !== "ios" && platform !== "android") throw new ReportPdfError("platform");
  if (!modules) throw new ReportPdfError("dependencies");
  const current = () => { if (!isCurrent()) throw new ReportPdfError("cancelled"); };
  try {
    current();
    if (!await modules.isAvailableAsync()) throw new ReportPdfError("sharing");
    current();
    const file = await modules.printToFileAsync({ html, base64: false, width: 595, height: 842 });
    if (!/^file:\/\/\/[^\r\n]+\.pdf$/i.test(file.uri)) throw new ReportPdfError("generation");
    current();
    await modules.shareAsync(file.uri, { mimeType: "application/pdf", UTI: "com.adobe.pdf", dialogTitle: "Save ReadBuddy synthetic AI report" });
    // A resolved share sheet is not proof the user saved the file.
  } catch (error) {
    if (error instanceof ReportPdfError) throw error;
    throw new ReportPdfError("generation");
  }
}
