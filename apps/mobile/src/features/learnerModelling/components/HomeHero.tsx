import { Pressable, StyleSheet, Text, useWindowDimensions, View } from "react-native";
import { useDeveloperTest } from "../preview/DeveloperTestSession";
import { useOptionalPreviewSession } from "../preview/PreviewSession";
import { DemoAvatar } from "./DemoProfileEditor";
import { DEMO_LEARNER } from "./DemoLearnerCard";
import { ReadingBuddyIllustration } from "./ReadingBuddyIllustration";
import { radii, softShadow } from "../theme";

// Home-only colors: bright accents, dark readable text, and quiet pastel surfaces.
const home = { blue: "#3182F6", actionBlue: "#1D4ED8", green: "#22C55E", purple: "#8B5CF6", ink: "#07142B", muted: "#465B73", white: "#FFFFFF", sky: "#EEF5FF", mint: "#EAFBF1", lavender: "#F4EFFF", greenInk: "#166534", blueInk: "#153E75", purpleInk: "#5B21B6" } as const;

/** Home-only provenance; other screens keep their existing disclosures. */
export function HomeDisclosure() {
  const sample = useDeveloperTest();
  return <Text style={styles.disclosure}>{"Demo Mode \u00b7 Fictional data"}{sample?.source === "laptop" ? " \u00b7 Calculated on laptop" : ""}</Text>;
}

export function HomeHero({ sessions, accuracy, speed, onStart }: {
  sessions: number; accuracy: string; speed: string; onStart: () => void;
}) {
  const session = useOptionalPreviewSession();
  const { width, fontScale } = useWindowDimensions();
  const stacked = width < 360 || fontScale > 1.2;
  return <View style={styles.root}>
    <View style={styles.hero}>
      <View style={[styles.copy, stacked && styles.stackedCopy]}>
        <Text accessibilityRole="header" style={styles.title}>Hi, Reader!</Text>
        <View style={styles.identity}><DemoAvatar avatar={session?.profile.avatar ?? "book"} /><Text style={[styles.label, { flexShrink: 1 }]}>{session?.profile.name ?? DEMO_LEARNER.name}</Text></View>
        <Text style={styles.message}>{"Let's grow your reading skills!"}</Text>
      </View>
      <View accessible={false} style={styles.picture}><ReadingBuddyIllustration compact /></View>
    </View>
    <View style={styles.metrics}>
      {[{ id: "Completed Sessions", label: "Sessions", value: String(sessions), icon: "\u2713", accent: home.green, ink: home.greenInk, background: home.mint },
        { id: "Reading Accuracy (%)", label: "Accuracy", value: accuracy, icon: "", accent: home.blue, ink: home.blueInk, background: home.sky },
        { id: "Reading Speed (WPM)", label: "Speed", value: /^\d+(?:\.\d+)?$/.test(speed) ? `${speed} WPM` : speed, icon: "\u2197", accent: home.purple, ink: home.purpleInk, background: home.lavender }].map(item =>
        <View key={item.id} testID={`home-${item.id}`} accessible accessibilityLabel={`${item.label}: ${item.value}`} style={[styles.tile, stacked && styles.stackedTile, { borderTopColor: item.accent, backgroundColor: item.background }]}>
          <View style={styles.metricTop}>{item.icon ? <Text accessible={false} style={[styles.metricIcon, { color: item.ink }]}>{item.icon}</Text> : null}<Text style={[styles.value, { color: item.ink }]}>{item.value}</Text></View>
          <Text style={styles.label}>{item.label}</Text>
        </View>)}
    </View>
    <Pressable accessibilityRole="button" accessibilityHint="Choose reading results to explore your progress" onPress={onStart} style={({ pressed }) => [styles.action, pressed && styles.pressed]}>
      <Text style={styles.actionLabel}>Reading Results</Text>
      <Text accessible={false} style={styles.actionArrow}>{"\u2192"}</Text>
    </Pressable>
  </View>;
}
const styles = StyleSheet.create({
  disclosure: { color: home.muted, fontSize: 12, lineHeight: 18 },
  identity: { flexDirection: "row", alignItems: "center", gap: 8 },
  root: { gap: 12 },
  hero: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", padding: 14, gap: 8, backgroundColor: home.sky, borderRadius: 24, borderWidth: 1, borderColor: "#D7E7FF" },
  copy: { flexGrow: 1, flexBasis: 130, gap: 6 }, stackedCopy: { flexBasis: "100%" }, picture: { width: 106, alignItems: "center" },
  title: { color: home.ink, fontSize: 24, fontWeight: "900" },
  message: { color: home.ink, fontSize: 15, lineHeight: 22 },
  metrics: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  tile: { flexGrow: 1, flexBasis: 88, minWidth: 88, borderRadius: radii.medium, borderTopWidth: 4, padding: 10, gap: 6, ...softShadow },
  stackedTile: { flexBasis: "100%" }, metricTop: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 6 },
  metricIcon: { fontSize: 15, fontWeight: "800" }, value: { fontSize: 23, fontWeight: "900" },
  label: { fontSize: 12, lineHeight: 18, color: home.ink, fontWeight: "700" },
  action: { minHeight: 52, alignItems: "center", borderRadius: radii.medium, padding: 14, backgroundColor: home.actionBlue, flexDirection: "row", justifyContent: "space-between", gap: 8 },
  actionLabel: { fontSize: 18, fontWeight: "800", color: home.white, flexShrink: 1 }, actionArrow: { fontSize: 24, color: home.white },
  pressed: { backgroundColor: "#1E40AF" },
});
