import { GuardianReportButton } from "./GuardianReportButton";
import type { GuardianReportData } from "../export/guardianReport";
import { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import type { GuardianArtifact } from "../preview/roleScenarioResults";
import type { GuardianDashboardPreview, MetricKey } from "../types";
import { palette, radii, softShadow } from "../theme";

import { ReadingBuddyIllustration } from "./ReadingBuddyIllustration";

const metricArt = { reading_accuracy: { accent: "#3182F6", background: "#EEF5FF", ink: "#153E75", icon: "\uD83C\uDFAF" }, reading_fluency_wpm: { accent: "#22C55E", background: "#EAFBF1", ink: "#166534", icon: "\u23F1\uFE0F" }, hesitation_rate_per_word: { accent: "#8B5CF6", background: "#F4EFFF", ink: "#5B21B6", icon: "\u23F8\uFE0F" } };

type Metric = { key: MetricKey; first: number | null; latest: number | null; count?: number; missing?: number; sufficient: boolean; direction: string; explanation: string; detail?: string };
type Context = { label: string; sessions: number; metrics: Metric[] };
const labels: Record<MetricKey, [string, string]> = { reading_accuracy: ["Reading Accuracy", "%"], reading_fluency_wpm: ["Reading Speed", "WPM"], hesitation_rate_per_word: ["Hesitation Frequency", "per 100 attempted words"] };
const keys = Object.keys(labels) as MetricKey[];
const value = (n: number | null | undefined) => n == null ? "Unavailable" : String(Number(n.toFixed(2)));
const sessions = (n: number) => `${n} ${n === 1 ? "session" : "sessions"}`;
const date = (s: string) => new Date(s).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
/** Presentation consumes only Guardian-authorized projections, never learner artifacts. */
export function ParentDashboard({ projection, dashboard, selection, onSeparate }: {
  projection?: GuardianArtifact["projection"] | null; dashboard?: GuardianDashboardPreview; selection?: string; onSeparate?: () => void;
}) {
  const [about, setAbout] = useState(false);
  const available = Boolean(projection || dashboard);
  const count = projection?.included_session_count ?? dashboard?.includedSessionCount ?? 0;
  const contexts: Context[] = projection ? projection.contexts.map(c => ({
    label: `${c.task_label} · ${c.difficulty_label} · ${c.support_label}`, sessions: c.session_count,
    metrics: c.metrics.map(m => ({ key: m.metric_name as MetricKey, first: m.first_value === null ? null : Number(m.first_value) * (m.metric_name === "reading_fluency_wpm" ? 1 : 100), latest: m.latest_value === null ? null : Number(m.latest_value) * (m.metric_name === "reading_fluency_wpm" ? 1 : 100), count: m.valid_observation_count, missing: m.missing_observation_count, sufficient: m.evidence_sufficient, direction: m.change_direction, explanation: m.explanation })),
  })) : dashboard ? [{ label: dashboard.contextSummary, sessions: count, metrics: dashboard.metrics.map(m => ({ key: m.key, first: count ? m.firstValue : null, latest: count ? m.latestValue : null, count: m.validObservationCount, missing: m.missingObservationCount, sufficient: m.changeDirection !== "insufficient_evidence", direction: m.changeDirection, explanation: m.explanation, detail: m.detail })) }] : [];
  // The projection provides ordered context summaries; select by explicit latest-session timestamp, not array position.
  const latestIndex = projection?.contexts.reduce((best, c, i, all) => c.latest_session_at > all[best]!.latest_session_at ? i : best, 0) ?? 0;
  const latest = contexts[latestIndex];
  const trendAvailable = contexts.some(c => c.sessions > 1 && c.metrics.some(m => m.sufficient && (m.count ?? 0) > 1));
  const start = projection?.reporting_period.start_at_utc ?? dashboard?.reportingStartUtc;
  const end = projection?.reporting_period.end_at_utc ?? dashboard?.reportingEndUtc;
  const status = trendAvailable ? "Comparable reading results are available below." : "More reading sessions are needed to see a trend";
  const report: GuardianReportData | null = available && start && end ? {
    source: selection ? `Selected reading scenario: ${selection}` : "Independent example. It does not follow the Learner's selected scenario.",
    start, end, completed: count, status,
    latest: keys.map(key => ({ label: labels[key][0], unit: labels[key][1], value: value(latest?.metrics.find(m => m.key === key)?.latest) })),
    contexts: contexts.map(c => ({ label: c.label, sessions: c.sessions, metrics: c.metrics.map(m => ({ label: labels[m.key][0], unit: labels[m.key][1], first: value(m.first), latest: value(m.latest), comparable: c.sessions > 1 && (m.count ?? 0) > 1 && m.first !== null && m.latest !== null,
      trend: c.sessions > 1 && (m.count ?? 0) > 1 && m.sufficient ? m.direction === "no_observed_change" ? "No observed change" : m.direction === "increased" ? "Increased" : m.direction === "decreased" ? "Decreased" : null : null, explanation: m.explanation })) })),
    support: projection?.support_exposures.map(x => `${x.support_label}: ${sessions(x.session_count)}`) ?? [],
    notes: [...(projection?.evidence_limitations ?? dashboard?.limitations ?? []), projection?.disclaimer ?? dashboard?.disclaimer ?? ""],
  } : null;
  return <ScrollView style={s.scroll} contentContainerStyle={s.content}>
    <View testID="parent-header" style={s.hero}>
      <View style={s.headerCopy}><Text accessibilityRole="header" style={s.title}>Parent Dashboard</Text><Text style={s.note}>{"Demo \u00b7 Fictional data"}</Text></View>
      <ParentReadingArtwork />
    </View>
    {selection ? <Text accessibilityLiveRegion="polite" style={s.note}>Selected reading scenario: {selection}</Text> : <Text style={s.note}>Independent example. It does not follow the Learner&apos;s selected scenario.</Text>}
    {!available ? <Text accessibilityRole="alert" style={s.body}>These sample results are unavailable. Select a matching sample in Learner view or choose a separate example.</Text> : <>
      <View testID="parent-overview" style={s.overview}>
      <View style={s.overviewHeading}><View style={s.headerCopy}><Text accessibilityRole="header" style={s.heading}>Reading Overview</Text>{start && end ? <Text style={s.note}>{date(start)} to {date(end)} (end not included)</Text> : null}</View><View testID="parent-book-art" pointerEvents="none" accessible={false} accessibilityElementsHidden importantForAccessibility="no-hide-descendants"><ReadingBuddyIllustration compact /></View></View>
      <View style={s.metrics}>
        <View testID="parent-sessions" style={[s.metric, { backgroundColor: "#FFF7E6", borderTopColor: "#FFB020" }]}><ParentIcon symbol={"\uD83D\uDCDA"} /><Text style={s.value}>{count}</Text><Text style={s.body}>Completed Sessions</Text><Text style={s.note}>{sessions(count)} completed</Text></View>
        {keys.map(key => { const m = latest?.metrics.find(m => m.key === key); const [label, unit] = labels[key]; return <View key={key} testID={`parent-${key}`} accessibilityLabel={`${label}: ${value(m?.latest)} ${unit}`} style={[s.metric, { backgroundColor: metricArt[key].background, borderTopColor: metricArt[key].accent }]}><ParentIcon symbol={metricArt[key].icon} /><Text style={[s.value, { color: metricArt[key].ink }]}>{value(m?.latest)}</Text><Text style={s.body}>{label}</Text><Text style={s.note}>{unit}</Text></View>; })}
      </View>
      </View>
      {contexts.length > 1 ? <Text style={s.note}>Latest results: {latest?.label}. Contexts are compared separately.</Text> : null}
      <View style={s.card}><Text accessibilityRole="header" style={s.heading}>Progress Summary</Text><Text style={s.body}>{status}</Text></View>
      {report ? <GuardianReportButton data={report} selection={{ development: __DEV__, demoMode: true, role: "guardian" }} /> : null}
      {onSeparate ? <Pressable accessibilityRole="button" onPress={onSeparate} style={s.action}><Text style={s.actionText}>View separate example</Text></Pressable> : null}
      {contexts.map((c, i) => <View key={i} style={s.card}>
        <Text style={s.heading}>{c.label}</Text><Text style={s.note}>{sessions(c.sessions)}</Text>
        {c.metrics.filter(m => c.sessions > 1 && (m.count ?? 0) > 1 && m.first !== null && m.latest !== null).map(m => {
          const [label, unit] = labels[m.key]; const max = m.key === "reading_accuracy" ? 100 : Math.max(1, m.first!, m.latest!);
          return <View key={m.key} testID={`parent-comparison-${i}-${m.key}`} style={s.comparison}>
            <Text style={s.body}>{label}</Text><Text style={s.note}>{unit} · Scale: 0–{value(max)}</Text>
            {(["First", "Latest"] as const).map((label, index) => { const v = index ? m.latest! : m.first!; return <View key={label} accessible accessibilityLabel={`${labels[m.key][0]}: ${label.toLowerCase()} ${value(v)} ${unit}`} style={s.comparison}>
              <Text style={s.body}>{label}: {value(v)} {unit}</Text><View style={s.track}><View style={{ height: 6, width: `${v / max * 100}%`, backgroundColor: index ? palette.teal : palette.primary }} /></View>
            </View>; })}
            {m.sufficient ? <Text style={s.body}>{m.direction === "no_observed_change" ? "No observed change" : m.direction === "increased" ? "Increased" : m.direction === "decreased" ? "Decreased" : "Trend unavailable"}. {m.explanation}</Text> : null}
          </View>;
        })}
      </View>)}
      <View style={s.card}><Text accessibilityRole="header" style={s.heading}>Support Used During Reading</Text>
        {projection?.support_exposures.length ? projection.support_exposures.map((x, i) => <Text key={i} style={s.body}>{x.support_label} · {sessions(x.session_count)}</Text>) : <Text style={s.body}>Support history: Unavailable</Text>}
        <Text style={s.note}>Observed support, not a recommendation.</Text>
      </View>
      <Pressable accessibilityRole="button" accessibilityState={{ expanded: about }} onPress={() => setAbout(!about)} style={s.action}><Text style={s.actionText}>About these results</Text></Pressable>
      {about ? <View style={s.card}>
        {start && end ? <Text style={s.body}>{date(start)} to {date(end)} (end not included)</Text> : null}
        {dashboard ? <Text style={s.body}>{dashboard.title}</Text> : null}
        {contexts.map((c, i) => <View key={i} style={s.comparison}>{c.metrics.map(m => <View key={m.key}><Text style={s.body}>{labels[m.key][0]}: {m.explanation}</Text>{m.detail ? <Text style={s.note}>{m.detail}</Text> : null}<Text style={s.note}>{m.count === undefined ? "Measurement count unavailable" : `${m.count} valid ${m.count === 1 ? "measurement" : "measurements"}`} · {m.missing ?? "Unavailable"} missing</Text></View>)}</View>)}
        {[...new Set(projection?.evidence_limitations ?? dashboard?.limitations ?? [])].map(x => <Text key={x} style={s.body}>{x}</Text>)}
        <Text style={s.body}>{projection?.disclaimer ?? dashboard?.disclaimer}</Text>
        {projection?.support_exposures.map((x, i) => <Text key={i} style={s.note}>{x.description} {date(x.first_observed_at)} to {date(x.latest_observed_at)}</Text>)}
        {projection?.difficulty_history.map((x, i) => <Text key={i} style={s.note}>{date(x.observed_at)}: {x.description}</Text>)}
        {dashboard?.difficultyProgression.map((x, i) => <Text key={i} style={s.note}>{x.explanation}</Text>)}
      </View> : null}
    </>}
    {!available && onSeparate ? <Pressable accessibilityRole="button" onPress={onSeparate} style={s.action}><Text style={s.actionText}>View separate example</Text></Pressable> : null}
  </ScrollView>;
}
/** Original local parent-and-child artwork, never a learner identity. */
function ParentReadingArtwork() {
  return <View testID="parent-reading-art" pointerEvents="none" accessible={false} accessibilityElementsHidden importantForAccessibility="no-hide-descendants" style={s.familyArt}>
    <View style={s.parentBody} /><View style={s.parentHead}><View style={s.faceEyes}><View style={s.eye} /><View style={s.eye} /></View><View style={s.smile} /></View>
    <View style={s.childBody} /><View style={s.childHead}><View style={s.faceEyes}><View style={s.eye} /><View style={s.eye} /></View><View style={s.smile} /></View>
    <Text allowFontScaling={false} style={s.familyBook}>{"\uD83D\uDCD6"}</Text><Text allowFontScaling={false} style={s.star}>{"\u2605"}</Text>
  </View>;
}
function ParentIcon({ symbol }: { symbol: string }) {
  return <View testID="parent-metric-art" pointerEvents="none" accessible={false} accessibilityElementsHidden importantForAccessibility="no-hide-descendants" style={s.iconBadge}><Text allowFontScaling={false} style={s.icon}>{symbol}</Text></View>;
}
const s = StyleSheet.create({
  hero: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 8, padding: 12, borderRadius: 22, backgroundColor: "#EEF5FF", borderWidth: 1, borderColor: "#D7E7FF" },
  headerCopy: { flexGrow: 1, flexShrink: 1, flexBasis: 150, gap: 6 },
  familyArt: { width: 110, height: 84, borderRadius: 18, backgroundColor: "#EAFBF1", marginLeft: "auto" },
  parentHead: { position: "absolute", top: 9, left: 12, width: 34, height: 34, borderRadius: 17, backgroundColor: "#F2C6A4", alignItems: "center" },
  childHead: { position: "absolute", top: 25, right: 14, width: 28, height: 28, borderRadius: 14, backgroundColor: "#B77A50", alignItems: "center" },
  parentBody: { position: "absolute", top: 40, left: 7, width: 46, height: 36, borderRadius: 16, backgroundColor: "#3182F6" },
  childBody: { position: "absolute", top: 51, right: 8, width: 39, height: 25, borderRadius: 13, backgroundColor: "#8B5CF6" },
  faceEyes: { flexDirection: "row", gap: 8, marginTop: 10 }, eye: { width: 3, height: 3, borderRadius: 2, backgroundColor: "#07142B" },
  smile: { width: 10, height: 5, borderBottomWidth: 2, borderColor: "#07142B", borderRadius: 5, marginTop: 3 },
  familyBook: { position: "absolute", bottom: 0, left: 32, fontSize: 32, lineHeight: 40 }, star: { position: "absolute", top: 1, right: 12, fontSize: 14, color: "#FFB020" },
  overview: { padding: 12, gap: 10, borderRadius: 22, backgroundColor: "#FFFFFF", ...softShadow },
  overviewHeading: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 8 },
  iconBadge: { width: 32, height: 32, borderRadius: 10, backgroundColor: "#FFFFFF", alignItems: "center", justifyContent: "center" }, icon: { fontSize: 20, lineHeight: 26 },
  scroll: { backgroundColor: palette.paper }, content: { padding: 16, paddingBottom: 112, gap: 12 },
  title: { color: "#07142B", fontSize: 22, fontWeight: "900" }, heading: { color: "#07142B", fontSize: 17, fontWeight: "800" },
  body: { color: palette.ink, fontSize: 15, lineHeight: 22 }, note: { color: palette.muted, fontSize: 12, lineHeight: 18 }, value: { color: palette.primaryDark, fontSize: 23, fontWeight: "900" },
  metrics: { flexDirection: "row", flexWrap: "wrap", gap: 8 }, metric: { backgroundColor: palette.surface, borderRadius: radii.medium, padding: 12, gap: 6, borderTopWidth: 4, flexBasis: 130, flexGrow: 1 },
  card: { backgroundColor: palette.surface, borderRadius: radii.medium, padding: 12, gap: 8 }, comparison: { gap: 6 }, track: { height: 6, backgroundColor: palette.primarySoft },
  action: { minHeight: 44, padding: 12, borderRadius: radii.small, backgroundColor: palette.primarySoft, justifyContent: "center" }, actionText: { color: palette.primaryDark, fontSize: 15, fontWeight: "700" },
});
