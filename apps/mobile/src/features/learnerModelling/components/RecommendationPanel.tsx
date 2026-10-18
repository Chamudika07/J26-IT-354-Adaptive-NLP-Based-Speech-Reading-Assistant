import { StyleSheet, Text, View } from "react-native";

import type { RecommendationPreview } from "../types";

interface RecommendationPanelProps {
  recommendation: RecommendationPreview;
}

export function RecommendationPanel({ recommendation }: RecommendationPanelProps) {
  return (
    <View style={styles.panel}>
      <View style={styles.headingRow}>
        <Text accessibilityRole="header" style={styles.heading}>
          Adaptive recommendation
        </Text>
        <Text style={styles.advisory}>ADVISORY ONLY</Text>
      </View>
      <Text style={styles.tier}>
        Difficulty: {recommendation.currentTier} → {recommendation.recommendedTier}
      </Text>
      <Text style={styles.suggestion}>{recommendation.supportSuggestion}</Text>
      <Text style={styles.explanation}>{recommendation.explanation}</Text>
      <View style={styles.reasons}>
        {recommendation.reasonCodes.map((reason) => (
          <Text key={reason} style={styles.reason}>
            {reason.replaceAll("_", " ")}
          </Text>
        ))}
      </View>
      <Text style={styles.safety}>This preview never applies a learner-setting change automatically.</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  panel: {
    gap: 10,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "#A9D9CF",
    backgroundColor: "#EAF8F5",
    padding: 16,
  },
  headingRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: 8,
  },
  heading: {
    flex: 1,
    color: "#123E37",
    fontSize: 18,
    fontWeight: "800",
  },
  advisory: {
    color: "#774C00",
    fontSize: 10,
    fontWeight: "900",
    backgroundColor: "#FFE7AF",
    borderRadius: 10,
    overflow: "hidden",
    paddingHorizontal: 8,
    paddingVertical: 5,
  },
  tier: {
    color: "#123E37",
    fontSize: 14,
    fontWeight: "800",
    textTransform: "capitalize",
  },
  suggestion: {
    color: "#176B5B",
    fontSize: 14,
    fontWeight: "700",
    lineHeight: 20,
  },
  explanation: {
    color: "#314C5E",
    fontSize: 13,
    lineHeight: 19,
  },
  reasons: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
  },
  reason: {
    color: "#40596B",
    fontSize: 11,
    backgroundColor: "#FFFFFF",
    borderRadius: 10,
    overflow: "hidden",
    paddingHorizontal: 8,
    paddingVertical: 5,
  },
  safety: {
    color: "#774C00",
    fontSize: 12,
    fontWeight: "700",
    lineHeight: 17,
  },
});
