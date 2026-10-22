import type { PreviewRole, ChangeDirection } from "../types";
import { Component4ApiError, createComponent4Client, type EducatorProjection, type GuardianProjection, type LearnerProjection, type MetricWire, type LiveConnection, type ReportingWindow } from "./component4Client";

export interface LiveMetric {
  name: MetricWire["metric_name"]; label: string; unit: string;
  firstValue: number | null; latestValue: number | null;
  direction: ChangeDirection; explanation: string;
  validCount?: number; missingCount?: number;
}
export interface LiveDashboard {
  role: PreviewRole; period: ReportingWindow; sessionCount: number;
  contexts: { label: string; metrics: LiveMetric[] }[];
  supportHistory: string[]; difficultyHistory: string[]; limitations: string[]; disclaimer: string;
}
const metricInfo = {
  reading_accuracy: { unit: "proportion", label: "Reading Accuracy", display: "%", scale: 100 },
  reading_fluency_wpm: { unit: "words_per_minute", label: "Reading Speed", display: "WPM", scale: 1 },
  hesitation_rate_per_word: { unit: "hesitations_per_attempted_word", label: "Hesitation Frequency", display: "per 100 attempted words", scale: 100 },
} as const;
const taskLabels: Record<string, string> = { independent_reading: "Independent reading", assisted_read_aloud: "Assisted read-aloud", guided_echo_reading: "Guided echo reading" };
const difficultyLabels: Record<string, string> = { early: "Early level", intermediate: "Intermediate level", advanced: "Advanced level" };
const supportLabels: Record<string, string> = { baseline_fixed: "Fixed support", adaptive: "Adaptive support", manual_override: "Manually selected support" };
function metrics(values: MetricWire[]): LiveMetric[] {
  if (new Set(values.map(v => v.metric_name)).size !== 3) throw new Component4ApiError("invalid_response");
  return values.map(value => {
    const info = metricInfo[value.metric_name];
    if (value.unit !== info.unit) throw new Component4ApiError("invalid_response");
    const convert = (number: number | string | null) => {
      if (number === null) return null;
      const n = Number(number) * info.scale;
      if (!Number.isFinite(n) || n < 0) throw new Component4ApiError("invalid_response");
      return n;
    };
    return { name: value.metric_name, label: info.label, unit: info.display,
      firstValue: convert(value.first_value), latestValue: convert(value.latest_value),
      direction: value.change_direction, explanation: value.explanation ?? value.educational_interpretation ?? "",
      validCount: value.valid_observation_count, missingCount: value.missing_observation_count };
  });
}
export function mapLearnerProjection(value: LearnerProjection): LiveDashboard {
  return { role: "learner", period: value.reporting_period, sessionCount: value.included_session_count,
    contexts: value.contexts.map(c => ({ label: `${c.task_label} · ${c.difficulty_label} · ${c.support_label}`, metrics: metrics(c.metrics) })),
    supportHistory: value.support_observations.map(s => s.description), difficultyHistory: value.difficulty_observations.map(d => d.description),
    limitations: [value.evidence_message], disclaimer: value.disclaimer };
}
export function mapGuardianProjection(value: GuardianProjection): LiveDashboard {
  return { role: "guardian", period: value.reporting_period, sessionCount: value.included_session_count,
    contexts: value.contexts.map(c => ({ label: `${c.task_label} · ${c.difficulty_label} · ${c.support_label}`, metrics: metrics(c.metrics) })),
    supportHistory: value.support_exposures.map(s => s.description), difficultyHistory: value.difficulty_history.map(d => d.description),
    limitations: value.evidence_limitations, disclaimer: value.disclaimer };
}
export function mapEducatorProjection(value: EducatorProjection): LiveDashboard {
  return { role: "educator", period: value.reporting_period, sessionCount: value.included_session_count,
    contexts: value.partitions.map(c => ({ label: `${taskLabels[c.task_type!]} · ${difficultyLabels[c.difficulty_tier!]} · ${supportLabels[c.support_mode!]}`, metrics: metrics(c.metrics) })),
    supportHistory: value.support_mode_exposures.map(s => `${supportLabels[s.support_mode]}: ${s.session_count} recorded sessions; ${s.active_duration_ms / 1000} active seconds, ${s.total_duration_ms / 1000} total seconds.`),
    difficultyHistory: value.difficulty_timeline.map(d => `${difficultyLabels[d.difficulty_tier]} — ${new Date(d.observed_at).toLocaleDateString("en-GB", { timeZone: "UTC" })}`),
    limitations: value.limitations, disclaimer: value.disclaimer };
}
export function createLiveDashboardProvider(connection: LiveConnection, transport?: typeof fetch) {
  const client = createComponent4Client(connection, transport);
  return {
    mode: "live" as const,
    async load(role: PreviewRole, window: ReportingWindow, signal?: AbortSignal): Promise<LiveDashboard> {
      if (role !== connection.role) throw new Component4ApiError("forbidden");
      if (role === "learner") return mapLearnerProjection(await client.loadLearnerProgress(window, signal));
      if (role === "guardian") return mapGuardianProjection(await client.loadGuardianSummary(window, signal));
      return mapEducatorProjection(await client.loadEducatorAnalytics(window, signal));
    },
    submitReadingSession: client.submitReadingSession,
  };
}
