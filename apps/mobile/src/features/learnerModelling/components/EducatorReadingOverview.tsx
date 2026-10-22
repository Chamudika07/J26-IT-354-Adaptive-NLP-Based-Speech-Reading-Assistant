import { useState, type ReactNode } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import type { EducatorArtifact } from "../preview/roleScenarioResults";
import { reportStyles as s } from "./LearnerReportLayout";
import { educatorFactualSummary } from "../export/educatorReports";
import { palette } from "../theme";

type Projection = EducatorArtifact["projection"];
const METRICS = [
  { key: "reading_accuracy", label: "Reading Accuracy", unit: "%", scale: 100, color: palette.primary },
  { key: "reading_fluency_wpm", label: "Reading Speed", unit: "WPM", scale: 1, color: palette.teal },
  { key: "hesitation_rate_per_word", label: "Hesitation Frequency", unit: "per 100 attempted words", scale: 100, color: palette.orange },
] as const;
const shortDate = (v: string) => new Date(v).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const supportLabel = (v: string) => v === "adaptive" ? "Adaptive support" : v === "baseline_fixed" ? "Fixed support" : v === "manual_override" ? "Manually chosen support" : "Recorded support";
const value = (v: string | null | undefined, scale: number) => v == null ? "Unavailable" : String(Number((Number(v) * scale).toFixed(2)));

/** Presentation only. Trend flags and comparison averages come from the role projection. */
export function EducatorReadingOverview({ projection: p, selection, onSeparate, studentName, reportAction }: {
  projection: Projection; selection: string; onSeparate: () => void; studentName?: string; reportAction?: ReactNode;
}) {
  const [details, setDetails] = useState(false);
  const dateRange = `${shortDate(p.reporting_period.start_at_utc)} to before ${shortDate(p.reporting_period.end_at_utc)}`;
  return <ScrollView style={s.scroll} contentContainerStyle={[s.content, { gap: 12, paddingBottom: 128 }]}>
    <Text style={{ color: palette.muted, fontSize: 12 }}>{"Demo \u00b7 Fictional classroom data"}</Text>
    <View style={{ gap: 4 }}>
      <Text accessibilityRole="header" style={[s.title, { fontSize: 22 }]}>{studentName ?? "Teacher Dashboard"}</Text>
      <Text style={s.body}>{selection.replace("Sample ", "Scenario ")} · {dateRange}</Text>
    </View>
    <View style={[s.card, { padding: 12, gap: 4, backgroundColor: palette.tealSoft }]}>
      <Text accessibilityRole="header" style={s.heading}>Completed Sessions</Text>
      <Text accessibilityLiveRegion="polite" style={s.body}>{p.included_session_count} completed {p.included_session_count === 1 ? "session" : "sessions"}</Text>
      <Text style={s.body}>Results use this scenario’s reading period.</Text>
    </View>
    <View style={[s.card, { padding: 12, gap: 8 }]}><Text accessibilityRole="header" style={s.heading}>Reading Summary</Text><Text style={s.body}>{educatorFactualSummary(p).replace(/^1 completed sessions/, "1 completed session")}</Text>{reportAction}</View>
    {p.partitions.length === 0 ? <Text style={s.body}>No completed reading sessions in this period.</Text> : null}
    {p.partitions.map((context, i) => {
      const comparable = context.metrics.filter(m => m.evidence_sufficient && m.change_direction !== "insufficient_evidence");
      return <View key={i} style={{ gap: 12 }}>
        <Text style={s.body}>{context.task_type.replaceAll("_", " ")} · {context.difficulty_tier} level · {supportLabel(context.support_mode)}</Text>
        <Text accessibilityRole="header" style={s.heading}>Latest Reading Results</Text>
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
          {METRICS.map(display => {
            const metric = context.metrics.find(m => m.metric_name === display.key);
            return <View key={display.key} testID={`teacher-${display.key}`} style={[s.card, { flexGrow: 1, flexBasis: 100, padding: 12, gap: 4, borderTopWidth: 4, borderTopColor: display.color }]}>
              <Text style={s.body}>{display.label}</Text>
              <Text style={[s.heading, { fontSize: 24, color: display.color }]}>{value(metric?.latest_value, display.scale)}</Text>
              <Text style={s.body}>{display.unit}</Text>
            </View>;
          })}
        </View>
        <View style={[s.card, { padding: 14, gap: 8 }]}>
          <Text accessibilityRole="header" style={s.heading}>Progress Summary</Text>
          <Text style={s.body}>{context.session_count} completed {context.session_count === 1 ? "session" : "sessions"} with the same activity, level and support.</Text>
          {comparable.length === 0 ? <Text style={s.body}>Not enough reading sessions to show a reliable trend yet.</Text> : comparable.map(metric => {
            const display = METRICS.find(m => m.key === metric.metric_name)!;
            const change = metric.change_direction === "increased" ? "increased" : metric.change_direction === "decreased" ? "decreased" : "showed no measured change";
            return <View key={metric.metric_name}>
              <Text style={s.body}>{display.label} {change} between the comparison periods.</Text>
              <Text style={s.body}>Earlier average: {value(metric.early_window_mean, display.scale)} · Recent average: {value(metric.late_window_mean, display.scale)} {display.unit}</Text>
            </View>;
          })}
          {comparable.length > 0 && comparable.length < METRICS.length ? <Text style={s.body}>Some measurements still need more comparable sessions.</Text> : null}
        </View>
        <View style={[s.card, { padding: 14, gap: 10 }]}>
          <Text accessibilityRole="header" style={s.heading}>First and Latest Results</Text>
          {METRICS.map(display => {
            const metric = context.metrics.find(m => m.metric_name === display.key);
            const max = display.key === "reading_accuracy" ? 100 : Math.max(1, Number(metric?.first_value ?? 0) * display.scale, Number(metric?.latest_value ?? 0) * display.scale);
            return <View key={display.key} style={{ gap: 4 }}>
              <Text style={[s.body, { fontWeight: "700" }]}>{display.label} ({display.unit})</Text>
              {(["first_value", "latest_value"] as const).map((key, index) => {
                const observation = metric?.[key];
                return <View key={key} accessibilityLabel={`${display.label}: ${index === 0 ? "First" : "Latest"} ${value(observation, display.scale)} ${display.unit}`} style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
                  <Text style={[s.body, { width: 45 }]}>{index === 0 ? "First" : "Latest"}</Text>
                  <View style={{ flex: 1, height: 12, backgroundColor: palette.primarySoft, borderRadius: 6 }}>
                    {observation != null ? <View style={{ height: 12, borderRadius: 6, backgroundColor: display.color, width: `${Math.max(0, Math.min(100, Number(observation) * display.scale / max * 100))}%` }} /> : null}
                  </View><Text style={[s.body, { minWidth: 40, flexShrink: 1 }]}>{value(observation, display.scale)}</Text>
                </View>;
              })}
              <Text style={s.body}>{metric?.valid_observation_count ?? 0} measured · {metric?.missing_observation_count ?? 0} unavailable</Text>
            </View>;
          })}
          <Text style={s.body}>First and latest results alone do not establish a trend.</Text>
        </View>
      </View>;
    })}
    {p.partitions.length === 0 ? <View style={s.card}><Text accessibilityRole="header" style={s.heading}>Reading Measurements</Text><Text style={s.body}>Accuracy, speed and hesitation frequency are not measured yet.</Text><Text style={s.body}>Not enough reading sessions to show a reliable trend yet.</Text></View> : null}
    <View style={[s.card, { padding: 14, gap: 8 }]}>
      <Text accessibilityRole="header" style={s.heading}>Support History</Text>
      {p.support_mode_exposures.length === 0 ? <Text style={s.body}>No recorded support use yet.</Text> : p.support_mode_exposures.map((item, i) => <View key={i} style={{ gap: 4 }}>
        <Text style={[s.body, { fontWeight: "700" }]}>{supportLabel(item.support_mode)}</Text>
        <Text style={s.body}>{item.session_count} {item.session_count === 1 ? "session" : "sessions"} · {shortDate(item.first_observed_at)} to {shortDate(item.latest_observed_at)}</Text>
        <Text style={s.body}>Active reading: {item.active_duration_ms / 1000} seconds · Total session time: {item.total_duration_ms / 1000} seconds</Text>
      </View>)}
      <Text style={s.body}>This shows support used, not a recommended change.</Text>
    </View>
    <Pressable accessibilityRole="button" accessibilityState={{ expanded: details }} onPress={() => setDetails(!details)} style={s.previewLink}><Text style={s.body}>About These Results</Text></Pressable>
    {details ? <View style={s.card}><Text style={s.body}>{p.disclaimer}</Text>{p.partitions.map((context, i) => <View key={i}>{context.metrics.map(metric => <Text key={metric.metric_name} style={s.body}>{metric.educational_interpretation}</Text>)}</View>)}</View> : null}
    <Pressable accessibilityRole="button" onPress={onSeparate} style={s.previewLink}><Text style={s.body}>View separate example</Text></Pressable>
  </ScrollView>;
}
