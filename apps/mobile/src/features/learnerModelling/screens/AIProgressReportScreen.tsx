import { developerToolsEnabled } from "../preview/developerTools";
import { useState } from "react";
import { Pressable, Text, View } from "react-native";

import { DashboardStateView } from "../components/DashboardStateView";
import { DifficultyProgression } from "../components/DifficultyProgression";
import { reportStyles, type LearnerReportProps } from "../components/LearnerReportLayout";
import { MetricChart } from "../components/MetricChart";
import { RecommendationPanel } from "../components/RecommendationPanel";
import { ReadingBuddyIllustration } from "../components/ReadingBuddyIllustration";
import { LocalPreviewLayout } from "../components/LocalPreviewLayout";
import { LocalAiPdfButton } from "../components/LocalAiPdfButton";
import { readBundledLocalSnapshot, selectLocalReportSnapshot } from "../preview/localReportSnapshot";

export function AIProgressReportScreen(props: LearnerReportProps & { initialSaved?: boolean }) {
  const [showSnapshot, setShowSnapshot] = useState(props.initialSaved ?? false);
  const [details, setDetails] = useState(false);
  const [summary, setSummary] = useState(false);
  if (!props.demoMode || props.dashboard.role !== "learner") {
    return <DashboardStateView state={{ status: "temporarily_unavailable", provenance: "live_unavailable" }} />;
  }
  const snapshot = selectLocalReportSnapshot({
    enabled: showSnapshot, development: __DEV__, demoMode: props.demoMode,
    role: props.dashboard.role, read: readBundledLocalSnapshot,
  });
  if (snapshot) {
    return (
      <LocalPreviewLayout title="My Reading Report"
        disclosure="Created earlier using sample reading data."
        introduction="See your reading progress, strengths and helpful tips."
        actions={<LocalAiPdfButton compact snapshot={snapshot} selection={{
          development: __DEV__, demoMode: props.demoMode, enabled: showSnapshot, role: props.dashboard.role,
        }} />}>
        <View style={reportStyles.card}>
          <ReadingBuddyIllustration compact />
          <Text accessibilityRole="header" style={reportStyles.heading}>SAVED AI REPORT</Text>
          <Text style={reportStyles.body}>This report is separate from your current reading journey. Opening it does not create a new report.</Text>
          <Text style={reportStyles.period}>ADVISORY ONLY</Text>
          {developerToolsEnabled() ? <Pressable accessibilityRole="button" accessibilityState={{ expanded: details }} onPress={() => setDetails(!details)} style={reportStyles.previewLink}><Text style={reportStyles.body}>Developer Details</Text></Pressable> : null}
          {developerToolsEnabled() && details ? <>
            <Text style={reportStyles.body}>Source: {snapshot.source} - Model: {snapshot.model}</Text>
            <Text style={reportStyles.body}>Generated on computer: {snapshot.generatedAt}</Text>
            <Text style={reportStyles.body}>Fixed sample period: {snapshot.reportingStartUtc} to {snapshot.reportingEndUtc} (end exclusive, UTC).</Text>
            <Text style={reportStyles.body}>This separate fixture does not use the selected dashboard reporting period or demo measurements.</Text>
            <Text style={reportStyles.body}>Production learner AI generation is not connected.</Text>
          </> : null}
        </View>
        <View style={reportStyles.card}>
          <Text accessibilityRole="header" style={reportStyles.heading}>Your saved reading report</Text>
          {snapshot.statements.map((text) => <Text key={text} style={reportStyles.body}>{text}</Text>)}
        </View>
        {!props.initialSaved ? <Pressable accessibilityRole="button" accessibilityLabel="Return to reading summary"
          style={reportStyles.previewLink} onPress={() => { setDetails(false); setShowSnapshot(false); }}>
          <Text style={reportStyles.body}>Return to reading summary</Text>
        </Pressable> : null}
      </LocalPreviewLayout>
    );
  }
  return (
    <LocalPreviewLayout title="My Reading Report" disclosure="Choose a saved report or a reading summary."
      introduction="See your reading progress, strengths and helpful tips.">
      <LocalAiPdfButton snapshot={null} selection={{
        development: __DEV__, demoMode: props.demoMode, enabled: false, role: props.dashboard.role,
      }} />
      {__DEV__ ? (
        <View style={reportStyles.card}>
          <Text style={reportStyles.heading}>Your saved AI report</Text>
          <Text style={reportStyles.body}>Open an earlier AI report. It is separate from your current reading journey.</Text>
          {showSnapshot ? <Text accessibilityRole="alert" style={reportStyles.body}>The saved AI report is unavailable. You can still read the sample summary.</Text> : null}
          <Pressable accessibilityRole="button" accessibilityLabel={showSnapshot ? "Close unavailable saved report" : "Open saved AI report"}
            style={reportStyles.primaryAction} onPress={() => { setDetails(false); setShowSnapshot(!showSnapshot); }}>
            <Text style={reportStyles.primaryLabel}>{showSnapshot ? "Close saved report" : "Open saved AI report"}</Text>
          </Pressable>
        </View>
      ) : null}
      <View style={reportStyles.card}>
        <ReadingBuddyIllustration compact />
        <Text style={reportStyles.heading}>Reading Progress Summary</Text>
        <Text style={reportStyles.body}>This sample summary is not AI-written. It does not update the saved AI report.</Text>
        <Pressable accessibilityRole="button" accessibilityState={{ expanded: summary }} onPress={() => setSummary(!summary)} style={reportStyles.previewLink}><Text style={reportStyles.body}>{summary ? "Hide reading summary" : "Read reading summary"}</Text></Pressable>
        {developerToolsEnabled() ? <Pressable accessibilityRole="button" accessibilityState={{ expanded: details }} onPress={() => setDetails(!details)} style={reportStyles.previewLink}><Text style={reportStyles.body}>Developer Details</Text></Pressable> : null}
        {developerToolsEnabled() && details ? <>
          <Text style={reportStyles.heading}>AI GENERATION NOT CONNECTED</Text>
          <Text style={reportStyles.body}>Production learner AI generation is not connected. No external AI service is called.</Text>
          <Text style={reportStyles.body}>{props.dashboard.reportingStartUtc} to {props.dashboard.reportingEndUtc} (UTC).</Text>
        </> : null}
      </View>
      {summary ? <>
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
      </> : null}
    </LocalPreviewLayout>
  );
}
