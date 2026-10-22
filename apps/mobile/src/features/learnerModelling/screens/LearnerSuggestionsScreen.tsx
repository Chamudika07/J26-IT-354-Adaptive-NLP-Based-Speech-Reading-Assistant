import { developerToolsEnabled } from "../preview/developerTools";
import { useState } from "react";
import { Pressable, Text, View } from "react-native";

import { reportStyles, type LearnerReportProps } from "../components/LearnerReportLayout";
import { DashboardStateView } from "../components/DashboardStateView";
import { LocalPreviewLayout } from "../components/LocalPreviewLayout";
import { selectBackendRecommendation } from "../preview/backendRecommendationSnapshot";
import { ReadingTipsView } from "../components/ReadingTipsView";

export function LearnerSuggestionsScreen(props: LearnerReportProps) {
  const [selected, setSelected] = useState(false);
  if (!props.demoMode || props.dashboard.role !== "learner") {
    return <DashboardStateView state={{ status: "temporarily_unavailable", provenance: "live_unavailable" }} />;
  }
  const snapshot = selectBackendRecommendation({ enabled: selected, development: __DEV__, demoMode: props.demoMode, role: props.dashboard.role });
  const flag = (value: boolean | null) => value === null ? "Unavailable" : value ? "Yes" : "No";
  const toggle = <Pressable accessibilityRole="button" style={reportStyles.previewLink}
    onPress={() => setSelected(!selected)} accessibilityLabel={selected ? "Return to demo suggestions" : "View backend synthetic recommendation"}>
    <Text style={reportStyles.body}>{selected ? "Return to demo suggestions" : "View backend synthetic recommendation"}</Text>
  </Pressable>;
  if (selected && developerToolsEnabled()) {
    return <LocalPreviewLayout title="Reading Tips"
      disclosure="SYNTHETIC BACKEND RECOMMENDATION ? ADVISORY ONLY"
      introduction="A saved suggestion from the backend rules, using made-up reading sessions. No settings are changed.">
      {snapshot ? <View style={reportStyles.card}>
        <Text style={reportStyles.body}>Source: {snapshot.source} ? {snapshot.engine_version}</Text>
        <Text style={reportStyles.body}>Separate synthetic period: {snapshot.reporting_start.slice(0, 10)} to {snapshot.reporting_end.slice(0, 10)} (UTC, end exclusive). Dashboard filters do not change this saved fixture.</Text>
        <Text style={reportStyles.body}>Reading context: Independent reading ? {snapshot.presentation.current}</Text>
        <Text style={reportStyles.heading}>Current support</Text>
        <Text style={reportStyles.body}>{snapshot.presentation.current ?? "Settings unavailable"}</Text>
        <Text style={reportStyles.heading}>{snapshot.presentation.action ?? "Recommendation unavailable"}</Text>
        <Text style={reportStyles.body}>Suggested changes: {snapshot.presentation.proposed.length ? snapshot.presentation.proposed.join(" ") : "None proposed."}</Text>
        {snapshot.presentation.reasons.map((text) => <Text key={text} style={reportStyles.body}>{text}</Text>)}
        <Text style={reportStyles.heading}>Evidence and limits</Text>
        <Text style={reportStyles.body}>Evidence: {snapshot.presentation.evidence_state}</Text>
        {snapshot.presentation.limitations.length === 0 ? <Text style={reportStyles.body}>No extra evidence limitations reported by this saved decision.</Text> : null}
        {snapshot.presentation.limitations.map((text) => <Text key={text} style={reportStyles.body}>{text}</Text>)}
        <Text style={reportStyles.body}>Fixed baseline: {flag(snapshot.presentation.fixed_baseline)}. Manual support: {flag(snapshot.presentation.manual_override_active)}. Settings locked: {flag(snapshot.presentation.global_lock)}.</Text>
        <Text style={reportStyles.body}>Manual control prevents adjustment: {flag(snapshot.presentation.manual_control_prevents_adjustment)}. Decision blocked by manual control: {flag(snapshot.presentation.blocked_by_manual_override)}.</Text>
        <Text style={reportStyles.body}>No settings were changed. Review ideas with a parent or teacher.</Text>
        <Text style={reportStyles.body}>{snapshot.presentation.disclaimer}</Text>
      </View> : <Text accessibilityRole="alert" style={reportStyles.body}>Backend snapshot unavailable or invalid. No recommendation is substituted.</Text>}
      {toggle}
    </LocalPreviewLayout>;
  }
  const recommendation = props.dashboard.recommendation;
  const titles = { maintain: "Keep current support", adjust_support: "Review reading support", adjust_difficulty: "Review reading level" };
  return <ReadingTipsView disclosure={"Demo \u00b7 Fictional data"} developerAction={developerToolsEnabled() ? toggle : undefined} title={titles[recommendation.action]}
    metrics={[{ label: "Completed Sessions", value: String(props.dashboard.includedSessionCount) }, ...props.dashboard.metrics.map(metric => ({ label: metric.key === "reading_accuracy" ? "Reading Accuracy (%)" : metric.key === "reading_fluency_wpm" ? "Reading Speed (WPM)" : "Hesitations per 100 attempted words", value: props.dashboard.includedSessionCount ? `${metric.latestValue}${metric.key === "reading_accuracy" ? "%" : metric.key === "reading_fluency_wpm" ? " WPM" : ""}` : "Unavailable", evidence: metric.evidenceLabel, explanation: metric.explanation, observations: metric.validObservationCount !== undefined && metric.missingObservationCount !== undefined ? `Valid observations: ${metric.validObservationCount}; missing measurements: ${metric.missingObservationCount}` : undefined }))]}
    limitations={[...props.dashboard.limitations, props.dashboard.disclaimer]} reasons={[recommendation.explanation]} reasonCodes={recommendation.reasonCodes} current={props.dashboard.contextSummary} currentLabel="Reading context" periodLabel={`${props.periodDays}-day reporting period`}
    nextSteps={[recommendation.supportSuggestion, ...(recommendation.action === "adjust_difficulty" ? [`Suggested reading level: ${recommendation.recommendedTier}`] : []), "Review this suggestion with a parent or teacher before making changes."]} />;
}
