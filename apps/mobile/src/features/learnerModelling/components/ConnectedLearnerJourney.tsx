import { Pressable, Text, View } from "react-native";
import type { ConnectedArtifact } from "../preview/connectedSessionPreview";
import { useDeveloperTest } from "../preview/DeveloperTestSession";
import type { LearnerDestination } from "../navigation/learnerDestinations";
import { LearnerReadingReportView } from "./LearnerReadingReportView";
import { LearnerProfileView } from "./LearnerProfileView";
import { HomeHero } from "./HomeHero";
import { LocalPreviewLayout } from "./LocalPreviewLayout";
import { ReadingTipsView } from "./ReadingTipsView";
import { ConfirmJourneyReset, ReadingProgress } from "./ReadingProgress";
import { reportStyles as s, type LearnerReportProps } from "./LearnerReportLayout";

/** Normal presentation of the existing validated artifact; no calculations or rules. */
export function ConnectedLearnerJourney({ artifact: a, destination, onNavigate, reportProps }: {
  artifact: ConnectedArtifact; destination: string; onNavigate?: (target: LearnerDestination) => void; reportProps?: LearnerReportProps;
}) {
  const session = useDeveloperTest()!;
  const number = (v: string | null | undefined, scale = 1) => v == null ? null : Number(v) * scale;
  const metric = (key: string, scale = 1) => number(a.metrics.find(m => m.metric_name === key)?.latest_value, scale);
  const format = (v: number | null) => v === null ? "Not measured" : String(Number(v.toFixed(2)));
  const latest = { label: "Latest", accuracy: metric("reading_accuracy", 100), speed: metric("reading_fluency_wpm"), hesitation: metric("hesitation_rate_per_word", 100) };
  const applied = session.replayIndex === null ? "Applied: imported sample results" : `Applied scenario: Sample ${session.replayIndex}`;
  if (destination === "report") return <LearnerReadingReportView allowSaved={Boolean(reportProps?.demoMode && reportProps.dashboard.role === "learner")}
    periodStart={a.reportingStartUtc} periodEnd={a.reportingEndUtc}
    metrics={[{ label: "Completed Sessions", value: String(a.includedSessionCount) }, { label: "Reading Accuracy (%)", value: latest.accuracy === null ? "Unavailable" : `${format(latest.accuracy)}%` }, { label: "Reading Speed (WPM)", value: latest.speed === null ? "Unavailable" : `${format(latest.speed)} WPM` }, { label: "Hesitations per 100 attempted words", value: latest.hesitation === null ? "Unavailable" : format(latest.hesitation) }]}
    currentSummary={<View style={{ gap: 10 }}>{a.reportStatements.map(text => <Text key={text} style={s.body}>{text}</Text>)}</View>}
    currentDetails={<Text style={s.body}>{a.disclaimer}</Text>} />;
  if (destination === "suggestions") return <ReadingTipsView
    disclosure={session.source === "laptop" ? "Synthetic Sample Data \u00b7 Calculated on laptop" : "Demo \u00b7 Fictional data"}
    title={a.recommendation?.action ?? "Keep reading to find a helpful tip."}
    metrics={[{ label: "Completed Sessions", value: String(a.includedSessionCount) },
      ...([{ key: "reading_accuracy", label: "Reading Accuracy (%)", scale: 100, unit: "%" }, { key: "reading_fluency_wpm", label: "Reading Speed (WPM)", scale: 1, unit: " WPM" }, { key: "hesitation_rate_per_word", label: "Hesitations per 100 attempted words", scale: 100, unit: "" }] as const).map(item => {
        const supplied = a.metrics.find(m => m.metric_name === item.key);
        const value = metric(item.key, item.scale);
        return { label: item.label, value: value === null ? "Unavailable" : `${format(value)}${item.unit}`, evidence: supplied?.evidence_state, explanation: supplied?.explanation };
      })]}
    reasons={[...a.recommendationExplanation, ...(a.recommendation?.reasons ?? [])]}
    periodLabel={`${a.reportingStartUtc.slice(0, 10)} to ${a.reportingEndUtc.slice(0, 10)}`} evidenceState={a.recommendation?.evidence_state} current={a.recommendation?.current ?? undefined}
    limitations={[...(a.recommendation?.limitations ?? []), ...(a.recommendation ? [a.recommendation.disclaimer] : []), a.disclaimer]}
    unavailableReason={!a.recommendation ? "There are not enough comparable reading results to recommend a change yet." : undefined}
    nextSteps={[...(a.recommendation?.proposed ?? []), a.recommendation?.manual_control_prevents_adjustment ? "Manual control keeps support unchanged." : "Review this tip with a parent or teacher. No settings are changed."]}
    onReport={() => onNavigate?.("report")} />;
  if (destination === "profile") return <LearnerProfileView demoMode sessions={a.includedSessionCount} accuracy={latest.accuracy === null ? "Unavailable" : `${format(latest.accuracy)}%`} speed={latest.speed === null ? "Unavailable" : `${format(latest.speed)} WPM`}
    history={a.history.map(h => ({ id: String(h.sequence), label: `Sample ${h.sequence}`, date: new Date(h.recordedAt).toLocaleDateString("en-GB", { timeZone: "UTC" }), accuracy: h.accuracy === null ? "Unavailable" : `${format(number(h.accuracy, 100))}%`, speed: h.wpm === null ? "Unavailable" : `${format(number(h.wpm))} WPM`, hesitation: h.hesitation === null ? "Unavailable" : `${format(number(h.hesitation, 100))} per 100 attempted words` }))}
    onAnalytics={() => onNavigate?.("progress")} onSettings={() => onNavigate?.("settings")}
    details={<><Text style={s.period}>{applied}</Text><Text style={s.body}>Level: {a.context.tier}. Activity: {a.context.task.replaceAll("_", " ")}.</Text></>} />;
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
  return <LocalPreviewLayout title={destination === "suggestions" ? "My Reading Tips" : destination === "report" ? "My Reading Report" : "Reading Home"}
    disclosure="" introduction="" homeHeader={destination === "home" ? <HomeHero sessions={a.includedSessionCount} accuracy={latest.accuracy === null ? "Not measured" : `${format(latest.accuracy)}%`} speed={format(latest.speed)} onStart={() => onNavigate?.("test")} /> : undefined}>
    <Text style={s.period}>{applied}</Text>
  </LocalPreviewLayout>;
}
