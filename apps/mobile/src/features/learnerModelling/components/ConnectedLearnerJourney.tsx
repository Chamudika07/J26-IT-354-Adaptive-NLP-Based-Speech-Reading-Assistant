import { useState } from "react";
import { Pressable, Text, View } from "react-native";
import type { ConnectedArtifact } from "../preview/connectedSessionPreview";
import { useDeveloperTest } from "../preview/DeveloperTestSession";
import type { LearnerDestination } from "../navigation/learnerDestinations";
import { AIProgressReportScreen } from "../screens/AIProgressReportScreen";
import { DemoLearnerCard, DemoPreferencesCard } from "./DemoLearnerCard";
import { HomeHero } from "./HomeHero";
import { LocalPreviewLayout } from "./LocalPreviewLayout";
import { ConfirmJourneyReset, ReadingProgress } from "./ReadingProgress";
import { reportStyles as s, type LearnerReportProps } from "./LearnerReportLayout";

/** Normal presentation of the existing validated artifact; no calculations or rules. */
export function ConnectedLearnerJourney({ artifact: a, destination, onNavigate, reportProps }: {
  artifact: ConnectedArtifact; destination: string; onNavigate?: (target: LearnerDestination) => void; reportProps?: LearnerReportProps;
}) {
  const session = useDeveloperTest()!;
  const [why, setWhy] = useState(false);
  const [summary, setSummary] = useState(false);
  const [saved, setSaved] = useState(false);
  const number = (v: string | null | undefined, scale = 1) => v == null ? null : Number(v) * scale;
  const metric = (key: string, scale = 1) => number(a.metrics.find(m => m.metric_name === key)?.latest_value, scale);
  const format = (v: number | null) => v === null ? "Not measured" : String(Number(v.toFixed(2)));
  const latest = { label: "Latest", accuracy: metric("reading_accuracy", 100), speed: metric("reading_fluency_wpm"), hesitation: metric("hesitation_rate_per_word", 100) };
  const applied = session.replayIndex === null ? "Applied: imported sample results" : `Applied scenario: Sample ${session.replayIndex}`;
  const action = (label: string, target: LearnerDestination, primary = true) => <Pressable accessibilityRole="button" onPress={() => onNavigate?.(target)} style={primary ? s.primaryAction : s.previewLink}><Text style={primary ? s.primaryLabel : s.body}>{label}</Text></Pressable>;
  if (saved && reportProps) return <View style={{ flex: 1 }}>
    <Pressable accessibilityRole="button" onPress={() => setSaved(false)} style={s.previewLink}><Text style={s.body}>Back to Current Reading Summary</Text></Pressable>
    <AIProgressReportScreen {...reportProps} initialSaved />
  </View>;
  if (destination === "progress") return <ReadingProgress rows={a.history.map(h => ({ label: `S${h.sequence}`, accuracy: number(h.accuracy, 100), speed: number(h.wpm), hesitation: number(h.hesitation, 100) }))}
    latest={latest} completedCount={a.includedSessionCount} engagement={a.history.at(-1)?.experimentalEngagement}
    insufficientHistory={a.metrics.some(m => m.change_direction === "insufficient_evidence")}
    period={`${applied} - ${a.includedSessionCount} completed sample sessions - ${a.reportingStartUtc.slice(0, 10)} to ${a.reportingEndUtc.slice(0, 10)}`}
    onTips={() => onNavigate?.("suggestions")} details={[...a.metrics.map(m => m.explanation), a.disclaimer]}
    actions={<View style={{ gap: 8 }}>
      {session.replayIndex !== null ? <>
        <Pressable accessibilityRole="button" disabled={session.replayIndex + 1 >= session.replayLength} accessibilityState={{ disabled: session.replayIndex + 1 >= session.replayLength }} onPress={() => session.replay(session.replayIndex! + 1)} style={s.previewLink}><Text style={s.body}>Add Next Sample</Text></Pressable>
        <ConfirmJourneyReset onReset={() => session.replay(0)} />
      </> : null}
    </View>} />;
  return <LocalPreviewLayout title={destination === "profile" ? "My Profile" : destination === "suggestions" ? "My Reading Tips" : destination === "report" ? "My Reading Report" : "Reading Home"}
    disclosure="" introduction="" homeHeader={destination === "home" ? <HomeHero sessions={a.includedSessionCount} accuracy={latest.accuracy === null ? "Not measured" : `${format(latest.accuracy)}%`} speed={format(latest.speed)} onStart={() => onNavigate?.("test")} /> : undefined}>
    {destination === "report" && session.source === "laptop" ? <Text style={s.period}>{"Synthetic Sample Data \u00b7 Calculated on laptop"}</Text> : null}
    {destination === "suggestions" ? <View style={s.card}>
      <Text accessibilityRole="header" style={s.heading}>{a.recommendation?.action ?? "Keep reading to find a helpful tip."}</Text>
      <Text style={s.period}>ADVISORY ONLY</Text>
      <Pressable accessibilityRole="button" accessibilityState={{ expanded: why }} onPress={() => setWhy(!why)} style={s.previewLink}><Text style={s.body}>Why This Tip?</Text></Pressable>
      <Text style={s.body}>{a.recommendation ? a.recommendationExplanation[0] : "There are not enough comparable reading results to recommend a change yet."}</Text>
      {why ? <>
        {a.recommendationExplanation.slice(a.recommendation ? 1 : 0).map(t => <Text key={t} style={s.body}>{t}</Text>)}
        <Text style={s.body}>Current support: {a.recommendation?.current ?? "Not available"}</Text>
        {a.recommendation?.proposed.map(t => <Text key={t} style={s.body}>{t}</Text>)}
        {a.recommendation?.limitations.map(t => <Text key={t} style={s.body}>{t}</Text>)}
      </> : null}
      <Text style={s.body}>{a.recommendation?.manual_control_prevents_adjustment ? "Manual control keeps support unchanged." : "Review this tip with a parent or teacher. No settings are changed."}</Text>
    </View> : null}
    <Text style={s.period}>{applied}</Text>
    {destination === "profile" ? <>
      <DemoLearnerCard editable />
      <View style={s.card}>
        <Text accessibilityRole="header" style={s.heading}>Latest Reading Results</Text>
        <Text style={s.body}>Accuracy: {format(latest.accuracy)}{latest.accuracy === null ? "" : "%"} · Speed: {format(latest.speed)} WPM</Text>
        <Text style={s.body}>Hesitation frequency: {format(latest.hesitation)} per 100 attempted words</Text>
        <Text style={s.body}>Level: {a.context.tier}. Activity: {a.context.task.replaceAll("_", " ")}.</Text>
        <Text style={s.body}>{a.includedSessionCount} completed sessions. These observations do not verify your identity or ability.</Text>
      </View>
      <DemoPreferencesCard />
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>{action("Reading Settings", "settings", false)}{action("Reading Feedback", "feedback", false)}</View>
      <View style={s.card}><Text accessibilityRole="header" style={s.heading}>Reading History</Text>
        {a.history.length ? a.history.map(h => <Text key={h.sequence} style={s.body}>Sample {h.sequence} · {h.recordedAt.slice(0, 10)} · Completed</Text>) : <Text style={s.body}>No completed sessions yet.</Text>}
      </View>
      {action("Next: My Analytics", "progress")}
    </> : null}
    {destination === "suggestions" ? action("Next: My Reading Report", "report") : null}
    {destination === "report" ? <>
      <View style={s.card}>
        <Text accessibilityRole="header" style={s.heading}>Current Reading Summary</Text>
        <Text style={s.body}>Uses your selected sample results. This summary is not AI-written.</Text>
        <Pressable accessibilityRole="button" accessibilityState={{ expanded: summary }} onPress={() => setSummary(!summary)} style={s.primaryAction}><Text style={s.primaryLabel}>Read Current Summary</Text></Pressable>
        {summary ? a.reportStatements.map(t => <Text key={t} style={s.body}>{t}</Text>) : null}
      </View>
      <View style={s.card}>
        <Text accessibilityRole="header" style={s.heading}>Saved AI Reading Report</Text>
        <Text style={s.body}>Created earlier from separate sample data. It does not use this journey.</Text>
        {reportProps ? <Pressable accessibilityRole="button" onPress={() => setSaved(true)} style={s.previewLink}><Text style={s.body}>Open Saved AI Report</Text></Pressable> : null}
      </View>
    </> : null}
  </LocalPreviewLayout>;
}
