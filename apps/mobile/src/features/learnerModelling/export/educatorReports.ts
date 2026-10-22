import { selectRoleScenario, type EducatorArtifact } from "../preview/roleScenarioResults";
import * as NativeFiles from "expo-file-system/legacy";
import { selectEducatorStudent } from "../preview/educatorStudents";
import type { PreviewRole } from "../types";
import { escapeHtml as e, installedPdfModules, ReportPdfError, type ExpoPdfModules } from "./localAiPdf";

export const educatorStudentNames = ["Alex Storybook", "Robin Page", "Jamie Bookmark"] as const;
export type EducatorProjection = EducatorArtifact["projection"];
export interface EducatorReportSelection {
  development: boolean;
  demoMode: boolean;
  role: PreviewRole;
  scenarioId: string | null;
  student: number | null; // null = class; never a real learner identifier
}
export const educatorMetrics = [
  { key: "reading_accuracy", label: "Reading Accuracy", unit: "%", scale: 100 },
  { key: "reading_fluency_wpm", label: "Reading Speed", unit: "WPM", scale: 1 },
  { key: "hesitation_rate_per_word", label: "Hesitation Frequency", unit: "per 100 attempted words", scale: 100 },
] as const;
export const educatorValue = (v: string | null | undefined, scale: number) => v == null ? "Not measured" : String(Number((Number(v) * scale).toFixed(2)));

/** Resolve only pinned, separately validated Educator projections. No caller-supplied evidence. */
export function educatorReportStudents(selection: EducatorReportSelection) {
  if (!__DEV__ || !selection.development || !selection.demoMode || selection.role !== "educator") throw new ReportPdfError("unavailable");
  if (selection.student !== null && (!Number.isInteger(selection.student) || selection.student < 0 || selection.student > 2)) throw new ReportPdfError("unavailable");
  return educatorStudentNames.map((name, index) => ({ name, index,
    projection: index === 0 ? selection.scenarioId ? selectRoleScenario("educator", selection.scenarioId)?.projection ?? null : null : selectEducatorStudent(index - 1),
  }));
}
export function educatorHasTrend(p: EducatorProjection) {
  return p.partitions.some(c => c.metrics.some(m => m.evidence_sufficient && m.change_direction !== "insufficient_evidence"));
}
export function educatorHasMissing(p: EducatorProjection) {
  return p.partitions.length === 0 || p.partitions.some(c => c.metrics.some(m => m.missing_observation_count > 0 || m.latest_value === null));
}
/** Descriptive counts only. No pooled performance averages or adaptation rules. */
export function educatorClassOverview(students: ReturnType<typeof educatorReportStudents>) {
  return { students: students.length,
    sessions: students.reduce((sum, s) => sum + (s.projection?.included_session_count ?? 0), 0),
    trends: students.filter(s => s.projection && educatorHasTrend(s.projection)).length,
    missing: students.filter(s => s.projection && educatorHasMissing(s.projection)).length,
    unavailable: students.filter(s => !s.projection).length,
  };
}
export function educatorFactualSummary(p: EducatorProjection): string {
  return `${p.included_session_count} completed sessions in this reporting period. ${educatorHasTrend(p) ? "Comparable progress results are available for some measurements." : "Not enough reading sessions to show a reliable trend yet."}`;
}
export const educatorReportDate = (date: Date) => date.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
/** Human-readable inclusive days only when the half-open interval covers whole UTC days. */
export function educatorReportingPeriod(start: string, end: string): string {
  const first = new Date(start), exclusive = new Date(end);
  const midnight = (d: Date) => d.getUTCHours() === 0 && d.getUTCMinutes() === 0 && d.getUTCSeconds() === 0 && d.getUTCMilliseconds() === 0;
  if (!Number.isFinite(first.getTime()) || !Number.isFinite(exclusive.getTime()) || first >= exclusive) throw new ReportPdfError("unavailable");
  if (!midnight(first) || !midnight(exclusive)) {
    const exact = (d: Date) => `${educatorReportDate(d)}, ${d.toISOString().slice(11, 23)} UTC`;
    return `${exact(first)} to before ${exact(exclusive)}`;
  }
  const last = new Date(exclusive.getTime() - 1);
  if (first.toISOString().slice(0, 10) === last.toISOString().slice(0, 10)) return educatorReportDate(first);
  const sameYear = first.getUTCFullYear() === last.getUTCFullYear();
  if (sameYear && first.getUTCMonth() === last.getUTCMonth()) return `${first.getUTCDate()}\u2013${educatorReportDate(last)}`;
  const left = sameYear ? first.toLocaleDateString("en-GB", { day: "numeric", month: "long", timeZone: "UTC" }) : educatorReportDate(first);
  return `${left}\u2013${educatorReportDate(last)}`;
}
const period = (p: EducatorProjection) => educatorReportingPeriod(p.reporting_period.start_at_utc, p.reporting_period.end_at_utc);
const support = (v: string) => v === "adaptive" ? "Adaptive support" : v === "baseline_fixed" ? "Fixed support" : v === "manual_override" ? "Manually chosen support" : "Recorded support";
const metricDisplay = (v: string | null | undefined, d: typeof educatorMetrics[number]) => v == null ? "Not measured" : `${educatorValue(v, d.scale)}${d.unit === "%" ? "" : " "}${d.unit}`;

function studentHtml(student: ReturnType<typeof educatorReportStudents>[number]): string {
  const p = student.projection;
  if (!p) return `<section class="student"><div class="student-intro"><h2>${e(student.name)}</h2><p>Reading results unavailable. This student is excluded from the available session total.</p></div></section>`;
  return `<section class="student"><div class="student-intro"><h2>${e(student.name)}</h2><p><strong>Reporting period:</strong> ${e(period(p))}</p><p>${p.included_session_count} completed sessions in this reporting period.</p></div>
    ${p.partitions.length === 0 ? "<p>No reading measurements available. Not enough reading sessions to show a reliable trend yet.</p>" : p.partitions.map(c => {
      const insufficient = c.metrics.filter(m => !m.evidence_sufficient || m.change_direction === "insufficient_evidence");
      return `<div class="measurements"><h3>${e(c.task_type.replaceAll("_", " "))} \u00b7 ${e(c.difficulty_tier)} \u00b7 ${e(support(c.support_mode))}</h3>
      <p>${c.session_count} completed sessions in this reading context.</p>
      <table><thead><tr><th>Measurement</th><th>First</th><th>Latest</th></tr></thead><tbody>${educatorMetrics.map(d => {
        const m = c.metrics.find(m => m.metric_name === d.key);
        return `<tr><th>${d.label}${m?.first_value == null && m?.latest_value == null ? `<small>${d.unit}</small>` : ""}</th><td>${e(metricDisplay(m?.first_value, d))}</td><td>${e(metricDisplay(m?.latest_value, d))}<small>${m?.valid_observation_count ?? 0} measured; ${m?.missing_observation_count ?? 0} unavailable</small></td></tr>`;
      }).join("")}</tbody></table></div>
      <div class="progress"><h3>Progress Summary</h3>${insufficient.length ? `<p>${insufficient.length === c.metrics.length ? "Not enough reading sessions to show a reliable trend yet." : `Not enough comparable sessions for: ${insufficient.map(m => educatorMetrics.find(d => d.key === m.metric_name)!.label).join(", ")}.`}</p>` : ""}${c.metrics.filter(m => m.evidence_sufficient && m.change_direction !== "insufficient_evidence").map(m => {
        const d = educatorMetrics.find(d => d.key === m.metric_name)!;
        const trend = `${d.label} ${m.change_direction === "increased" ? "increased" : m.change_direction === "decreased" ? "decreased" : "showed no measured change"} between comparison periods.`;
        return `<p class="trend">${e(trend)}<small>Earlier average: ${e(metricDisplay(m.early_window_mean, d))}; recent average: ${e(metricDisplay(m.late_window_mean, d))}.</small></p>`;
      }).join("")}${c.metrics.some(m => m.missing_observation_count > 0 || m.latest_value === null) ? '<p class="note">Unavailable measurements are not zero and are excluded from metric comparisons.</p>' : ""}</div>`;
    }).join("")}
    <div class="support-history"><h3>Reading Support History</h3>${p.support_mode_exposures.length === 0 ? "<p>No recorded support use.</p>" : p.support_mode_exposures.map(s => `<p>${e(support(s.support_mode))}: ${s.session_count} sessions, ${e(educatorReportDate(new Date(s.first_observed_at)))} to ${e(educatorReportDate(new Date(s.latest_observed_at)))}.<br><small>Active reading: ${s.active_duration_ms / 1000} seconds; total session time: ${s.total_duration_ms / 1000} seconds.</small></p>`).join("")}</div></section>`;
}

export function buildEducatorReport(selection: EducatorReportSelection, generatedAt = new Date()) {
  const students = educatorReportStudents(selection);
  if (!Number.isFinite(generatedAt.getTime())) throw new ReportPdfError("unavailable");
  const selected = selection.student === null ? students : [students[selection.student]!];
  if (selection.student !== null && !selected[0]!.projection) throw new ReportPdfError("unavailable");
  const totals = educatorClassOverview(students);
  const title = selection.student === null ? "Whole Class Analytics Report" : "Individual Student Analytics Report";
  const filename = `ReadBuddy-${selection.student === null ? "Class-Analytics" : selected[0]!.name.replaceAll(" ", "-") + "-Analytics"}-${generatedAt.toISOString().slice(0, 10)}.pdf`;
  const html = `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>ReadBuddy — ${title}</title><style>
    @page{size:A4;margin:14mm}
    *{box-sizing:border-box}body{font:11pt Arial,sans-serif;color:#183149;line-height:1.3;margin:0}
    header{background:#edf6ff;border-top:4px solid #0865c5;padding:10px 12px;border-radius:10px}
    h1{font-size:20pt;line-height:1.15;margin:4px 0}h2{font-size:16pt;color:#164f80;margin:12px 0 5px}h3{font-size:11.5pt;color:#164f80;margin:9px 0 4px}
    h2,h3{break-after:avoid;page-break-after:avoid}p{orphans:2;widows:2;margin:5px 0}
    table{border-collapse:collapse;width:100%;table-layout:fixed}th,td{text-align:left;padding:7px 6px;border-bottom:1px solid #cbdce9;vertical-align:top;overflow-wrap:anywhere}th:first-child{width:28%}thead{display:table-header-group;background:#edf6ff}
    tr,header,.student-intro,.measurements,.progress,.support-history,.report-notes{break-inside:avoid;page-break-inside:avoid}
    .student{break-inside:auto;page-break-inside:auto}.student+.student{border-top:1px solid #cbdce9;margin-top:12px;padding-top:4px}
    small,.note,.metadata{font-size:10pt}small{display:block;margin-top:2px}.badge{font-size:10pt;color:#19563b}.metadata{margin-top:5px}.report-notes{margin-top:10px;border-top:1px solid #cbdce9;padding-top:6px}
    </style></head><body><header><strong>ReadBuddy</strong><h1>${title}</h1><span class="badge">Sample Data</span><p class="metadata">Report generated: ${e(educatorReportDate(generatedAt))} (UTC)</p></header>
    ${selection.student === null ? `<h2>Class Overview</h2><p>${totals.students} fictional students · ${totals.sessions} completed sessions in available records · ${totals.trends} students with at least one supported trend · ${totals.missing} students with missing measurements · ${totals.unavailable} students with unavailable results.</p><p>Counts describe the available student records in each period below. ${totals.unavailable ? "Session totals are incomplete because some results are unavailable." : "All three student records are available."} Performance is shown separately for each student and reading context; no class averages or cross-student trend comparisons are calculated.</p>` : ""}
    ${selected.map(studentHtml).join("")}<div class="report-notes"><p class="note">Fictional students, not real learner records or a real class roster. Factual summary; not AI-generated.</p><p class="note">Results are descriptive: they do not establish causes or assess health or ability. Support history shows recorded modes, not exact settings or recommended changes. No settings are changed.</p></div></body></html>`;
  return { html, filename };
}

export interface EducatorPdfFiles {
  cacheDirectory: string | null;
  copyAsync(options: { from: string; to: string }): Promise<void>;
  deleteAsync(uri: string, options: { idempotent: boolean }): Promise<void>;
}
export async function exportEducatorReport({ selection, platform, modules = installedPdfModules(), files, isCurrent = () => true }: {
  selection: EducatorReportSelection; platform: string; modules?: ExpoPdfModules | null; files?: EducatorPdfFiles; isCurrent?: () => boolean;
}) {
  const report = buildEducatorReport(selection);
  if (platform !== "ios" && platform !== "android") throw new ReportPdfError("platform");
  if (!modules) throw new ReportPdfError("dependencies");
  const current = () => { if (!isCurrent()) throw new ReportPdfError("cancelled"); };
  let original: string | undefined;
  let named: string | undefined;
  let storage: EducatorPdfFiles | undefined;
  let shared = false;
  try {
    current();
    if (!await modules.isAvailableAsync()) throw new ReportPdfError("sharing");
    current();
    storage = files ?? NativeFiles;
    if (!storage.cacheDirectory || !/^file:\/\/\/[^\r\n]+\/$/.test(storage.cacheDirectory)) throw new ReportPdfError("generation");
    const file = await modules.printToFileAsync({ html: report.html, base64: false, width: 595, height: 842 });
    if (!/^file:\/\/\/[^\r\n]+\.pdf$/i.test(file.uri)) throw new ReportPdfError("generation");
    original = file.uri;
    current();
    // Unique copies avoid replacing a file another native share target is still reading.
    named = `${storage.cacheDirectory}${report.filename.replace(/\.pdf$/, `-${Date.now()}.pdf`)}`;
    await storage.copyAsync({ from: original, to: named });
    current();
    await modules.shareAsync(named, { mimeType: "application/pdf", UTI: "com.adobe.pdf", dialogTitle: "Save ReadBuddy analytics report" });
    shared = true;
  } catch (error) {
    if (error instanceof ReportPdfError) throw error;
    throw new ReportPdfError("generation");
  } finally {
    // Share targets may read after the chooser closes, especially on Android.
    // Keep successfully shared copies in device cache (OS-managed), not permanent storage.
    if (storage) for (const uri of new Set([original, shared ? undefined : named])) if (uri) {
      try { await storage.deleteAsync(uri, { idempotent: true }); } catch { /* Cache cleanup is best effort. */ }
    }
  }
}
