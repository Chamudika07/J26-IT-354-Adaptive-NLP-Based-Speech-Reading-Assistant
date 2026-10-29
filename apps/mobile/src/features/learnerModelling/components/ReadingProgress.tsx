import { useState } from "react";
import { Alert, Pressable, ScrollView, StyleSheet, Text, useWindowDimensions, View } from "react-native";
import { useOptionalPreviewSession } from "../preview/PreviewSession";
import { reportStyles as s } from "./LearnerReportLayout";
import { palette, radii } from "../theme";
import { ReadingBuddyIllustration } from "./ReadingBuddyIllustration";

// Analytics-only styling; metric accents match the Reading Results cards.
const analytics = { ink: "#07142B", muted: "#465B73", blue: "#3182F6", green: "#22C55E", purple: "#8B5CF6", teal: "#14B8A6", sky: "#EEF5FF", mint: "#EAFBF1", lavender: "#F4EFFF", tealSoft: "#E7F8F5" };

export type ProgressRow = { label: string; accuracy: number | null; speed: number | null; hesitation: number | null };
export function ReadingProgress({ rows, latest, period, onTips, details, actions, demoMode = true, historyAvailable = true, completedCount, engagement, insufficientHistory = false }: {
  rows: ProgressRow[]; latest: ProgressRow; period: string; onTips?: () => void;
  details?: string[]; actions?: React.ReactNode; demoMode?: boolean; historyAvailable?: boolean; completedCount?: number; engagement?: string | null; insufficientHistory?: boolean;
}) {
  const { width, fontScale } = useWindowDimensions();
  const stacked = width < 360 || fontScale > 1.2;
  const [expanded, setExpanded] = useState(false);
  const [behaviour, setBehaviour] = useState(false);
  const [history, setHistory] = useState(false);
  const preview = useOptionalPreviewSession();
  const metrics = [
    { key: "accuracy", label: "Reading Accuracy", unit: "%", color: "#153E75", accent: analytics.blue, background: analytics.sky, icon: "\uD83C\uDFAF" },
    { key: "speed", label: "Reading Speed", unit: "WPM", color: "#166534", accent: analytics.green, background: analytics.mint, icon: "\u23F1\uFE0F" },
    { key: "hesitation", label: "Hesitation Frequency", unit: "per 100 attempted words", color: "#5B21B6", accent: analytics.purple, background: analytics.lavender, icon: "\u23F8\uFE0F" },
  ] as const;
  const value = (n: number | null) => n === null ? "Unavailable" : String(Number(n.toFixed(2)));
  return <ScrollView style={s.scroll} contentContainerStyle={[s.content, { gap: 12, paddingBottom: 96 }]}>
    {demoMode ? <Text style={{ color: palette.muted, fontSize: 12 }}>{"Demo \u00b7 Fictional data"}</Text> : null}
    <View style={styles.header}>
      <Text accessibilityRole="header" style={[s.title, styles.heading]}>My Reading Analytics</Text>
      <View testID="analytics-reading-illustration" pointerEvents="none" accessible={false} accessibilityElementsHidden importantForAccessibility="no-hide-descendants" style={styles.illustration}><ReadingBuddyIllustration compact /></View>
    </View>
    <Text style={s.body}>{rows.length < 2 || insufficientHistory ? "Keep reading to see your progress." : "Explore your reading results below. Different results do not always mean a lasting change."}</Text>
    <Text accessibilityRole="header" style={s.heading}>Reading Performance</Text>
    <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
      <View testID="analytics-sessions" accessible accessibilityLabel={`Completed Sessions: ${completedCount ?? (historyAvailable ? rows.length : "Unavailable")}`} style={[s.card, styles.metric, stacked && styles.stackedMetric, { borderTopColor: analytics.teal, backgroundColor: analytics.tealSoft }]}><View style={styles.metricTitle}><AnalyticsIcon symbol={"\uD83D\uDCDA"} /><Text style={styles.label}>Completed Sessions</Text></View><Text style={[styles.value, { color: "#115E59" }]}>{completedCount ?? (historyAvailable ? rows.length : "Unavailable")}</Text></View>
      {metrics.map(m => <View key={m.key} testID={`analytics-${m.key}`} accessible accessibilityLabel={`${m.label}: ${value(latest[m.key])}${latest[m.key] === null ? "" : ` ${m.unit}`}`} style={[s.card, styles.metric, stacked && styles.stackedMetric, { borderTopColor: m.accent, backgroundColor: m.background }]}>
        <View style={styles.metricTitle}><AnalyticsIcon symbol={m.icon} /><Text style={styles.label}>{m.label}</Text></View><Text style={[styles.value, { color: m.color }]}>{value(latest[m.key])}</Text><Text style={styles.unit}>{m.unit}</Text>
      </View>)}
    </View>
    {onTips ? <Pressable accessibilityRole="button" onPress={onTips} style={[s.primaryAction, styles.tips]}><Text style={[s.primaryLabel, { color: "#FFFFFF" }]}>View Reading Tips</Text></Pressable> : null}
    {actions}
    <View style={[s.card, { padding: 14, gap: 6 }]}>
      <Text accessibilityRole="header" style={s.heading}>Reading Behaviour</Text>
      <Pressable accessibilityRole="button" accessibilityState={{ expanded: behaviour }} onPress={() => setBehaviour(!behaviour)} style={[s.previewLink, { minHeight: 44 }]}><Text style={s.body}>{behaviour ? "Hide Behaviour Details" : "View Behaviour Details"}</Text></Pressable>
      {behaviour ? <>
      <Text style={s.body}>{completedCount === undefined ? historyAvailable ? `${rows.length} completed sessions` : "Session completion details are unavailable." : `${completedCount} completed sessions`}</Text>
      <Text style={s.body}>Reading time: Unavailable.</Text>
      <Text style={s.body}>Pauses and replays: Unavailable.</Text>
      <Text style={s.body}>Experimental engagement estimate: {engagement ?? "Unavailable"}.</Text>
      <Text style={s.body}>This research estimate is not scientifically validated. It does not measure attention or ability.</Text>
      {preview ? <>
        <Text style={s.body}>Your demo feedback: {preview.feedback.feeling ?? "Not selected"}; {preview.feedback.difficulty ?? "Not selected"}; continue: {preview.feedback.continueReading ?? "Not selected"}.</Text>
        <Text style={s.body}>These answers are separate from the sample measurements.</Text>
      </> : null}
      </> : null}
    </View>
    <Text accessibilityRole="header" style={s.heading}>Reading Progress</Text>
    {metrics.map(m => {
      const maximum = m.key === "accuracy" ? 100 : Math.max(1, ...rows.map(r => r[m.key] ?? 0));
      return <View key={m.key} testID={`trend-${m.key}`} style={[s.card, styles.chart, { borderTopColor: m.accent }]}>
        <Text accessibilityRole="header" style={[s.heading, { color: analytics.ink }]}>{m.label} across {historyAvailable ? "sessions" : "observations"}</Text>
        <Text style={styles.unit}>{m.unit} · Scale: {rows.some(r => r[m.key] !== null) ? `0–${value(maximum)}` : "Unavailable"}</Text>
        {rows.length === 0 ? <Text style={s.body}>No completed sessions yet.</Text> : <ScrollView horizontal showsHorizontalScrollIndicator contentContainerStyle={{ gap: 12, paddingBottom: 8 }}>
          {rows.map((r, i) => <View key={i} accessible accessibilityLabel={`${r.label}: ${value(r[m.key])} ${m.unit}`} style={{ width: fontScale > 1.2 ? 104 : 76, gap: 6, alignItems: "center" }}>
            <Text style={[s.body, { textAlign: "center" }]}>{value(r[m.key])}</Text>
            <View style={{ height: 64, width: 24, justifyContent: "flex-end", backgroundColor: m.background, borderTopLeftRadius: 6, borderTopRightRadius: 6, overflow: "hidden", borderBottomWidth: 1, borderBottomColor: analytics.muted }}>
              {r[m.key] !== null ? <View testID={`bar-${m.key}-${i}`} style={{ height: `${Math.min(100, Math.max(0, r[m.key]! / maximum * 100))}%`, backgroundColor: m.color }} /> : null}
            </View><Text style={s.body}>{r.label}</Text>
          </View>)}
        </ScrollView>}
      </View>;
    })}
    <View style={s.card}><Text accessibilityRole="header" style={s.heading}>Reading History</Text>
      <Pressable accessibilityRole="button" accessibilityState={{ expanded: history }} onPress={() => setHistory(!history)} style={[s.previewLink, { minHeight: 44 }]}><Text style={s.body}>{history ? "Hide Reading History" : "View Reading History"}</Text></Pressable>
      {history ? <>
      {!historyAvailable ? <Text style={s.body}>This overview has no session-by-session history. Start a demo reading journey to explore completed sessions.</Text> : rows.length === 0 ? <Text style={s.body}>Your completed sessions will appear here.</Text> : rows.map((r, i) => <Text key={i} style={s.body}>{r.label} · Completed · {r.accuracy === null ? "Accuracy Unavailable" : `${value(r.accuracy)}% accuracy`} · {r.speed === null ? "Speed Unavailable" : `${value(r.speed)} WPM`}{" \u00b7 "}{value(r.hesitation)} hesitations per 100 attempted words</Text>)}
      </> : null}
    </View>
    {details?.length ? <View style={s.card}>
      <Pressable accessibilityRole="button" accessibilityState={{ expanded }} onPress={() => setExpanded(!expanded)} style={[s.previewLink, { minHeight: 44 }]}><Text style={s.body}>{expanded ? "Hide result details" : "About these results"}</Text></Pressable>
      {expanded ? <><Text style={s.body}>{period}</Text>{details.map((text, i) => <Text key={i} style={s.body}>{text}</Text>)}</> : null}
    </View> : null}
  </ScrollView>;
}

function AnalyticsIcon({ symbol }: { symbol: string }) {
  return <View testID="analytics-metric-icon" pointerEvents="none" accessible={false} accessibilityElementsHidden importantForAccessibility="no-hide-descendants" style={styles.iconBadge}><Text allowFontScaling={false} style={styles.icon}>{symbol}</Text></View>;
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 8 },
  heading: { fontSize: 22, flexGrow: 1, flexShrink: 1, flexBasis: 180 },
  illustration: { width: 94, height: 84 },
  iconBadge: { width: 32, height: 32, borderRadius: 10, backgroundColor: "#FFFFFF", alignItems: "center", justifyContent: "center" },
  metric: { flexGrow: 1, flexBasis: 120, padding: 12, gap: 6, borderTopWidth: 4, borderRadius: radii.medium },
  stackedMetric: { flexBasis: "100%" },
  metricTitle: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 6 },
  icon: { fontSize: 20, lineHeight: 26 },
  label: { color: analytics.ink, fontSize: 14, lineHeight: 20, fontWeight: "700" },
  value: { fontSize: 24, fontWeight: "900" },
  unit: { color: analytics.muted, fontSize: 13, lineHeight: 19 },
  chart: { padding: 14, gap: 10, borderRadius: radii.medium, borderTopWidth: 3 },
  tips: { minHeight: 48, backgroundColor: "#1D4ED8", borderRadius: radii.medium },
});

export function ConfirmJourneyReset({ onReset }: { onReset: () => void }) {
  return <Pressable accessibilityRole="button" onPress={() => Alert.alert("Reset Journey?", "Return to Before Reading? Saved sample sessions stay in the database.", [{ text: "Cancel", style: "cancel" }, { text: "Reset Journey", style: "destructive", onPress: onReset }])} style={[s.previewLink, { minHeight: 44 }]}><Text style={s.body}>Reset Journey</Text></Pressable>;
}
