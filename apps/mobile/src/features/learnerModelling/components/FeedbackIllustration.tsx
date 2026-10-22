import { StyleSheet, Text, View } from "react-native";

import { ReadingBuddyIllustration } from "./ReadingBuddyIllustration";
import { palette, radii, spacing } from "../theme";

export function FeedbackIllustration() {
  return (
    <View accessible accessibilityRole="image" accessibilityLabel="A book and a speech bubble: your view matters" style={styles.scene}>
      <View style={styles.bubble}>
        <Text style={styles.caption}>Your view matters</Text>
        <View style={styles.line} />
        <View style={[styles.line, styles.shortLine]} />
      </View>
      <ReadingBuddyIllustration large />
    </View>
  );
}

const styles = StyleSheet.create({
  scene: { alignItems: "center", backgroundColor: palette.surface, borderRadius: radii.large, padding: spacing.lg, gap: spacing.sm },
  bubble: { alignSelf: "stretch", padding: spacing.lg, borderRadius: radii.medium, borderBottomLeftRadius: 4, backgroundColor: palette.tealSoft, gap: spacing.sm },
  caption: { fontSize: 20, fontWeight: "800", color: palette.primaryDark },
  line: { height: 5, width: "70%", borderRadius: 3, backgroundColor: "#9BCDBA" },
  shortLine: { width: "45%" },
});
