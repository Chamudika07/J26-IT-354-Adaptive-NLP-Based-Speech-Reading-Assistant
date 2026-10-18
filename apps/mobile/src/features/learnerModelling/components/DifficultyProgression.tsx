import { StyleSheet, Text, View } from "react-native";

import type { DifficultyPreview } from "../types";

interface DifficultyProgressionProps {
  observations: readonly DifficultyPreview[];
}

export function DifficultyProgression({ observations }: DifficultyProgressionProps) {
  return (
    <View style={styles.card}>
      <Text accessibilityRole="header" style={styles.heading}>
        Difficulty progression
      </Text>
      {observations.map((observation, index) => (
        <View key={`${observation.observedAt}-${observation.tier}`} style={styles.row}>
          <View style={styles.rail}>
            <View style={styles.dot} />
            {index < observations.length - 1 ? <View style={styles.line} /> : null}
          </View>
          <View style={styles.copy}>
            <Text style={styles.tier}>{observation.tier}</Text>
            <Text style={styles.date}>
              {new Date(observation.observedAt).toLocaleDateString("en-GB", {
                day: "numeric",
                month: "short",
                timeZone: "UTC",
              })}
            </Text>
            <Text style={styles.context}>{observation.context}</Text>
            <Text style={styles.explanation}>{observation.explanation}</Text>
          </View>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    gap: 12,
    borderRadius: 16,
    backgroundColor: "#FFFFFF",
    padding: 16,
  },
  heading: {
    color: "#183142",
    fontSize: 18,
    fontWeight: "800",
  },
  row: {
    flexDirection: "row",
    gap: 12,
  },
  rail: {
    width: 12,
    alignItems: "center",
  },
  dot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: "#20A486",
  },
  line: {
    width: 2,
    flex: 1,
    minHeight: 58,
    backgroundColor: "#B8DDD5",
  },
  copy: {
    flex: 1,
    paddingBottom: 6,
  },
  tier: {
    color: "#183142",
    fontSize: 15,
    fontWeight: "800",
    textTransform: "capitalize",
  },
  date: {
    color: "#176B5B",
    fontSize: 12,
    fontWeight: "700",
  },
  context: {
    color: "#40596B",
    fontSize: 12,
    marginTop: 4,
  },
  explanation: {
    color: "#667C8B",
    fontSize: 12,
    lineHeight: 17,
    marginTop: 3,
  },
});
