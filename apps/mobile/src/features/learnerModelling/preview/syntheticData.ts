import type {
  ChangeDirection,
  DashboardPreview,
  DifficultyPreview,
  EducatorDashboardPreview,
  GuardianDashboardPreview,
  LearnerDashboardPreview,
  MetricKey,
  MetricPreview,
  PreviewRole,
  ReportingPeriodDays,
} from "../types";

const PREVIEW_END_UTC = new Date("2026-10-15T12:00:00.000Z");

const ROLE_COPY: Record<PreviewRole, Pick<DashboardPreview, "title" | "subtitle">> = {
  learner: {
    title: "My reading progress",
    subtitle: "A clear view of recent practice and the evidence available so far.",
  },
  guardian: {
    title: "Guardian progress summary",
    subtitle: "A privacy-minimized educational summary of synthetic reading practice.",
  },
  educator: {
    title: "Educator reading analytics",
    subtitle: "Detailed synthetic observations partitioned by comparable reading context.",
  },
};

interface SyntheticMetricEvidenceBase {
  key: MetricKey;
  firstValue: number;
  latestValue: number;
  validObservationCount: number;
  missingObservationCount: number;
  interpretation: string;
}

interface InsufficientSyntheticMetricEvidence extends SyntheticMetricEvidenceBase {
  changeDirection: "insufficient_evidence";
  earlyWindowCount: 0;
  lateWindowCount: 0;
  earlyWindowMean: null;
  lateWindowMean: null;
}

interface SufficientSyntheticMetricEvidence extends SyntheticMetricEvidenceBase {
  changeDirection: Exclude<ChangeDirection, "insufficient_evidence">;
  earlyWindowCount: 3;
  lateWindowCount: 3;
  earlyWindowMean: number;
  lateWindowMean: number;
}

type SyntheticMetricEvidence =
  | InsufficientSyntheticMetricEvidence
  | SufficientSyntheticMetricEvidence;

interface SyntheticPeriodEvidence {
  sessionCount: number;
  metrics: readonly SyntheticMetricEvidence[];
  difficultyProgression: readonly DifficultyPreview[];
}

const PERIOD_EVIDENCE: Record<ReportingPeriodDays, SyntheticPeriodEvidence> = {
  7: {
    sessionCount: 4,
    metrics: [
      {
        key: "reading_accuracy",
        firstValue: 84,
        latestValue: 85,
        changeDirection: "insufficient_evidence",
        validObservationCount: 4,
        missingObservationCount: 0,
        earlyWindowCount: 0,
        lateWindowCount: 0,
        earlyWindowMean: null,
        lateWindowMean: null,
        interpretation:
          "The small difference is treated as short-term fluctuation, with insufficient evidence for a trend.",
      },
      {
        key: "reading_fluency_wpm",
        firstValue: 66,
        latestValue: 64,
        changeDirection: "insufficient_evidence",
        validObservationCount: 4,
        missingObservationCount: 0,
        earlyWindowCount: 0,
        lateWindowCount: 0,
        earlyWindowMean: null,
        lateWindowMean: null,
        interpretation:
          "The values fluctuate within a narrow range, with insufficient evidence for a trend.",
      },
      {
        key: "hesitation_rate_per_word",
        firstValue: 9,
        latestValue: 8,
        changeDirection: "insufficient_evidence",
        validObservationCount: 3,
        missingObservationCount: 1,
        earlyWindowCount: 0,
        lateWindowCount: 0,
        earlyWindowMean: null,
        lateWindowMean: null,
        interpretation:
          "One measurement is missing, so the small difference is insufficient evidence for a trend.",
      },
    ],
    difficultyProgression: [
      {
        observedAt: "2026-10-09T09:00:00.000Z",
        tier: "intermediate",
        context: "Independent reading with adaptive support",
        explanation: "First observed difficulty in this seven-day synthetic reporting sequence.",
      },
      {
        observedAt: "2026-10-14T09:00:00.000Z",
        tier: "intermediate",
        context: "Independent reading with adaptive support",
        explanation: "The latest synthetic session remained at the same difficulty tier.",
      },
    ],
  },
  30: {
    sessionCount: 9,
    metrics: [
      {
        key: "reading_accuracy",
        firstValue: 74,
        latestValue: 86,
        changeDirection: "increased",
        validObservationCount: 9,
        missingObservationCount: 0,
        earlyWindowCount: 3,
        lateWindowCount: 3,
        earlyWindowMean: 76,
        lateWindowMean: 84,
        interpretation: "The available comparable observations show higher measured accuracy.",
      },
      {
        key: "reading_fluency_wpm",
        firstValue: 52,
        latestValue: 68,
        changeDirection: "increased",
        validObservationCount: 9,
        missingObservationCount: 0,
        earlyWindowCount: 3,
        lateWindowCount: 3,
        earlyWindowMean: 54,
        lateWindowMean: 66,
        interpretation: "The available comparable observations show higher measured fluency.",
      },
      {
        key: "hesitation_rate_per_word",
        firstValue: 13,
        latestValue: 8,
        changeDirection: "decreased",
        validObservationCount: 8,
        missingObservationCount: 1,
        earlyWindowCount: 3,
        lateWindowCount: 3,
        earlyWindowMean: 13,
        lateWindowMean: 8,
        interpretation:
          "The available comparable observations show lower measured hesitation frequency.",
      },
    ],
    difficultyProgression: [
      {
        observedAt: "2026-09-18T09:00:00.000Z",
        tier: "beginner",
        context: "Independent reading with adaptive support",
        explanation: "First observed difficulty in this thirty-day synthetic reporting sequence.",
      },
      {
        observedAt: "2026-10-03T09:00:00.000Z",
        tier: "intermediate",
        context: "Independent reading with adaptive support",
        explanation: "Later synthetic sessions were observed at the next difficulty tier.",
      },
    ],
  },
  90: {
    sessionCount: 15,
    metrics: [
      {
        key: "reading_accuracy",
        firstValue: 70,
        latestValue: 86,
        changeDirection: "increased",
        validObservationCount: 15,
        missingObservationCount: 0,
        earlyWindowCount: 3,
        lateWindowCount: 3,
        earlyWindowMean: 72,
        lateWindowMean: 84,
        interpretation: "The longer sequence shows higher measured accuracy with some fluctuation.",
      },
      {
        key: "reading_fluency_wpm",
        firstValue: 48,
        latestValue: 68,
        changeDirection: "increased",
        validObservationCount: 14,
        missingObservationCount: 1,
        earlyWindowCount: 3,
        lateWindowCount: 3,
        earlyWindowMean: 51,
        lateWindowMean: 66,
        interpretation: "The longer sequence shows higher measured fluency with some fluctuation.",
      },
      {
        key: "hesitation_rate_per_word",
        firstValue: 15,
        latestValue: 8,
        changeDirection: "decreased",
        validObservationCount: 13,
        missingObservationCount: 2,
        earlyWindowCount: 3,
        lateWindowCount: 3,
        earlyWindowMean: 14,
        lateWindowMean: 8,
        interpretation:
          "The longer sequence shows lower measured hesitation frequency with some fluctuation.",
      },
    ],
    difficultyProgression: [
      {
        observedAt: "2026-07-25T09:00:00.000Z",
        tier: "beginner",
        context: "Independent reading with adaptive support",
        explanation: "First observed difficulty in this ninety-day synthetic reporting sequence.",
      },
      {
        observedAt: "2026-09-01T09:00:00.000Z",
        tier: "intermediate",
        context: "Independent reading with adaptive support",
        explanation: "Later synthetic sessions were observed at the next difficulty tier.",
      },
      {
        observedAt: "2026-10-03T09:00:00.000Z",
        tier: "intermediate",
        context: "Independent reading with adaptive support",
        explanation: "The latest synthetic sessions remained at the intermediate tier.",
      },
    ],
  },
};

const METRIC_COPY: Record<MetricKey, { label: string; unit: string }> = {
  reading_accuracy: { label: "Reading accuracy", unit: "% correct" },
  reading_fluency_wpm: { label: "Reading fluency", unit: "words per minute" },
  hesitation_rate_per_word: {
    label: "Hesitation frequency",
    unit: "per 100 attempted words",
  },
};

function missingLabel(count: number): string {
  if (count === 0) {
    return "no missing measurements";
  }
  return `${count} missing measurement${count === 1 ? "" : "s"}`;
}

function metricDetail(role: PreviewRole, evidence: SyntheticMetricEvidence): string | undefined {
  if (role === "learner") {
    return undefined;
  }
  if (role === "guardian") {
    return `${evidence.validObservationCount} valid observations; ${missingLabel(evidence.missingObservationCount)}.`;
  }
  if (evidence.changeDirection === "insufficient_evidence") {
    return `Insufficient evidence; windows contain 0 and 0 comparable observations; no window averages were calculated; ${missingLabel(evidence.missingObservationCount)}; formula version v1.`;
  }
  return `Early-window mean ${evidence.earlyWindowMean}; late-window mean ${evidence.lateWindowMean}; windows contain ${evidence.earlyWindowCount} and ${evidence.lateWindowCount} comparable observations; ${missingLabel(evidence.missingObservationCount)}; formula version v1.`;
}

function metricPreview(
  role: PreviewRole,
  sessionCount: number,
  evidence: SyntheticMetricEvidence,
): MetricPreview {
  const copy = METRIC_COPY[evidence.key];
  const sufficient = evidence.changeDirection !== "insufficient_evidence";
  const sufficiency = sufficient ? "Sufficient evidence" : "Insufficient evidence";
  const explanation = sufficient
    ? `${copy.label} changed from ${evidence.firstValue} to ${evidence.latestValue}. ${evidence.interpretation}`
    : `First observed ${copy.label.toLowerCase()}: ${evidence.firstValue}; latest observed: ${evidence.latestValue}. ${evidence.interpretation}`;
  return {
    key: evidence.key,
    ...copy,
    firstValue: evidence.firstValue,
    latestValue: evidence.latestValue,
    changeDirection: evidence.changeDirection,
    validObservationCount: evidence.validObservationCount,
    missingObservationCount: evidence.missingObservationCount,
    evidenceLabel: `${sufficiency} — ${evidence.validObservationCount} of ${sessionCount} sessions measured`,
    explanation,
    detail: metricDetail(role, evidence),
  };
}

export function buildSyntheticDashboard(
  role: "learner",
  periodDays: ReportingPeriodDays,
): LearnerDashboardPreview;
export function buildSyntheticDashboard(
  role: "guardian",
  periodDays: ReportingPeriodDays,
): GuardianDashboardPreview;
export function buildSyntheticDashboard(
  role: "educator",
  periodDays: ReportingPeriodDays,
): EducatorDashboardPreview;
export function buildSyntheticDashboard(
  role: PreviewRole,
  periodDays: ReportingPeriodDays,
): DashboardPreview {
  const reportingStart = new Date(PREVIEW_END_UTC);
  reportingStart.setUTCDate(reportingStart.getUTCDate() - periodDays);
  const evidence = PERIOD_EVIDENCE[periodDays];

  return {
    role,
    ...ROLE_COPY[role],
    reportingStartUtc: reportingStart.toISOString(),
    reportingEndUtc: PREVIEW_END_UTC.toISOString(),
    includedSessionCount: evidence.sessionCount,
    contextSummary: "Independent reading · Intermediate difficulty · Adaptive support observed",
    metrics: evidence.metrics.map((metric) => metricPreview(role, evidence.sessionCount, metric)),
    difficultyProgression: evidence.difficultyProgression,
    recommendation: {
      action: periodDays === 7 ? "maintain" : "adjust_support",
      currentTier: "intermediate",
      recommendedTier: "intermediate",
      supportSuggestion:
        periodDays === 7
          ? "Keep the current difficulty and support while gathering more comparable evidence."
          : "Keep the current tier and reduce speech cues gradually during review.",
      reasonCodes:
        periodDays === 7
          ? ["insufficient_evidence", "short_term_fluctuation", "difficulty_maintained"]
          : ["accuracy_improving", "hesitation_reducing", "difficulty_maintained"],
      explanation:
        periodDays === 7
          ? "The deterministic preview rule keeps difficulty and support unchanged because four sessions are insufficient for a trend recommendation."
          : "The deterministic preview rule keeps difficulty unchanged and suggests a small support adjustment for human review.",
    },
    limitations: [
      "Results describe synthetic observations and do not establish that support caused a change.",
      "Task type, difficulty tier, and observed support mode must remain comparable.",
      "Missing measurements reduce the evidence available for interpretation.",
    ],
    disclaimer:
      "Educational analytics only. This preview does not diagnose a condition or measure clinical severity.",
  };
}
