import { ReadingProgress } from "../components/ReadingProgress";
import type { LearnerReportProps } from "../components/LearnerReportLayout";

export function LearnerProgressHistoryScreen({ dashboard, demoMode, periodDays, onTips }: LearnerReportProps & { onTips?: () => void }) {
  const row = (position: "firstValue" | "latestValue") => ({
    label: position === "firstValue" ? "First" : "Latest",
    accuracy: dashboard.metrics.find(m => m.key === "reading_accuracy")?.[position] ?? null,
    speed: dashboard.metrics.find(m => m.key === "reading_fluency_wpm")?.[position] ?? null,
    hesitation: dashboard.metrics.find(m => m.key === "hesitation_rate_per_word")?.[position] ?? null,
  });
  return <ReadingProgress insufficientHistory={dashboard.metrics.some(m => m.changeDirection === "insufficient_evidence")} demoMode={demoMode} historyAvailable={false} rows={dashboard.metrics.length ? [row("firstValue"), row("latestValue")] : []}
    completedCount={dashboard.includedSessionCount} latest={row("latestValue")} period={`${periodDays}-day reporting period - ${dashboard.reportingStartUtc.slice(0, 10)} to ${dashboard.reportingEndUtc.slice(0, 10)} (UTC)`}
    onTips={onTips} details={[...dashboard.metrics.flatMap(m => [m.explanation, `${m.validObservationCount === undefined ? "Valid observation count unavailable." : m.validObservationCount + " valid observations"} \u00b7 ${m.missingObservationCount === undefined ? "Missing measurement count unavailable." : m.missingObservationCount + " missing measurements"}`]), ...dashboard.limitations, dashboard.disclaimer]} />;
}
