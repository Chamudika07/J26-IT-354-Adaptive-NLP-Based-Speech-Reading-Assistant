import { EducatorReadingOverview } from "./EducatorReadingOverview";
import { useState, type ReactNode } from "react";
import { Pressable, Text, View } from "react-native";
import { useSelectedScenario } from "../preview/selectedScenario";
import { selectRoleScenario } from "../preview/roleScenarioResults";
import type { ChangeDirection, MetricKey } from "../types";
import { LocalPreviewLayout } from "./LocalPreviewLayout";
import { MetricChart } from "./MetricChart";
import { reportStyles as s } from "./LearnerReportLayout";

/** Existing role screens opt in only for ready development/demo state. */
export function RoleScenarioView({ role, children }: { role: "guardian" | "educator"; children: ReactNode }) {
  const id = useSelectedScenario();
  const [separate, setSeparate] = useState<string | null>(null);
  if (!__DEV__ || !id) return <>{children}</>;
  if (separate === id) return <View style={{ flex: 1 }}>
    <Pressable accessibilityRole="button" onPress={() => setSeparate(null)} style={s.previewLink}><Text style={s.body}>Back to selected sample</Text></Pressable>{children}
  </View>;
  const guardian = role === "guardian" ? selectRoleScenario("guardian", id) : null;
  const educator = role === "educator" ? selectRoleScenario("educator", id) : null;
  if (educator) return <EducatorReadingOverview projection={educator.projection} selection={(() => { try { const index: unknown = JSON.parse(id)[0]; return typeof index === "number" && index >= 0 ? `Scenario ${index}` : "Selected reading results"; } catch { return "Selected reading results"; } })()} onSeparate={() => setSeparate(id)} />;
  const projection = guardian?.projection;
  const contexts = guardian?.projection.contexts ?? [];
  const heading = role === "guardian" ? "Parent Dashboard" : "Teacher Dashboard";
  let label = "Selected sample";
  try { const index: unknown = JSON.parse(id)[0]; label = typeof index === "number" && index >= 0 ? `Sample ${index}` : "Imported sample results"; } catch { /* Unavailable below. */ }
  return <LocalPreviewLayout title={heading} disclosure="" introduction="Reading progress from the selected example.">
    <Text accessibilityLiveRegion="polite" style={s.period}>Selected reading scenario: {label}</Text>
    {!projection ? <Text accessibilityRole="alert" style={s.body}>These sample results are unavailable. Select a matching sample in Learner view or choose a separate example.</Text> : <>
      <View style={s.card}>
        <Text accessibilityRole="header" style={s.heading}>Reading Overview</Text>
        <Text style={s.body}>{projection.included_session_count} completed sample sessions</Text>
        <Text style={s.body}>These results follow the selected sample period.</Text>
        <Text style={s.body}>Period: {projection.reporting_period.start_at_utc.slice(0, 10)} to {projection.reporting_period.end_at_utc.slice(0, 10)} (end not included).</Text>
        {contexts.length === 0 ? <Text style={s.body}>No comparable completed sessions yet.</Text> : null}
      </View>
      {contexts.map((context, i) => <View key={i} style={{ gap: 12 }}>
        <Text style={s.heading}>{context.task_type.replaceAll("_", " ")} · {context.difficulty_tier} · {context.support_mode.replaceAll("_", " ")}</Text>
        {context.metrics.map(m => {
          const scale = m.metric_name === "reading_fluency_wpm" ? 1 : 100;
          const label = m.metric_name === "reading_accuracy" ? "Reading Accuracy" : m.metric_name === "reading_fluency_wpm" ? "Reading Speed" : "Hesitation Frequency";
          const unit = m.metric_name === "reading_accuracy" ? "%" : m.metric_name === "reading_fluency_wpm" ? "WPM" : "per 100 attempted words";
          const explanation = m.explanation;
          return <View key={m.metric_name}>
            {m.first_value === null || m.latest_value === null ? <View style={s.card}><Text style={s.heading}>{label}</Text><Text style={s.body}>Not enough measurements yet.</Text><Text style={s.body}>{explanation}</Text></View> : <MetricChart metric={{
              key: m.metric_name as MetricKey, label, unit,
              firstValue: Number(m.first_value) * scale, latestValue: Number(m.latest_value) * scale,
              changeDirection: m.change_direction as ChangeDirection,
              evidenceLabel: m.evidence_sufficient ? "Comparable reading results available" : "Keep reading to see more progress",
              explanation, validObservationCount: m.valid_observation_count, missingObservationCount: m.missing_observation_count,
            }} />}
            {role === "educator" ? <Text style={s.body}>{m.valid_observation_count} measured · {m.missing_observation_count} unavailable</Text> : null}
          </View>;
        })}
        <Text style={s.body}>{context.session_count} sessions · {context.first_session_at.slice(0, 10)} to {context.latest_session_at.slice(0, 10)}</Text>
      </View>)}
      <View style={s.card}>
        <Text accessibilityRole="header" style={s.heading}>Support Used During Reading</Text>
        {(guardian?.projection.support_exposures ?? []).map((support, i) => <View key={i}>
          <Text style={s.body}>{support.support_mode.replaceAll("_", " ")} · {support.session_count} sessions</Text>
          <Text style={s.body}>{support.first_observed_at.slice(0, 10)} to {support.latest_observed_at.slice(0, 10)}</Text>
        </View>)}
        <Text style={s.body}>This describes support used, not a new recommendation.</Text>
      </View>
      <View style={s.card}><Text accessibilityRole="header" style={s.heading}>Progress Summary</Text><Text style={s.body}>{projection.disclaimer}</Text></View>
    </>}
    <Pressable accessibilityRole="button" onPress={() => setSeparate(id)} style={s.previewLink}><Text style={s.body}>View separate example</Text></Pressable>
  </LocalPreviewLayout>;
}
