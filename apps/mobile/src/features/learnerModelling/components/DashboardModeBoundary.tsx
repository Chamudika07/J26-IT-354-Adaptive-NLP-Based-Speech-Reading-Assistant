import { useEffect, useRef, useState, type ReactNode } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { Component4ApiError, type ApiFailure, type LiveConnection, type ReadingSessionInput } from "../data/component4Client";
import { createLiveDashboardProvider, type LiveDashboard } from "../data/liveDashboardProvider";
import type { PreviewRole, ReportingPeriodDays } from "../types";
import { palette, radii, spacing } from "../theme";

export interface LiveScreenProps {
  initialMode?: "demo" | "live";
  liveConnection?: LiveConnection;
  /** Validated upstream telemetry only; never populate with a demo form or fixture. */
  pendingSession?: ReadingSessionInput;
}
const messages: Record<ApiFailure, string> = {
  authentication_required: "Please sign in again to see this report.",
  consent_required: "Learning-support consent must be confirmed before this report is available.",
  forbidden: "This account cannot access this reading information.",
  learner_unavailable: "This learner is not available to this account.",
  invalid_request: "Please check the reading information and reporting period.",
  session_conflict: "This session was already received with different reading information.",
  temporarily_unavailable: "We could not reach your reading report. Please try again.",
  invalid_response: "The reading report could not be verified. Please try again later.",
  cancelled: "The request was cancelled.",
};
type State = { owner: LiveConnection; days: number; revision: number } & (
  { status: "loading" } | { status: "ready"; dashboard: LiveDashboard } | { status: "error"; failure: ApiFailure });
function Action({ label, onPress, disabled = false }: { label: string; onPress(): void; disabled?: boolean }) {
  return <Pressable accessibilityRole="button" accessibilityState={{ disabled }} disabled={disabled} onPress={onPress} style={[styles.button, disabled && { opacity: 0.5 }]}><Text style={styles.buttonText}>{label}</Text></Pressable>;
}
function LiveContent({ connection, role, days, pendingSession }: { connection: LiveConnection; role: PreviewRole; days: ReportingPeriodDays; pendingSession?: ReadingSessionInput }) {
  const [revision, setRevision] = useState(0);
  const [state, setState] = useState<State>();
  const [submission, setSubmission] = useState<{ owner: LiveConnection; input: ReadingSessionInput; message: string; pending: boolean }>();
  const submitController = useRef<AbortController | undefined>(undefined);
  const loadController = useRef<AbortController | undefined>(undefined);

  useEffect(() => {
    return () => submitController.current?.abort();
  }, [connection, pendingSession]);
  useEffect(() => {
    const controller = new AbortController();
    loadController.current = controller;
    const owner = { owner: connection, days, revision };
    const end = new Date();
    const window = { start_at_utc: new Date(end.getTime() - days * 86400000).toISOString(), end_at_utc: end.toISOString() };
    void (async () => {
      try {
        const dashboard = await createLiveDashboardProvider(connection).load(role, window, controller.signal);
        if (!controller.signal.aborted) setState({ ...owner, status: "ready", dashboard });
      } catch (error) {
        if (!controller.signal.aborted) setState({ ...owner, status: "error", failure: error instanceof Component4ApiError ? error.failure : "temporarily_unavailable" });
      }
    })();
    return () => controller.abort();
  }, [connection, role, days, revision]);
  const current = state?.owner === connection && state.days === days && state.revision === revision ? state : undefined;
  const currentSubmission = submission?.owner === connection && submission.input === pendingSession ? submission : undefined;
  const submitting = currentSubmission?.pending === true;
  async function submit() {
    if (!pendingSession || submitting) return;
    const controller = new AbortController();
    submitController.current = controller;
    const owner = { owner: connection, input: pendingSession };
    setSubmission({ ...owner, message: "", pending: true });
    try {
      const receipt = await createLiveDashboardProvider(connection).submitReadingSession(pendingSession, controller.signal);
      if (!controller.signal.aborted) {
        setSubmission({ ...owner, message: receipt.created ? "Reading session received." : "This reading session was already received.", pending: false });
        setRevision(v => v + 1);
      }
    } catch (error) {
      if (!controller.signal.aborted) setSubmission({ ...owner, message: messages[error instanceof Component4ApiError ? error.failure : "temporarily_unavailable"], pending: false });
    }
  }
  return <ScrollView contentContainerStyle={styles.content}>
    <Text accessibilityRole="header" style={styles.heading}>{role === "learner" ? "My Learning Analytics" : role === "guardian" ? "Parent Dashboard" : "Teacher Dashboard"}</Text>
    {!current || current.status === "loading" ? <View><ActivityIndicator accessibilityLabel="Loading live reading report" /><Action label="Cancel Loading" onPress={() => {
      loadController.current?.abort();
      setState({ owner: connection, days, revision, status: "error", failure: "cancelled" });
    }} /></View> : current.status === "error" ? <View accessibilityRole="alert" style={styles.card}><Text>{messages[current.failure]}</Text><Action label="Try Again" onPress={() => setRevision(v => v + 1)} /></View> : <>
      <View style={styles.card}><Text style={styles.heading}>Reading Progress</Text><Text>{current.dashboard.sessionCount} recorded sessions</Text><Text>{new Date(current.dashboard.period.start_at_utc).toLocaleDateString()} – {new Date(current.dashboard.period.end_at_utc).toLocaleDateString()} (end excluded)</Text></View>
      {current.dashboard.sessionCount === 0 ? <Text>No reading results for this period yet.</Text> : null}
      {current.dashboard.contexts.map((context, i) => <View key={i} style={styles.card}><Text style={styles.heading}>{context.label}</Text>{context.metrics.map(metric => <View key={metric.name} style={styles.metric}><Text style={styles.label}>{metric.label}</Text><Text>{metric.latestValue === null ? "Not available yet" : `${Number(metric.latestValue.toFixed(2))} ${metric.unit}`}</Text><Text>First: {metric.firstValue === null ? "Not available yet" : `${Number(metric.firstValue.toFixed(2))} ${metric.unit}`}</Text><Text>{metric.explanation}</Text>{metric.missingCount !== undefined ? <Text>{metric.missingCount} missing measurements</Text> : null}</View>)}</View>)}
      <View style={styles.card}><Text style={styles.heading}>Reading Support History</Text>{current.dashboard.supportHistory.length ? current.dashboard.supportHistory.map((text, i) => <Text key={i}>{text}</Text>) : <Text>No reading support history for this period.</Text>}</View>
      {current.dashboard.difficultyHistory.length ? <View style={styles.card}><Text style={styles.heading}>Reading History</Text>{current.dashboard.difficultyHistory.map((text, i) => <Text key={i}>{text}</Text>)}</View> : null}
      <View style={styles.card}>{current.dashboard.limitations.map((text, i) => <Text key={i}>{text}</Text>)}<Text>{current.dashboard.disclaimer}</Text></View>
      <Text>Reading tips and AI reports are not included in this live report.</Text>
      <Action label="Refresh Reading Report" onPress={() => setRevision(v => v + 1)} />
    </>}
    {role === "learner" && pendingSession ? <View style={styles.card}><Action label="Submit Reading Session" onPress={() => void submit()} disabled={submitting} /><Text accessibilityLiveRegion="polite">{currentSubmission?.message ?? ""}</Text></View> : null}
  </ScrollView>;
}
/** Feature-local opt-in. Demo children unmount in Live Mode; no sample fallback. */
export function DashboardModeBoundary({ liveConnection, pendingSession, initialMode = "demo", role, periodDays, children }: LiveScreenProps & { role: PreviewRole; periodDays: ReportingPeriodDays; children: ReactNode }) {
  const [mode, setMode] = useState<"demo" | "live">(initialMode);
  const permitted = liveConnection?.role === role;
  return <View style={{ flex: 1 }}>
    {liveConnection || mode === "live" ? <View style={styles.controls}><Text>{mode === "live" ? "Live Mode" : "Demo Mode — Sample Data"}</Text><Action label={mode === "live" ? "Use Demo Mode" : "Use Live Mode"} onPress={() => setMode(mode === "live" ? "demo" : "live")} /></View> : null}
    {mode === "demo" ? children : permitted ? <LiveContent key={`${liveConnection.session.scopeKey}:${liveConnection.learnerId}:${role}`} connection={liveConnection} role={role} days={periodDays} pendingSession={pendingSession} /> : <Text accessibilityRole="alert">Sign in with an authorized account to view this report.</Text>}
  </View>;
}
const styles = StyleSheet.create({
  content: { padding: spacing.lg, gap: spacing.md, paddingBottom: 40, backgroundColor: palette.paper },
  controls: { padding: spacing.sm, gap: spacing.sm, backgroundColor: palette.surface },
  card: { padding: spacing.lg, gap: spacing.sm, borderRadius: radii.medium, backgroundColor: palette.surface },
  heading: { fontSize: 19, fontWeight: "800", color: palette.ink },
  label: { fontSize: 16, fontWeight: "700", color: palette.primaryDark },
  metric: { paddingVertical: spacing.sm, gap: 4 },
  button: { minHeight: 48, padding: spacing.md, backgroundColor: palette.primary, borderRadius: radii.small, alignItems: "center" },
  buttonText: { color: "white", fontWeight: "700", fontSize: 16 },
});
