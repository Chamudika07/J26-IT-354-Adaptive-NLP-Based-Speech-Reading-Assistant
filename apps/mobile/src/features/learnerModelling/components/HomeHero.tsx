import { Pressable, StyleSheet, Text, View } from "react-native";
import { useDeveloperTest } from "../preview/DeveloperTestSession";
import { useOptionalPreviewSession } from "../preview/PreviewSession";
import { DemoAvatar } from "./DemoProfileEditor";
import { DEMO_LEARNER } from "./DemoLearnerCard";
import { ReadingBuddyIllustration } from "./ReadingBuddyIllustration";
import { palette, radii, softShadow } from "../theme";

/** Home-only provenance; other screens keep their existing disclosures. */
export function HomeDisclosure() {
  const sample = useDeveloperTest();
  return <Text style={styles.disclosure}>{"Demo Mode \u00b7 Fictional data"}{sample?.source === "laptop" ? " \u00b7 Calculated on laptop" : ""}</Text>;
}

export function HomeHero({ sessions, accuracy, speed, onStart }: {
  sessions: number; accuracy: string; speed: string; onStart: () => void;
}) {
  const session = useOptionalPreviewSession();
  return <View style={styles.root}>
    <View style={styles.hero}>
      <View style={styles.copy}>
        <Text accessibilityRole="header" style={styles.title}>Hi, Reader!</Text>
        <View style={styles.identity}><DemoAvatar avatar={session?.profile.avatar ?? "book"} /><Text style={[styles.label, { flexShrink: 1 }]}>{session?.profile.name ?? DEMO_LEARNER.name}</Text></View>
        <Text style={styles.message}>{"Let's grow your reading skills!"}</Text>
      </View>
      <View accessible={false} style={styles.picture}><ReadingBuddyIllustration compact /></View>
    </View>
    <View style={styles.metrics}>
      {[{ label: "Completed Sessions", value: String(sessions), color: palette.teal, background: palette.tealSoft },
        { label: "Reading Accuracy (%)", value: accuracy, color: palette.primary, background: palette.primarySoft },
        { label: "Reading Speed (WPM)", value: speed, color: palette.violet, background: palette.violetSoft }].map((item) =>
        <View key={item.label} style={[styles.tile, { borderTopColor: item.color, backgroundColor: item.background }]}>
          <Text style={[styles.value, { color: item.color }]}>{item.value}</Text>
          <Text style={styles.label}>{item.label}</Text>
        </View>)}
    </View>
    <Pressable accessibilityRole="button" onPress={onStart} style={styles.action}>
      <Text style={styles.actionLabel}>Reading Results</Text>
      <Text accessible={false} style={styles.actionLabel}>→</Text>
    </Pressable>
  </View>;
}
const styles = StyleSheet.create({
  disclosure: { color: palette.muted, fontSize: 12, lineHeight: 18 },
  identity: { flexDirection: "row", alignItems: "center", gap: 8 },
  root: { gap: 8 },
  hero: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", padding: 12, gap: 8, backgroundColor: palette.heroSoft, borderRadius: radii.large },
  copy: { flexGrow: 1, flexBasis: 150, gap: 2 },
  picture: { width: 106, alignItems: "center" },
  title: { color: palette.primaryDark, fontSize: 23, fontWeight: "900" },
  message: { color: palette.ink, fontSize: 15, lineHeight: 21 },
  metrics: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  tile: { flexGrow: 1, flexBasis: 88, minWidth: 88, borderRadius: radii.medium, borderTopWidth: 3, padding: 10, gap: 4, ...softShadow },
  value: { fontSize: 23, fontWeight: "900" },
  label: { fontSize: 12, lineHeight: 17, color: palette.ink, fontWeight: "700" },
  action: { minHeight: 48, alignItems: "center", borderRadius: radii.medium, padding: 12, backgroundColor: palette.primary, flexDirection: "row", justifyContent: "space-between", gap: 8 },
  actionLabel: { fontSize: 17, fontWeight: "800", color: palette.surface, flexShrink: 1 },
});
