import type { ReactNode } from "react";
import { StyleSheet, View } from "react-native";
import { ReadingBuddyIllustration } from "./ReadingBuddyIllustration";
import { palette, radii, softShadow } from "../theme";

/** Reference-inspired book hero; decoration never implies a score or achievement. */
export function ReferenceHero({ children }: { children: ReactNode }) {
  return <View style={styles.hero}>
    <View style={styles.copy}>{children}</View>
    <View style={styles.picture} pointerEvents="none" accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      <ReadingBuddyIllustration compact />
    </View>
  </View>;
}
const styles = StyleSheet.create({
  hero: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 12, padding: 18, borderRadius: radii.large, backgroundColor: palette.heroSoft, borderWidth: 1, borderColor: "#D5E7FF", ...softShadow },
  copy: { flexGrow: 1, flexShrink: 1, flexBasis: 190, gap: 10 },
  picture: { width: 106, alignItems: "center", justifyContent: "center", alignSelf: "center" },
});
