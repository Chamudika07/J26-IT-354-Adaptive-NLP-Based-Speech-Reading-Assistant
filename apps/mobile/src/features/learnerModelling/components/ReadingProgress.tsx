import { useState } from "react";
import { Alert, Pressable, ScrollView, Text, View } from "react-native";
import { useOptionalPreviewSession } from "../preview/PreviewSession";
import { reportStyles as s } from "./LearnerReportLayout";
import { palette } from "../theme";

export type ProgressRow = { label: string; accuracy: number | null; speed: number | null; hesitation: number | null };
export function ReadingProgress({ rows, latest, period, onTips, details, actions, demoMode = true, historyAvailable = true, completedCount, engagement, insufficientHistory = false }: {
  rows: ProgressRow[]; latest: ProgressRow; period: string; onTips?: () => void;
  details?: string[]; actions?: React.ReactNode; demoMode?: boolean; historyAvailable?: boolean; completedCount?: number; engagement?: string | null; insufficientHistory?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const [behaviour, setBehaviour] = useState(false);
  const [history, setHistory] = useState(false);
  const preview = useOptionalPreviewSession();
  const metrics = [
    { key: "accuracy", label: "Reading Accuracy", unit: "%", color: palette.primary },
    { key: "speed", label: "Reading Speed", unit: "WPM", color: palette.teal },
    { key: "hesitation", label: "Hesitation Frequency", unit: "per 100 attempted words", color: palette.orange },
  ] as const;
  const value = (n: number | null) => n === null ? "Unavailable" : String(Number(n.toFixed(2)));
  return <ScrollView style={s.scroll} contentContainerStyle={[s.content, { gap: 12, paddingBottom: 96 }]}>
    {demoMode ? <Text style={{ color: palette.muted, fontSize: 12 }}>{"Demo \u00b7 Fictional data"}</Text> : null}
    <Text accessibilityRole="header" style={[s.title, { fontSize: 22 }]}>My Reading Analytics</Text>
    <Text style={s.body}>{rows.length < 2 || insufficientHistory ? "Keep reading to see your progress." : "Explore your reading results below. Different results do not always mean a lasting change."}</Text>
    <Text accessibilityRole="header" style={s.heading}>Reading Performance</Text>
    <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
      <View style={[s.card, { flexGrow: 1, flexBasis: 120, padding: 10, gap: 4 }]}><Text style={s.body}>Completed Sessions</Text><Text style={s.heading}>{completedCount ?? (historyAvailable ? rows.length : "Unavailable")}</Text></View>
      {metrics.map(m => <View key={m.key} style={[s.card, { flexGrow: 1, flexBasis: 120, padding: 10, gap: 4, borderTopWidth: 4, borderTopColor: m.color }]}>
        <Text style={s.body}>{m.label}</Text><Text style={[s.heading, { color: m.color }]}>{value(latest[m.key])}</Text><Text style={s.body}>{m.unit}</Text>
      </View>)}
    </View>
    {onTips ? <Pressable accessibilityRole="button" onPress={onTips} style={[s.primaryAction, { minHeight: 44 }]}><Text style={s.primaryLabel}>View Reading Tips</Text></Pressable> : null}
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
      return <View key={m.key} style={[s.card, { padding: 14, gap: 8 }]}>
        <Text accessibilityRole="header" style={s.heading}>{m.label} across {historyAvailable ? "sessions" : "observations"}</Text>
        <Text style={s.body}>{m.unit} · Scale: {rows.some(r => r[m.key] !== null) ? `0–${value(maximum)}` : "Unavailable"}</Text>
        {rows.length === 0 ? <Text style={s.body}>No completed sessions yet.</Text> : <ScrollView horizontal showsHorizontalScrollIndicator contentContainerStyle={{ gap: 8 }}>
          {rows.map((r, i) => <View key={i} accessible accessibilityLabel={`${r.label}: ${value(r[m.key])} ${m.unit}`} style={{ width: 68, gap: 4, alignItems: "center" }}>
            <Text style={[s.body, { textAlign: "center" }]}>{value(r[m.key])}</Text>
            <View style={{ height: 64, width: 24, justifyContent: "flex-end", backgroundColor: palette.primarySoft, borderBottomWidth: 1, borderBottomColor: palette.muted }}>
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

export function ConfirmJourneyReset({ onReset }: { onReset: () => void }) {
  return <Pressable accessibilityRole="button" onPress={() => Alert.alert("Reset Journey?", "Return to Before Reading? Saved sample sessions stay in the database.", [{ text: "Cancel", style: "cancel" }, { text: "Reset Journey", style: "destructive", onPress: onReset }])} style={[s.previewLink, { minHeight: 44 }]}><Text style={s.body}>Reset Journey</Text></Pressable>;
}
