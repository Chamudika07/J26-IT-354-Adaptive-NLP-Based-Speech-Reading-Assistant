import { Text, View } from "react-native";

import { LearnerProfileView } from "../components/LearnerProfileView";
import type { LearnerReportProps } from "../components/LearnerReportLayout";

export function LearnerProfileScreen(props: LearnerReportProps & { onOpenSettings?: () => void; onAnalytics?: () => void }) {
  const { dashboard } = props;
  const latest = dashboard.difficultyProgression.reduce<typeof dashboard.difficultyProgression[number] | undefined>(
    (current, observation) => !current || Date.parse(observation.observedAt) > Date.parse(current.observedAt) ? observation : current,
    undefined,
  );
  const accuracy = dashboard.metrics.find(metric => metric.key === "reading_accuracy");
  const speed = dashboard.metrics.find(metric => metric.key === "reading_fluency_wpm");
  return <LearnerProfileView demoMode={props.demoMode} sessions={dashboard.includedSessionCount}
    accuracy={dashboard.includedSessionCount && accuracy ? `${accuracy.latestValue}%` : "Unavailable"}
    speed={dashboard.includedSessionCount && speed ? `${speed.latestValue} WPM` : "Unavailable"}
    onSettings={props.demoMode ? props.onOpenSettings : undefined} onAnalytics={props.onAnalytics}
    details={<View style={{ gap: 8 }}><Text>{props.periodDays}-day reporting period</Text><Text>{latest ? `Latest observed difficulty: ${latest.tier}` : "Observed difficulty unavailable."}</Text>{latest ? <Text>{latest.context}</Text> : null}</View>} />;
}
