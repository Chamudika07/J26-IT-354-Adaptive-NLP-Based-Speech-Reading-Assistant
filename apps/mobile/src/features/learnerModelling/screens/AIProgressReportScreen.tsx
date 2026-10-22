import { Text, View } from "react-native";
import { DashboardStateView } from "../components/DashboardStateView";
import { DifficultyProgression } from "../components/DifficultyProgression";
import { reportStyles, type LearnerReportProps } from "../components/LearnerReportLayout";
import { MetricChart } from "../components/MetricChart";
import { RecommendationPanel } from "../components/RecommendationPanel";
import { LearnerReadingReportView } from "../components/LearnerReadingReportView";

export function AIProgressReportScreen(props: LearnerReportProps & { initialSaved?: boolean }) {
  if (!props.demoMode || props.dashboard.role !== "learner") {
    return <DashboardStateView state={{ status: "temporarily_unavailable", provenance: "live_unavailable" }} />;
  }
  const dashboard = props.dashboard;
  const labels = { reading_accuracy: "Reading Accuracy (%)", reading_fluency_wpm: "Reading Speed (WPM)", hesitation_rate_per_word: "Hesitations per 100 attempted words" };
  return <LearnerReadingReportView allowSaved initialSaved={props.initialSaved}
    periodStart={dashboard.reportingStartUtc} periodEnd={dashboard.reportingEndUtc}
    metrics={[{ label: "Completed Sessions", value: String(dashboard.includedSessionCount) }, ...dashboard.metrics.map(metric => ({ label: labels[metric.key], value: dashboard.includedSessionCount ? `${metric.latestValue}${metric.key === "reading_accuracy" ? "%" : metric.key === "reading_fluency_wpm" ? " WPM" : ""}` : "Unavailable" }))]}
    currentSummary={<View style={{ gap: 10 }}><Text style={reportStyles.body}>{dashboard.contextSummary}</Text>{dashboard.metrics.map(metric => <View key={metric.key} style={{ gap: 4 }}><Text style={reportStyles.heading}>{metric.label}</Text><Text style={reportStyles.body}>{metric.explanation}</Text></View>)}</View>}
    currentDetails={<View style={{ gap: 12 }}>
      <Text style={reportStyles.period}>{props.periodDays}-day reporting period</Text>
      {props.dashboard.limitations.map(note => <Text key={note} style={reportStyles.body}>{note}</Text>)}
      <Text style={reportStyles.body}>{props.dashboard.disclaimer}</Text>
      {props.dashboard.metrics.map((metric) => (
        <View key={metric.key} style={reportStyles.card}>
          <MetricChart metric={metric} />
          <Text style={reportStyles.body}>
            {metric.validObservationCount === undefined ? "Valid observation count unavailable." : `${metric.validObservationCount} valid observations`}
            {" · "}
            {metric.missingObservationCount === undefined ? "Missing measurement count unavailable." : `${metric.missingObservationCount} missing measurements`}
          </Text>
        </View>
      ))}
      {props.dashboard.difficultyProgression.length > 0
        ? <DifficultyProgression observations={props.dashboard.difficultyProgression} />
        : <Text style={reportStyles.body}>Difficulty observations unavailable for this reporting period.</Text>}
      <RecommendationPanel recommendation={props.dashboard.recommendation} />
    </View>} />;
}
