import { developerToolsEnabled } from "../preview/developerTools";
import { useState } from "react";
import { Pressable, Text, View } from "react-native";

import { LearnerReportLayout, reportStyles, type LearnerReportProps } from "../components/LearnerReportLayout";
import { DashboardStateView } from "../components/DashboardStateView";
import { LocalPreviewLayout } from "../components/LocalPreviewLayout";
import { selectBackendRecommendation } from "../preview/backendRecommendationSnapshot";
import { RecommendationPanel } from "../components/RecommendationPanel";

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
  return (
    <LearnerReportLayout {...props} title="My Reading Tips"
      introduction="Explore suggestions with a parent or teacher. Your reading level and support choices stay unchanged.">
      {developerToolsEnabled() ? toggle : null}
      <View style={reportStyles.card}>
        <Text accessibilityRole="header" style={reportStyles.heading}>Support Level & Recommendations</Text>
        <Text style={reportStyles.body}>Observed reading context: {props.dashboard.contextSummary}</Text>
        <Text style={reportStyles.body}>Authoritative recommended support level unavailable. The existing suggestion below is advisory, not a saved support level.</Text>
      </View>
      <RecommendationPanel recommendation={props.dashboard.recommendation} playful collapsibleDetails />
      <View style={reportStyles.card}>
        <Text accessibilityRole="header" style={reportStyles.heading}>What supports this idea?</Text>
        {props.dashboard.metrics.map((metric) => (
          <View key={metric.key} style={{ gap: 8 }}>
            <Text style={reportStyles.heading}>{metric.label}</Text>
            <Text style={reportStyles.body}>{metric.explanation}</Text>
            <Text style={reportStyles.body}>{metric.evidenceLabel}</Text>
          </View>
        ))}
      </View>
    </LearnerReportLayout>
  );
}
