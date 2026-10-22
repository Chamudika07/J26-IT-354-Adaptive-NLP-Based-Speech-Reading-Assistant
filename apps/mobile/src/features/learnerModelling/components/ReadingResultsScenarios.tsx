import { useEffect, useState } from "react";
import { Pressable, Text, View } from "react-native";
import { selectConnectedReplay, connectedReplayLength } from "../preview/connectedSessionPreview";
import { useOptionalPreviewSession } from "../preview/PreviewSession";
import { useDeveloperTest } from "../preview/DeveloperTestSession";
import { PreviewChoiceGroup } from "./PreviewChoiceGroup";
import { reportStyles as s } from "./LearnerReportLayout";

export function ReadingResultsScenarios({ onApplied }: { onApplied?: () => void }) {
  const session = useDeveloperTest();
  const choices = useOptionalPreviewSession();
  const [details, setDetails] = useState(false);
  const [selected, setSelected] = useState(session?.replayIndex ?? 0);
  const cancel = session?.cancelCalculation;
  useEffect(() => () => cancel?.(), [cancel]);
  if (!session || !__DEV__) return null;
  const sample = selectConnectedReplay({ index: selected, development: true, demoMode: true, role: "learner" });
  const display = (key: string, scale = 1) => {
    const value = sample?.metrics.find(m => m.metric_name === key)?.latest_value;
    return value == null ? "Not measured" : String(Number((Number(value) * scale).toFixed(2)));
  };
  return <View style={s.card}>
    <PreviewChoiceGroup label="Results source" selected={session.source} onSelect={value => session.chooseSource(value as "offline" | "laptop")}
      choices={[{ value: "laptop", label: "Connected sample (laptop)" }, { value: "offline", label: "Offline examples" }]} />
    {session.source === "laptop" && !session.connectedAvailable ? <Text style={s.body}>Sign in, then choose Open PP1 Sample Journey to connect.</Text> : null}
    {session.calculationError ? <><Text accessibilityRole="alert" style={s.body}>{session.calculationError}</Text>
      <Pressable accessibilityRole="button" onPress={() => session.chooseSource("offline")} style={s.previewLink}><Text style={s.body}>Use offline examples</Text></Pressable></> : null}
    {session.calculating ? <><Text accessibilityLiveRegion="polite">Getting sample results?</Text><Pressable accessibilityRole="button" onPress={session.cancelCalculation}><Text>Cancel calculation</Text></Pressable></> : null}
    <Text style={s.body}>See how these reading results affect your progress.</Text>
    <PreviewChoiceGroup label="Sample scenario" selected={String(selected)} onSelect={value => { session.cancelCalculation(); setSelected(Number(value)); }}
      choices={Array.from({ length: connectedReplayLength }, (_, value) => ({ value: String(value), label: value === 0 ? "Before reading" : `Sample ${value}` }))} />
    {sample ? <>
      <Text style={s.period}>{sample.includedSessionCount} completed sample sessions</Text>
      <Text style={s.body}>Reading Accuracy (%): {display("reading_accuracy", 100)}</Text>
      <Text style={s.body}>Reading Speed (WPM): {display("reading_fluency_wpm")}</Text>
      <Text style={s.body}>Hesitations per 100 attempted words: {display("hesitation_rate_per_word", 100)}</Text>
      <Pressable accessibilityRole="button" accessibilityState={{ expanded: details }} onPress={() => setDetails(!details)} style={s.previewLink}><Text style={s.body}>Session Details</Text></Pressable>
      {details ? <>
      <Text style={s.body}>Reading time: Not provided in this sample result.</Text>
      <Text style={s.body}>Pause count and duration: Not provided in this sample result.</Text>
      <Text style={s.body}>Replays: Not provided in this sample result.</Text>
      <Text style={s.body}>Session completion: {sample.history.length ? "Completed sessions only" : "No completed sessions"}.</Text>
      <Text style={s.body}>Latest session: {sample.history.at(-1) ? new Date(sample.history.at(-1)!.recordedAt).toLocaleDateString("en-GB", { timeZone: "UTC" }) : "No completed session"}.</Text>
      </> : null}
      <Text style={s.body}>Reading activity: {sample.context.task.replaceAll("_", " ")}. Level: {sample.context.tier}. Support: {sample.context.mode.replaceAll("_", " ")}.</Text>
      <Text style={s.body}>Each sample includes earlier sessions. Switching samples replaces your selection.</Text>
    </> : <Text accessibilityRole="alert" style={s.body}>This sample is unavailable. Choose another example.</Text>}
    {details && choices ? <View style={s.previewLink}>
      <Text style={s.heading}>Your demo choices</Text>
      <Text style={s.body}>Font: {({ comfortable: "Comfortable", large: "Large", extraLarge: "Extra large" })[choices.settings.font]}. Spacing: {choices.settings.spacing === "wide" ? "Wide" : "Comfortable"}. Highlighting: {choices.settings.highlight ? "On" : "Off"}.</Text>
      <Text style={s.body}>Feedback: {choices.feedback.feeling ?? "Not selected"}; {choices.feedback.difficulty ?? "Not selected"}; continue: {choices.feedback.continueReading ?? "Not selected"}.</Text>
      <Text style={s.body}>These device-only choices do not change the sample calculations or support decisions.</Text>
    </View> : null}
    {session.source === "laptop" ? <>
      <Text style={s.body}>Synthetic Sample Data. Saving Sample {selected} adds samples 1?{selected}. Earlier saved sessions stay unchanged.</Text>
      {session.savedMessage ? <Text accessibilityLiveRegion="polite">{session.savedMessage}</Text> : null}
      <Pressable accessibilityRole="button" disabled={session.calculating || !session.connectedAvailable} style={s.primaryAction} onPress={() => { void session.savedProgress(selected).then(ok => { if (ok) onApplied?.(); }); }}><Text style={s.primaryLabel}>Save Sample Progress</Text></Pressable>
      <Pressable accessibilityRole="button" disabled={session.calculating || !session.connectedAvailable} style={s.previewLink} onPress={() => { void session.savedProgress().then(ok => { if (ok) onApplied?.(); }); }}><Text style={s.body}>Refresh Saved Progress</Text></Pressable>
      <Text style={s.body}>After reopening the app, sign in and refresh to load saved sessions. Cancelling may leave a completed save; retrying is safe.</Text>
    </> : <Pressable accessibilityRole="button" disabled={!sample || session.busy || session.calculating} accessibilityState={{ disabled: !sample || session.busy || session.calculating }} onPress={() => { if (session.source === "offline") { session.replay(selected); onApplied?.(); } else { void session.applyScenario(selected).then(applied => { if (applied) onApplied?.(); }); } }} style={s.primaryAction}><Text style={s.primaryLabel}>Update My Progress</Text></Pressable>}
    <Text style={s.body}>Only these sample values can be applied here. Saved AI reports and PDFs stay unchanged.</Text>
  </View>;
}
