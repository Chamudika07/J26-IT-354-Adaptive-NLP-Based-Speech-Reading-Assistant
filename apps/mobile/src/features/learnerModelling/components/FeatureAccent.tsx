import { StyleSheet, Text, View } from "react-native";
import { palette, radii } from "../theme";

// Presentation only: no data, support decisions or provider selection.
export function FeatureAccent({ title }: { title: string }) {
  const key = title.toLowerCase();
  const feature = key.includes("profile") ? { label: "ABOUT YOU", icon: "Aa", color: palette.teal, background: palette.tealSoft }
    : key.includes("settings") ? { label: "READ YOUR WAY", icon: "Aa", color: palette.blue, background: palette.blueSoft }
    : key.includes("feedback") ? { label: "YOUR VOICE MATTERS", icon: "?", color: palette.orange, background: palette.orangeSoft }
    : key.includes("session") ? { label: "LET'S TRY READING", icon: "+", color: palette.teal, background: palette.tealSoft }
    : key.includes("suggest") || key.includes("support") ? { label: "IDEAS TO REVIEW", icon: "+", color: palette.orange, background: palette.orangeSoft }
    : key.includes("report") ? { label: "YOUR READING STORY", icon: "R", color: palette.blue, background: palette.blueSoft }
    : key.includes("guardian") || key.includes("educator") ? { label: "SUPPORTING YOUR READER", icon: "R", color: palette.teal, background: palette.tealSoft }
    : key.includes("progress") || key.includes("analytics") ? { label: "SEE YOUR PRACTICE", icon: "+", color: palette.teal, background: palette.tealSoft }
    : { label: "READY TO EXPLORE", icon: "R", color: palette.yellow, background: palette.yellowSoft };
  return <View style={[styles.row, { backgroundColor: feature.background }]}>
    <Text accessible={false} style={[styles.icon, { color: feature.color }]}>{feature.icon}</Text>
    <Text style={[styles.label, { color: feature.color }]}>{feature.label}</Text>
  </View>;
}
const styles = StyleSheet.create({
  row: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", alignSelf: "flex-start", gap: 8, padding: 10, borderRadius: radii.medium },
  icon: { fontSize: 18, fontWeight: "900" },
  label: { fontSize: 13, fontWeight: "800", flexShrink: 1 },
});
