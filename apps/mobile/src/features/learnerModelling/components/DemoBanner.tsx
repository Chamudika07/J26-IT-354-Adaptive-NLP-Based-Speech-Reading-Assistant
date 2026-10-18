import { StyleSheet, Text, View } from "react-native";

export function DemoBanner() {
  return (
    <View accessibilityRole="alert" style={styles.banner}>
      <Text style={styles.text}>DEMO — SYNTHETIC DATA</Text>
      <Text style={styles.subtext}>No accounts, consent records, or learner services are used.</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  banner: {
    gap: 3,
    borderRadius: 14,
    borderWidth: 2,
    borderColor: "#B36B00",
    backgroundColor: "#FFF4DB",
    padding: 12,
  },
  text: {
    color: "#6E3F00",
    fontSize: 15,
    fontWeight: "900",
    letterSpacing: 0.4,
  },
  subtext: {
    color: "#6E3F00",
    fontSize: 12,
    lineHeight: 17,
  },
});
