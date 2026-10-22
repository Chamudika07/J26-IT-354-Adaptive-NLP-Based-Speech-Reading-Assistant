import { useState } from "react";
import { Pressable, Text, View } from "react-native";
import { reportStyles } from "./LearnerReportLayout";
import { DemoAvatar, DemoProfileEditor } from "./DemoProfileEditor";
import { useOptionalPreviewSession, usePreviewSession } from "../preview/PreviewSession";

// Display-only sample identity, never inferred from telemetry or an account.
export const DEMO_LEARNER = Object.freeze({ name: "Demo Learner", age: 10, id: "DEMO-001" });

export function DemoLearnerCard({ editable = false }: { editable?: boolean }) {
  const session = useOptionalPreviewSession();
  const [editing, setEditing] = useState(false);
  return <View style={reportStyles.card}>
    <Text accessibilityRole="header" style={reportStyles.heading}>{session?.profile.name ?? DEMO_LEARNER.name}</Text>
    <DemoAvatar avatar={session?.profile.avatar ?? "book"} />
    {editable && session ? editing ? <DemoProfileEditor onClose={() => setEditing(false)} /> : <Pressable accessibilityRole="button" onPress={() => setEditing(true)} style={reportStyles.previewLink}><Text style={reportStyles.heading}>Edit Profile</Text></Pressable> : null}
    {editable && session ? <Text accessibilityLiveRegion="polite" style={reportStyles.body}>{session.storageMessage}</Text> : null}
    <Text style={reportStyles.body}>Sample age: {DEMO_LEARNER.age} years</Text>
    <Text style={reportStyles.body}>This is a sample name and age, not a real learner record.</Text>
  </View>;
}

export function DemoPreferencesCard() {
  const { settings } = usePreviewSession();
  const sizes = { comfortable: "Comfortable", large: "Large", extraLarge: "Extra large" };
  return <View style={reportStyles.card}>
    <Text accessibilityRole="header" style={reportStyles.heading}>Your demo reading preferences</Text>
    <Text style={reportStyles.body}>Font size: {sizes[settings.font]}. Line spacing: {settings.spacing === "wide" ? "Wide" : "Comfortable"}.</Text>
    <Text style={reportStyles.body}>Highlighting: {settings.highlight ? "On" : "Off"}. Audio preferred: {settings.audio ? "Yes" : "No"}.</Text>
    <Text style={reportStyles.body}>LOCAL PREVIEW ONLY. Choices stay on this device; no audio plays and no reading support changes.</Text>
  </View>;
}
