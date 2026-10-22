import { useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { useOptionalPreviewSession } from "../preview/PreviewSession";
import { DemoBanner } from "./DemoBanner";
import { reportStyles as s } from "./LearnerReportLayout";
import { palette } from "../theme";

export type ProgressRow = { label: string; accuracy: number | null; speed: number | null; hesitation: number | null };
export function ReadingProgress({ rows, latest, period, onTips, details, actions, demoMode = true, historyAvailable = true, completedCount, engagement, insufficientHistory = false }: {
  rows: ProgressRow[]; latest: ProgressRow; period: string; onTips?: () => void;
  details?: string[]; actions?: React.ReactNode; demoMode?: boolean; historyAvailable?: boolean; completedCount?: number; engagement?: string | null; insufficientHistory?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const preview = useOptionalPreviewSession();
  const metrics = [
    { key: "accuracy", label: "Reading Accuracy", unit: "%", color: palette.primary },
    { key: "speed", label: "Reading Speed", unit: "WPM", color: palette.teal },
    { key: "hesitation", label: "Hesitation Frequency", unit: "per 100 attempted words", color: palette.orange },
  ] as const;
  const value = (n: number | null) => n === null ? "Not measured" : String(Number(n.toFixed(2)));
  return <ScrollView style={s.scroll} contentContainerStyle={[s.content, { gap: 12, paddingBottom: 96 }]}>
    {demoMode ? <DemoBanner /> : null}
    <Text accessibilityRole="header" style={s.title}>My Analytics</Text>
    <Text style={s.body}>{period}</Text>
    <Text style={s.body}>{rows.length < 2 || insufficientHistory ? "Keep reading to see your progress." : "Explore your reading results below. Different results do not always mean a lasting change."}</Text>
    <Text accessibilityRole="header" style={s.heading}>Reading Performance</Text>
    <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
      {metrics.map(m => <View key={m.key} style={[s.card, { flexGrow: 1, flexBasis: 95, padding: 12, gap: 4, borderTopWidth: 4, borderTopColor: m.color }]}>
        <Text style={s.body}>{m.label}</Text><Text style={[s.heading, { color: m.color }]}>{value(latest[m.key])}</Text><Text style={s.body}>{m.unit}</Text>
      </View>)}
    </View>
    <Text style={s.body}>Cards show the latest available results. Hesitations show a frequency, not a total count.</Text>
    <View style={[s.card, { padding: 14, gap: 6 }]}>
      <Text accessibilityRole="header" style={s.heading}>Reading Behaviour</Text>
      <Text style={s.body}>{completedCount === undefined ? historyAvailable ? `${rows.length} completed sessions` : "Session completion details are unavailable." : `${completedCount} completed sessions`}</Text>
      <Text style={s.body}>Reading time: Not supplied.</Text>
      <Text style={s.body}>Pauses and replays: Not supplied.</Text>
      <Text style={s.body}>Experimental engagement estimate: {engagement ?? "Not available yet"}.</Text>
      <Text style={s.body}>This research estimate is not scientifically validated. It does not measure attention or ability.</Text>
      {preview ? <>
        <Text style={s.body}>Your demo feedback: {preview.feedback.feeling ?? "Not selected"}; {preview.feedback.difficulty ?? "Not selected"}; continue: {preview.feedback.continueReading ?? "Not selected"}.</Text>
        <Text style={s.body}>These answers are separate from the sample measurements.</Text>
      </> : null}
    </View>
    <Text accessibilityRole="header" style={s.heading}>Reading Progress</Text>
    {metrics.map(m => {
      const maximum = m.key === "accuracy" ? 100 : Math.max(1, ...rows.map(r => r[m.key] ?? 0));
      return <View key={m.key} style={[s.card, { padding: 14, gap: 8 }]}>
        <Text accessibilityRole="header" style={s.heading}>{m.label} across {historyAvailable ? "sessions" : "observations"}</Text>
        <Text style={s.body}>{m.unit} · Scale: 0–{value(maximum)}</Text>
        {rows.length === 0 ? <Text style={s.body}>No completed sessions yet.</Text> : rows.map((r, i) => <View key={i} accessibilityLabel={`${r.label}: ${value(r[m.key])} ${m.unit}`} style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
          <Text style={[s.body, { width: 52 }]}>{r.label}</Text>
          <View style={{ flex: 1, height: 14, backgroundColor: palette.primarySoft, borderRadius: 7 }}>
            {r[m.key] !== null ? <View style={{ width: `${Math.min(100, Math.max(0, r[m.key]! / maximum * 100))}%`, height: 14, backgroundColor: m.color, borderRadius: 7 }} /> : null}
          </View><Text style={[s.body, { width: 90, textAlign: "right" }]}>{value(r[m.key])}</Text>
        </View>)}
      </View>;
    })}
    <View style={s.card}><Text accessibilityRole="header" style={s.heading}>Reading History</Text>
      {!historyAvailable ? <Text style={s.body}>This overview has no session-by-session history. Start a demo reading journey to explore completed sessions.</Text> : rows.length === 0 ? <Text style={s.body}>Your completed sessions will appear here.</Text> : rows.map((r, i) => <Text key={i} style={s.body}>{r.label} · Completed · {r.accuracy === null ? "Accuracy not measured" : `${value(r.accuracy)}% accuracy`} · {r.speed === null ? "Speed not measured" : `${value(r.speed)} WPM`}</Text>)}
    </View>
    {onTips ? <Pressable accessibilityRole="button" onPress={onTips} style={s.primaryAction}><Text style={s.primaryLabel}>View Reading Tips</Text></Pressable> : null}
    {actions}
    {details?.length ? <View style={s.card}>
      <Pressable accessibilityRole="button" accessibilityState={{ expanded }} onPress={() => setExpanded(!expanded)} style={s.previewLink}><Text style={s.body}>{expanded ? "Hide result details" : "About these results"}</Text></Pressable>
      {expanded ? details.map((text, i) => <Text key={i} style={s.body}>{text}</Text>) : null}
    </View> : null}
  </ScrollView>;
}
