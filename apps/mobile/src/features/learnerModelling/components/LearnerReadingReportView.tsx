import { useState, type ReactNode } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { developerToolsEnabled } from "../preview/developerTools";
import { readBundledLocalSnapshot, selectLocalReportSnapshot } from "../preview/localReportSnapshot";
import { LocalAiPdfButton } from "./LocalAiPdfButton";
import { palette, radii } from "../theme";

export interface ReportMetric { label: string; value: string }
const date = (value: string) => new Date(value).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
/** Factual current evidence and the independent saved AI snapshot never share content. */
export function LearnerReadingReportView({ metrics, periodStart, periodEnd, currentSummary, currentDetails, allowSaved = false, initialSaved = false }: {
  metrics: readonly ReportMetric[]; periodStart: string; periodEnd: string;
  currentSummary: ReactNode; currentDetails?: ReactNode; allowSaved?: boolean; initialSaved?: boolean;
}) {
  const [summary, setSummary] = useState(false);
  const [details, setDetails] = useState(false);
  const [saved, setSaved] = useState(initialSaved);
  const [developer, setDeveloper] = useState(false);
  const selection = { enabled: saved && allowSaved, development: __DEV__, demoMode: true, role: "learner" as const };
  const snapshot = selectLocalReportSnapshot({ ...selection, read: readBundledLocalSnapshot });
  return <ScrollView style={styles.scroll} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
    <Text accessibilityRole="header" style={styles.title}>My Reading Report</Text>
    <Text style={styles.disclosure}>{"Demo \u00b7 Fictional data"}</Text>
    <View testID="current-progress-report" style={styles.card}>
      <Text accessibilityRole="header" style={styles.heading}>Current Progress Report</Text>
      <Text style={styles.body}>Based on the selected reading results. This summary is not AI-written.</Text>
      <Text style={styles.disclosure}>{date(periodStart)} to {date(periodEnd)} (end not included)</Text>
      <View style={styles.metrics}>
        {metrics.map(metric => <View testID={`report-${metric.label}`} key={metric.label} style={styles.metric}><Text style={styles.value}>{metric.value}</Text><Text style={styles.metricLabel}>{metric.label}</Text></View>)}
      </View>
      <Pressable accessibilityRole="button" accessibilityState={{ expanded: summary }} onPress={() => setSummary(!summary)} style={styles.primary}><Text style={styles.primaryText}>{summary ? "Hide Current Summary" : "View Current Summary"}</Text></Pressable>
      {summary ? <View testID="current-summary-content" style={styles.details}>
        {currentSummary}
        {currentDetails ? <><Pressable accessibilityRole="button" accessibilityState={{ expanded: details }} onPress={() => setDetails(!details)} style={styles.secondary}><Text style={styles.actionText}>Report Details</Text></Pressable>{details ? currentDetails : null}</> : null}
        {__DEV__ && allowSaved ? <Text style={styles.disclosure}>PDF export is available for the saved AI report below.</Text> : null}
      </View> : null}
    </View>
    {__DEV__ && allowSaved ? <View testID="previously-saved-ai-report" style={styles.card}>
      <Text accessibilityRole="header" style={styles.heading}>Previously Saved AI Report</Text>
      <Text style={styles.body}>Created earlier using sample reading data.</Text>
      <Text style={styles.body}>Uses different sessions from this journey; no new AI report is generated.</Text>
      <Pressable accessibilityRole="button" accessibilityState={{ expanded: saved }} onPress={() => { setDeveloper(false); setSaved(!saved); }} style={styles.secondary}><Text style={styles.actionText}>{saved ? "Hide Saved AI Report" : "View Saved AI Report"}</Text></Pressable>
      {saved ? snapshot ? <View style={styles.details}>
        <Text style={styles.disclosure}>Report period: {date(snapshot.reportingStartUtc)} to {date(snapshot.reportingEndUtc)} (end not included)</Text>
        <Text style={styles.disclosure}>Created: {date(snapshot.generatedAt)}</Text>
        <Text style={styles.advisory}>ADVISORY ONLY</Text>
        <View testID="saved-ai-report-content" style={styles.details}>{snapshot.statements.map(text => <Text key={text} style={styles.body}>{text}</Text>)}</View>
        <LocalAiPdfButton compact snapshot={snapshot} selection={selection} />
        {developerToolsEnabled() ? <>
          <Pressable accessibilityRole="button" accessibilityState={{ expanded: developer }} onPress={() => setDeveloper(!developer)} style={styles.secondary}><Text style={styles.actionText}>Developer Details</Text></Pressable>
          {developer ? <View style={styles.details}>
            <Text style={styles.body}>Source: {snapshot.source} - Model: {snapshot.model}</Text>
            <Text style={styles.body}>Generated on computer: {snapshot.generatedAt}</Text>
            <Text style={styles.body}>Fixed sample period: {snapshot.reportingStartUtc} to {snapshot.reportingEndUtc} (end exclusive, UTC).</Text>
            <Text style={styles.body}>This separate fixture does not use the selected dashboard reporting period or demo measurements.</Text>
            <Text style={styles.body}>Production learner AI generation is not connected.</Text>
          </View> : null}
        </> : null}
      </View> : <Text accessibilityRole="alert" style={styles.body}>The saved AI report is unavailable. Your current summary is still available.</Text> : null}
    </View> : null}
  </ScrollView>;
}
const styles = StyleSheet.create({
  scroll: { backgroundColor: palette.paper }, content: { paddingHorizontal: 16, paddingTop: 8, paddingBottom: 96, gap: 12 },
  title: { fontSize: 22, color: palette.primaryDark, fontWeight: "900" }, disclosure: { fontSize: 12, lineHeight: 18, color: palette.muted },
  heading: { color: palette.primaryDark, fontSize: 18, fontWeight: "800" }, body: { color: palette.ink, fontSize: 15, lineHeight: 22 },
  card: { backgroundColor: palette.surface, borderRadius: radii.medium, padding: 12, gap: 10 }, details: { gap: 10 },
  metrics: { flexDirection: "row", flexWrap: "wrap", gap: 6 }, metric: { flexGrow: 1, flexBasis: 110, minWidth: 110, padding: 10, backgroundColor: palette.primarySoft, borderRadius: radii.small, gap: 6 },
  value: { fontSize: 22, color: palette.primaryDark, fontWeight: "900" }, metricLabel: { fontSize: 12, lineHeight: 18, color: palette.ink }, advisory: { fontSize: 12, color: palette.primaryDark, fontWeight: "800" },
  primary: { minHeight: 48, padding: 12, alignItems: "center", justifyContent: "center", backgroundColor: palette.primary, borderRadius: radii.small }, primaryText: { color: palette.surface, fontWeight: "800", fontSize: 16 },
  secondary: { minHeight: 44, padding: 10, alignItems: "center", justifyContent: "center", backgroundColor: palette.primarySoft, borderRadius: radii.small }, actionText: { color: palette.primaryDark, fontWeight: "700", fontSize: 14 },
});
