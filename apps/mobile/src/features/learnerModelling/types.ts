export type PreviewRole = "learner" | "guardian" | "educator";
export type ReportingPeriodDays = 7 | 30 | 90;
export type DashboardDataProvenance = "demo" | "live_unavailable";
export type MetricKey = "reading_accuracy" | "reading_fluency_wpm" | "hesitation_rate_per_word";
export type ChangeDirection =
  | "increased"
  | "decreased"
  | "no_observed_change"
  | "insufficient_evidence";

export interface MetricPreview {
  key: MetricKey;
  label: string;
  unit: string;
  firstValue: number;
  latestValue: number;
  changeDirection: ChangeDirection;
  evidenceLabel: string;
  validObservationCount?: number;
  missingObservationCount?: number;
  explanation: string;
  detail?: string;
}

export interface DifficultyPreview {
  observedAt: string;
  tier: "beginner" | "intermediate" | "advanced";
  context: string;
  explanation: string;
}

export interface RecommendationPreview {
  action: "maintain" | "adjust_support" | "adjust_difficulty";
  currentTier: "beginner" | "intermediate" | "advanced";
  recommendedTier: "beginner" | "intermediate" | "advanced";
  supportSuggestion: string;
  reasonCodes: readonly string[];
  explanation: string;
}

export interface DashboardPreview {
  role: PreviewRole;
  title: string;
  subtitle: string;
  reportingStartUtc: string;
  reportingEndUtc: string;
  includedSessionCount: number;
  contextSummary: string;
  metrics: readonly MetricPreview[];
  difficultyProgression: readonly DifficultyPreview[];
  recommendation: RecommendationPreview;
  limitations: readonly string[];
  disclaimer: string;
}

// Mobile presentation models only. They are deliberately not authoritative API schemas.
export type LearnerDashboardPreview = DashboardPreview & { role: "learner" };
export type GuardianDashboardPreview = DashboardPreview & { role: "guardian" };
export type EducatorDashboardPreview = DashboardPreview & { role: "educator" };

export type DashboardPresentationStatus =
  | "loading"
  | "empty"
  | "consent_required"
  | "learner_unavailable"
  | "temporarily_unavailable"
  | "reporting_limit_exceeded";

export type DashboardPresentationState<TDashboard extends DashboardPreview> =
  | { status: "ready"; provenance: DashboardDataProvenance; dashboard: TDashboard }
  | { status: DashboardPresentationStatus; provenance: DashboardDataProvenance };
