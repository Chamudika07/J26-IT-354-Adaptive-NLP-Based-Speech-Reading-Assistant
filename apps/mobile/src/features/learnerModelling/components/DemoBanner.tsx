import { StyleSheet, Text, View } from "react-native";
import { palette } from "../theme";

export function DemoBanner() {
  return <View accessibilityRole="alert" style={styles.banner}><Text style={styles.text}>Sample Data</Text></View>;
}
const styles = StyleSheet.create({
  banner: { alignSelf: "center", borderRadius: 20, backgroundColor: palette.yellowSoft, paddingHorizontal: 16, paddingVertical: 6 },
  text: { color: palette.yellow, fontSize: 14, fontWeight: "800" },
});
