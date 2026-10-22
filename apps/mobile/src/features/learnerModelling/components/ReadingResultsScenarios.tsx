import { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, useWindowDimensions, View } from "react-native";
import { selectConnectedReplay, connectedReplayLength } from "../preview/connectedSessionPreview";
import { useOptionalPreviewSession } from "../preview/PreviewSession";
import { useDeveloperTest } from "../preview/DeveloperTestSession";
import { radii } from "../theme";

// Reading Results only; keep the rest of the application theme unchanged.
const colors = { blue: "#3182F6", green: "#22C55E", purple: "#8B5CF6", ink: "#07142B", muted: "#465B73", white: "#FFFFFF", outline: "#D7E7FF", sky: "#EEF5FF", mint: "#EAFBF1", lavender: "#F4EFFF", action: "#1D4ED8" };

export function ReadingResultsScenarios({ onApplied }: { onApplied?: () => void }) {
  const session = useDeveloperTest();
  const { width, fontScale } = useWindowDimensions();
  const stacked = width < 360 || fontScale > 1.2;
  const choices = useOptionalPreviewSession();
  const [details, setDetails] = useState(false);
  const [more, setMore] = useState(false);
  const [selected, setSelected] = useState(session?.replayIndex ?? 0);
  const cancel = session?.cancelCalculation;
  useEffect(() => () => cancel?.(), [cancel]);
  if (!session || !__DEV__) return null;
  const sample = selectConnectedReplay({ index: selected, development: true, demoMode: true, role: "learner" });
  const display = (key: string, scale = 1) => {
    const value = sample?.metrics.find(m => m.metric_name === key)?.latest_value;
    return value == null ? "Unavailable" : String(Number((Number(value) * scale).toFixed(2)));
  };
  const connected = session.source === "laptop";
  const disabled = connected ? session.calculating || !session.connectedAvailable : !sample || session.busy || session.calculating;
  return <View style={styles.root}>
    <Text style={styles.disclosure}>{connected ? "Synthetic Sample Data \u00b7 Laptop connection" : "Demo Mode \u00b7 Fictional data"}</Text>
    <View style={styles.card}>
      <Text accessibilityRole="header" style={styles.heading}>Choose your reading sample</Text>
      <View accessibilityRole="radiogroup" accessibilityLabel="Sample scenario" style={styles.chips}>
        {Array.from({ length: connectedReplayLength }, (_, value) => <Pressable key={value} accessibilityRole="radio"
          accessibilityLabel={`Sample scenario: ${value === 0 ? "Before reading" : `Sample ${value}`}`}
          accessibilityState={{ checked: selected === value }} onPress={() => { session.cancelCalculation(); setSelected(value); }}
          style={({ pressed }) => [styles.chip, selected === value && styles.selected, pressed && styles.pressed]}>
          <Text style={[styles.chipText, selected === value && styles.selectedText]}>{value === 0 ? "Before Reading" : `Sample ${value}`}</Text>
        </Pressable>)}
      </View>
      <Text style={styles.body}>{selected === 0 ? "Before reading" : `Sample ${selected}`} selected</Text>
      <Text style={styles.count}>{sample ? `${sample.includedSessionCount} completed sample sessions` : "Session count unavailable"}</Text>
      <View style={styles.metrics}>
        {[{ key: "reading_accuracy", label: "Accuracy", unit: "%", icon: "\u25C6", scale: 100, accent: colors.blue, color: "#153E75", background: colors.sky },
          { key: "reading_fluency_wpm", label: "Speed", unit: "WPM", icon: "\u2197", scale: 1, accent: colors.green, color: "#166534", background: colors.mint },
          { key: "hesitation_rate_per_word", label: "Hesitations", unit: "per 100 attempted words", icon: "\u22EF", scale: 100, accent: colors.purple, color: "#5B21B6", background: colors.lavender }].map(metric => {
            const value = display(metric.key, metric.scale);
            return <View testID={`results-${metric.key}`} key={metric.key} accessible accessibilityLabel={`${metric.label}: ${value}${value === "Unavailable" ? "" : ` ${metric.unit}`}`} style={[styles.metric, stacked && styles.stackedMetric, { backgroundColor: metric.background, borderTopColor: metric.accent }]}>
              <View style={styles.metricTitle}><Text accessible={false} style={[styles.icon, { color: metric.color }]}>{metric.icon}</Text><Text style={styles.metricLabel}>{metric.label}</Text></View>
              <Text style={[styles.value, { color: metric.color }]}>{value}</Text>
              {value !== "Unavailable" ? <Text style={styles.unit}>{metric.unit}</Text> : null}
            </View>;
          })}
      </View>
      {!sample ? <Text accessibilityRole="alert" style={styles.body}>This sample is unavailable. Choose another example.</Text> : null}
    </View>
    <View style={styles.card}>
      <Text accessibilityRole="header" style={styles.heading}>{connected ? "Save your sample progress" : "Update your progress"}</Text>
      <Text style={styles.body}>{connected ? "Save the selected samples, or load your saved progress." : "See how these reading results affect your progress."}</Text>
      {session.calculationError ? <><Text accessibilityRole="alert" style={styles.body}>{session.calculationError}</Text>
        <Pressable accessibilityRole="button" disabled={session.calculating} accessibilityState={{ disabled: session.calculating }} onPress={() => { void session.retrySavedProgress().then(ok => { if (ok) onApplied?.(); }); }} style={styles.secondary}><Text style={styles.secondaryText}>Retry</Text></Pressable></> : null}
      {connected && session.savedMessage ? <Text accessibilityLiveRegion="polite" style={styles.body}>{session.savedMessage}</Text> : null}
      {session.calculating ? <View><Text accessibilityLiveRegion="polite" style={styles.body}>Getting sample results...</Text>
        <Pressable accessibilityRole="button" onPress={session.cancelCalculation} style={styles.secondary}><Text style={styles.secondaryText}>Cancel calculation</Text></Pressable></View> : null}
      <Pressable accessibilityRole="button" disabled={disabled} accessibilityState={{ disabled }} style={[styles.primary, disabled && styles.disabled]}
        onPress={() => { if (connected) { void session.savedProgress(selected).then(ok => { if (ok) onApplied?.(); }); } else { session.replay(selected); onApplied?.(); } }}>
        <Text style={styles.primaryText}>{connected ? "Save Sample Progress" : "Update My Progress"}</Text>
      </Pressable>
      {connected ? <Pressable accessibilityRole="button" disabled={disabled} accessibilityState={{ disabled }} style={[styles.secondary, disabled && styles.disabled]}
        onPress={() => { void session.savedProgress().then(ok => { if (ok) onApplied?.(); }); }}><Text style={styles.secondaryText}>Refresh Saved Progress</Text></Pressable> : null}
    </View>
    <View style={styles.card}>
      <Pressable accessibilityRole="button" accessibilityLabel="Session Details" accessibilityState={{ expanded: details }} onPress={() => setDetails(!details)} style={styles.detailsToggle}>
        <Text style={styles.heading}>Session Details</Text><Text accessible={false} style={styles.secondaryText}>{details ? "Hide" : "Show"}</Text>
      </Pressable>
      {details ? <View style={styles.detailContent}>
        <Text style={styles.body}>Reading time: Unavailable.</Text>
        <Text style={styles.body}>Pause count and duration: Unavailable.</Text>
        <Text style={styles.body}>Replays: Unavailable.</Text>
        <Text style={styles.body}>Session completion: {sample?.history.length ? "Completed sessions only" : "No completed sessions"}.</Text>
        <Text style={styles.body}>Latest session: {sample?.history.at(-1) ? new Date(sample.history.at(-1)!.recordedAt).toLocaleDateString("en-GB", { timeZone: "UTC" }) : "Unavailable"}.</Text>
        {sample ? <Text style={styles.body}>Activity: {sample.context.task.replaceAll("_", " ")}. Level: {sample.context.tier}. Support: {sample.context.mode.replaceAll("_", " ")}.</Text> : null}
      </View> : null}
    </View>
    <View style={styles.card}>
      <Pressable accessibilityRole="button" accessibilityLabel="More information" accessibilityState={{ expanded: more }} onPress={() => setMore(!more)} style={styles.detailsToggle}>
        <Text style={styles.heading}>More information</Text><Text accessible={false} style={styles.secondaryText}>{more ? "Hide" : "Show"}</Text>
      </Pressable>
      {more ? <View style={styles.detailContent}>
        <Text style={styles.body}>Selected sample values, not new phone measurements.</Text>
        <Text style={styles.body}>{connected ? `Saving Sample ${selected} adds missing samples 1 to ${selected}. Saved sessions stay unchanged.` : "Samples include earlier sessions. Updating replaces the selected example."}</Text>
        {connected ? <Text style={styles.body}>After reopening, sign in and refresh. A cancelled save may have finished; retrying is safe.</Text> : null}
        {choices ? <><Text style={styles.heading}>Your demo choices</Text>
          <Text style={styles.body}>Font: {({ comfortable: "Comfortable", large: "Large", extraLarge: "Extra large" })[choices.settings.font]}. Spacing: {choices.settings.spacing === "wide" ? "Wide" : "Comfortable"}. Highlighting: {choices.settings.highlight ? "On" : "Off"}.</Text>
          <Text style={styles.body}>Feedback: {choices.feedback.feeling ?? "Not selected"}; {choices.feedback.difficulty ?? "Not selected"}; continue: {choices.feedback.continueReading ?? "Not selected"}.</Text>
          <Text style={styles.body}>Device choices do not change sample calculations or tips.</Text></> : null}
        <Text style={styles.body}>Only these samples can be applied. Saved AI reports and PDFs stay unchanged.</Text>
      </View> : null}
    </View>
  </View>;
}
const styles = StyleSheet.create({
  root: { gap: 12 },
  disclosure: { fontSize: 12, lineHeight: 18, color: colors.muted },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  chip: { minHeight: 44, minWidth: 44, paddingVertical: 8, paddingHorizontal: 12, alignItems: "center", justifyContent: "center", borderRadius: radii.pill, borderWidth: 1, borderColor: colors.outline, backgroundColor: colors.white },
  selected: { backgroundColor: colors.sky, borderColor: colors.blue, borderWidth: 2 },
  chipText: { color: colors.ink, fontSize: 14, fontWeight: "700", flexShrink: 1 },
  selectedText: { color: "#153E75", fontWeight: "900" },
  pressed: { opacity: 0.8 },
  card: { borderRadius: radii.medium, padding: 12, gap: 8, backgroundColor: colors.white, borderWidth: 1, borderColor: colors.outline },
  heading: { fontSize: 16, fontWeight: "800", color: colors.ink },
  body: { fontSize: 14, lineHeight: 20, color: colors.ink },
  count: { fontSize: 14, fontWeight: "700", color: colors.ink },
  metrics: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  metric: { flexGrow: 1, flexBasis: 84, minWidth: 84, padding: 12, borderRadius: radii.medium, borderTopWidth: 4, gap: 6 },
  stackedMetric: { flexBasis: "100%" },
  metricTitle: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 6 },
  icon: { fontSize: 16, fontWeight: "800" },
  unit: { fontSize: 12, lineHeight: 18, color: colors.muted },
  value: { fontSize: 23, fontWeight: "900", flexShrink: 1 },
  metricLabel: { fontSize: 13, lineHeight: 19, fontWeight: "700", color: colors.ink },
  primary: { minHeight: 48, padding: 12, borderRadius: radii.medium, backgroundColor: colors.action, alignItems: "center", justifyContent: "center" },
  primaryText: { fontSize: 16, fontWeight: "800", color: colors.white, textAlign: "center" },
  secondary: { minHeight: 44, padding: 10, borderRadius: radii.medium, backgroundColor: colors.sky, alignItems: "center", justifyContent: "center" },
  secondaryText: { fontSize: 14, fontWeight: "700", color: colors.ink },
  disabled: { opacity: 0.55 },
  detailsToggle: { minHeight: 44, flexDirection: "row", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 8 },
  detailContent: { gap: 8 },
});
