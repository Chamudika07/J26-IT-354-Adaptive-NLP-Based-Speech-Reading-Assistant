import { buildSyntheticDashboard } from "../preview/syntheticData";
import type {
  EducatorDashboardPreview,
  DashboardDataProvenance,
  GuardianDashboardPreview,
  LearnerDashboardPreview,
  ReportingPeriodDays,
} from "../types";

export type DashboardProviderMode = DashboardDataProvenance;
export type DashboardProviderFailure =
  | "consent_required"
  | "learner_unavailable"
  | "temporarily_unavailable"
  | "reporting_limit_exceeded";

/**
 * A role-separated mobile presentation boundary. It intentionally contains no
 * authorization action, access path, consent result, learner identifier, or API schema.
 */
export interface Component4DashboardProvider {
  readonly mode: DashboardProviderMode;
  loadLearnerProgress(periodDays: ReportingPeriodDays): Promise<LearnerDashboardPreview>;
  loadGuardianSummary(periodDays: ReportingPeriodDays): Promise<GuardianDashboardPreview>;
  loadEducatorAnalytics(periodDays: ReportingPeriodDays): Promise<EducatorDashboardPreview>;
}

export class DashboardProviderError extends Error {
  constructor(readonly failure: DashboardProviderFailure) {
    super("The requested educational report is unavailable.");
    this.name = "DashboardProviderError";
  }
}

export const demoDashboardProvider: Component4DashboardProvider = Object.freeze({
  mode: "demo",
  loadLearnerProgress: async (periodDays: ReportingPeriodDays) =>
    buildSyntheticDashboard("learner", periodDays),
  loadGuardianSummary: async (periodDays: ReportingPeriodDays) =>
    buildSyntheticDashboard("guardian", periodDays),
  loadEducatorAnalytics: async (periodDays: ReportingPeriodDays) =>
    buildSyntheticDashboard("educator", periodDays),
});

function liveIntegrationUnavailable(): Promise<never> {
  return Promise.reject(new DashboardProviderError("temporarily_unavailable"));
}

/**
 * Safe placeholder for future generated-client integration. It cannot perform a request
 * and never falls back to demo data. Authentication, approved endpoints, consent policy,
 * and generated API types must exist before this provider can be replaced.
 */
export const unavailableLiveDashboardProvider: Component4DashboardProvider = Object.freeze({
  mode: "live_unavailable",
  loadLearnerProgress: liveIntegrationUnavailable,
  loadGuardianSummary: liveIntegrationUnavailable,
  loadEducatorAnalytics: liveIntegrationUnavailable,
});
