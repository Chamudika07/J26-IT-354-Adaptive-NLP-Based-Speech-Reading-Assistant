import { useEffect, useState, type ReactNode } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useOptionalPreviewSession } from "../preview/PreviewSession";
import { useDeveloperTest } from "../preview/DeveloperTestSession";
import { DemoAvatar, DemoProfileEditor } from "./DemoProfileEditor";
import { DEMO_LEARNER } from "./DemoLearnerCard";
import { palette, radii } from "../theme";

export interface ProfileSessionRow { id: string; label: string; date: string; accuracy: string; speed: string; hesitation: string }
export function LearnerProfileView({ demoMode, sessions, accuracy, speed, history, details, onAnalytics, onSettings }: {
  demoMode: boolean; sessions: number; accuracy: string; speed: string; history?: readonly ProfileSessionRow[];
  details?: ReactNode; onAnalytics?: () => void; onSettings?: () => void;
}) {
  const profile = useOptionalPreviewSession();
  const journey = useDeveloperTest();
  const [editing, setEditing] = useState(false);
  const [preferences, setPreferences] = useState(false);
  const [technical, setTechnical] = useState(false);
  const dismiss = journey?.dismissProgressUpdate;
  useEffect(() => () => dismiss?.(), [dismiss]);
  return <ScrollView style={styles.scroll} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled" keyboardDismissMode="on-drag">
    <Text accessibilityRole="header" style={styles.title}>My Profile</Text>
    {demoMode ? <Text style={styles.disclosure}>{"Demo \u00b7 Fictional data"}</Text> : null}
    {journey?.source === "offline" && journey.progressUpdated ? <Text accessibilityRole="alert" accessibilityLiveRegion="polite" style={styles.confirmation}>Progress updated</Text> : null}
    <View style={styles.card}>
      <View style={styles.identity}>
        {demoMode ? <DemoAvatar avatar={profile?.profile.avatar ?? "book"} /> : null}
        <Text accessibilityRole="header" style={styles.name}>{demoMode ? profile?.profile.name ?? DEMO_LEARNER.name : "Reader"}</Text>
        {demoMode && profile && !editing ? <Pressable accessibilityRole="button" onPress={() => setEditing(true)} style={styles.secondary}><Text style={styles.actionText}>Edit Profile</Text></Pressable> : null}
      </View>
      {editing && profile ? <DemoProfileEditor onClose={() => setEditing(false)} /> : null}
      {profile?.storageMessage ? <Text accessibilityLiveRegion="polite" style={styles.disclosure}>{profile.storageMessage}</Text> : null}
    </View>
    <View style={styles.metrics}>
      {[{ label: "Completed Sessions", value: String(sessions), background: palette.tealSoft }, { label: "Reading Accuracy (%)", value: accuracy, background: palette.primarySoft }, { label: "Reading Speed (WPM)", value: speed, background: palette.violetSoft }].map(item =>
        <View key={item.label} testID={`profile-${item.label}`} style={[styles.metric, { backgroundColor: item.background }]}><Text style={styles.value}>{item.value}</Text><Text style={styles.metricLabel}>{item.label}</Text></View>)}
    </View>
    {onAnalytics ? <Pressable accessibilityRole="button" onPress={onAnalytics} style={styles.primary}><Text style={styles.primaryText}>View Analytics</Text></Pressable> : null}
    {onSettings ? <Pressable accessibilityRole="button" onPress={onSettings} style={styles.secondary}><Text style={styles.actionText}>Reading Settings</Text></Pressable> : null}
    <View style={styles.card}>
      <Text accessibilityRole="header" style={styles.heading}>Reading History</Text>
      {history?.length ? history.map(row => <View key={row.id} testID={`profile-session-${row.id}`} style={styles.session}>
        <View style={styles.sessionTop}><Text style={styles.heading}>{row.label}</Text><Text style={styles.body}>{row.date} · Completed</Text></View>
        <Text style={styles.body}>Accuracy: {row.accuracy} · Speed: {row.speed}</Text>
        <Text style={styles.body}>Hesitations: {row.hesitation}</Text>
      </View>) : <Text style={styles.body}>{sessions ? "Session details are unavailable for this overview." : "No completed sessions yet."}</Text>}
    </View>
    {demoMode && profile ? <View style={styles.card}>
      <Pressable accessibilityRole="button" accessibilityLabel="Reading Preferences" accessibilityState={{ expanded: preferences }} onPress={() => setPreferences(!preferences)} style={styles.toggle}><Text style={styles.heading}>Reading Preferences</Text><Text style={styles.actionText}>{preferences ? "Hide" : "Show"}</Text></Pressable>
      {preferences ? <><Text style={styles.body}>Font: {({ comfortable: "Comfortable", large: "Large", extraLarge: "Extra large" })[profile.settings.font]}. Spacing: {profile.settings.spacing === "wide" ? "Wide" : "Comfortable"}.</Text><Text style={styles.body}>Highlighting: {profile.settings.highlight ? "On" : "Off"}. Audio preferred: {profile.settings.audio ? "Yes" : "No"}.</Text></> : null}
    </View> : null}
    <View style={styles.card}>
      <Pressable accessibilityRole="button" accessibilityLabel="Profile Details" accessibilityState={{ expanded: technical }} onPress={() => setTechnical(!technical)} style={styles.toggle}><Text style={styles.heading}>Profile Details</Text><Text style={styles.actionText}>{technical ? "Hide" : "Show"}</Text></Pressable>
      {technical ? <View style={{ gap: 8 }}>{journey?.source === "laptop" ? <Text style={styles.body}>Calculated on laptop</Text> : null}{details}</View> : null}
    </View>
  </ScrollView>;
}
const styles = StyleSheet.create({
  scroll: { backgroundColor: palette.paper }, content: { paddingHorizontal: 16, paddingTop: 8, paddingBottom: 96, gap: 10 },
  title: { fontSize: 22, fontWeight: "900", color: palette.primaryDark }, disclosure: { color: palette.muted, fontSize: 12, lineHeight: 18 },
  confirmation: { color: palette.primaryDark, backgroundColor: palette.tealSoft, padding: 10, borderRadius: radii.small, fontSize: 15, fontWeight: "700" },
  card: { backgroundColor: palette.surface, borderRadius: radii.medium, padding: 12, gap: 10 },
  identity: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 8 }, name: { flexGrow: 1, flexShrink: 1, fontSize: 19, fontWeight: "800", color: palette.primaryDark },
  metrics: { flexDirection: "row", flexWrap: "wrap", gap: 6 }, metric: { flexGrow: 1, flexBasis: 84, minWidth: 84, padding: 10, borderRadius: radii.small, gap: 6 },
  value: { fontSize: 23, fontWeight: "900", color: palette.primaryDark }, metricLabel: { fontSize: 12, lineHeight: 17, color: palette.ink },
  heading: { fontSize: 16, fontWeight: "800", color: palette.primaryDark }, body: { fontSize: 14, lineHeight: 20, color: palette.ink },
  session: { borderTopWidth: 1, borderColor: palette.outline, paddingTop: 10, gap: 4 }, sessionTop: { flexDirection: "row", flexWrap: "wrap", gap: 8, justifyContent: "space-between" },
  primary: { minHeight: 48, padding: 12, backgroundColor: palette.primary, borderRadius: radii.small, alignItems: "center", justifyContent: "center" }, primaryText: { color: palette.surface, fontWeight: "800", fontSize: 16 },
  secondary: { minHeight: 44, padding: 10, backgroundColor: palette.primarySoft, borderRadius: radii.small, alignItems: "center", justifyContent: "center" }, actionText: { color: palette.primaryDark, fontSize: 14, fontWeight: "700" },
  toggle: { minHeight: 44, flexDirection: "row", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 8 },
});
