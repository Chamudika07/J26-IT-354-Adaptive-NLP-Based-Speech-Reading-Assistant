import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { palette, radii, softShadow, spacing } from "../theme";
import type { RecommendationPreview } from "../types";

interface RecommendationPanelProps {
  recommendation: RecommendationPreview;
  playful?: boolean;
  collapsibleDetails?: boolean;
}

export function RecommendationPanel({ recommendation, playful = false, collapsibleDetails = false }: RecommendationPanelProps) {
  const [details, setDetails] = useState(false);
  return (
    <View style={[styles.panel, playful && styles.playfulPanel]}>
      <View style={styles.headingRow}>
        <View style={styles.headingCopy}>
          <Text style={styles.eyebrow}>A friendly next step</Text>
          <Text accessibilityRole="header" style={styles.heading}>
            Adaptive recommendation
          </Text>
        </View>
        <Text style={styles.advisory}>ADVISORY ONLY</Text>
      </View>
      <Text style={styles.tier}>
        Difficulty: {recommendation.currentTier} → {recommendation.recommendedTier}
      </Text>
      <Text style={styles.suggestion}>{recommendation.supportSuggestion}</Text>
      <Text style={styles.review}>
        {playful
          ? "Review this suggestion with a parent or teacher before making changes."
          : "Recommendations require human review before any difficulty or support changes."}
      </Text>
      {collapsibleDetails ? <Pressable accessibilityRole="button" accessibilityState={{ expanded: details }} onPress={() => setDetails(!details)} style={{ minHeight: 48, justifyContent: "center" }}><Text style={styles.review}>{details ? "Hide support evidence" : "Why this support?"}</Text></Pressable> : null}
      {!collapsibleDetails || details ? <>
      <Text style={styles.explanation}>{recommendation.explanation}</Text>
      <View style={styles.reasons}>
        {recommendation.reasonCodes.map((reason) => (
          <Text key={reason} style={styles.reason}>
            {reason.replaceAll("_", " ")}
          </Text>
        ))}
      </View>
      </> : null}
      <View style={styles.safetyBox}>
        <Text style={styles.safetyIcon}>i</Text>
        <Text style={styles.safety}>
          This preview never applies a learner-setting change automatically.
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  playfulPanel: {
    backgroundColor: palette.tealSoft,
    borderColor: "#8BCDB5",
  },
  review: {
    color: palette.ink,
    fontSize: 14,
    lineHeight: 22,
    fontWeight: "700",
  },
  panel: {
    gap: spacing.md,
    borderRadius: radii.large,
    borderWidth: 2,
    borderColor: "#B3D1EE",
    backgroundColor: palette.primarySoft,
    padding: spacing.lg,
    ...softShadow,
  },
  headingRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  headingCopy: {
    flexGrow: 1,
    flexBasis: 180,
  },
  eyebrow: {
    color: palette.primary,
    fontSize: 11,
    fontWeight: "900",
    letterSpacing: 0.5,
    textTransform: "uppercase",
  },
  heading: {
    color: palette.primaryDark,
    fontSize: 18,
    fontWeight: "900",
    marginTop: 2,
  },
  advisory: {
    color: palette.yellow,
    fontSize: 12,
    fontWeight: "900",
    backgroundColor: palette.yellowSoft,
    borderRadius: radii.pill,
    overflow: "hidden",
    paddingHorizontal: 8,
    paddingVertical: 5,
  },
  tier: {
    color: palette.ink,
    fontSize: 14,
    fontWeight: "800",
    textTransform: "capitalize",
  },
  suggestion: {
    color: palette.primaryDark,
    fontSize: 14,
    fontWeight: "700",
    lineHeight: 20,
  },
  explanation: {
    color: palette.ink,
    fontSize: 15,
    lineHeight: 23,
  },
  reasons: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
  },
  reason: {
    flexShrink: 1,
    color: palette.primaryDark,
    fontSize: 11,
    backgroundColor: palette.surface,
    borderRadius: radii.pill,
    overflow: "hidden",
    paddingHorizontal: 8,
    paddingVertical: 5,
  },
  safetyBox: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacing.sm,
    borderRadius: radii.small,
    backgroundColor: palette.surface,
    padding: spacing.md,
  },
  safetyIcon: {
    width: 20,
    height: 20,
    color: palette.surface,
    fontSize: 12,
    fontWeight: "900",
    lineHeight: 20,
    textAlign: "center",
    borderRadius: 10,
    overflow: "hidden",
    backgroundColor: palette.primary,
  },
  safety: {
    flex: 1,
    color: palette.ink,
    fontSize: 12,
    fontWeight: "700",
    lineHeight: 17,
  },
});
