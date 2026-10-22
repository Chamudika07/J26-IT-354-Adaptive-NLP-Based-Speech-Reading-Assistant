import { StyleSheet, Text, View } from "react-native";

import { palette, radii, softShadow, spacing } from "../theme";
import type { DifficultyPreview } from "../types";

interface DifficultyProgressionProps {
  observations: readonly DifficultyPreview[];
  playful?: boolean;
}

const TIER_STYLE = {
  beginner: { icon: "Aa", color: palette.teal, background: palette.tealSoft },
  intermediate: { icon: "Abc", color: palette.primary, background: palette.primarySoft },
  advanced: { icon: "ABC", color: palette.blue, background: palette.blueSoft },
} as const;

export function DifficultyProgression({ observations, playful = false }: DifficultyProgressionProps) {
  return (
    <View style={styles.card}>
      <View style={styles.headingRow}>
        <View style={styles.iconBubble}>
          <Text style={styles.icon}>↗</Text>
        </View>
        <View style={styles.headingCopy}>
          <Text accessibilityRole="header" style={styles.heading}>
            Reading journey
          </Text>
          <Text style={styles.intro}>Difficulty tiers observed in this reporting period.</Text>
        </View>
      </View>
      {observations.map((observation, index) => (
        <View key={`${observation.observedAt}-${observation.tier}`} style={styles.row}>
          <View style={styles.rail}>
            {playful ? (
              <View style={[styles.milestone, { backgroundColor: TIER_STYLE[observation.tier].background }]}>
                <Text style={[styles.milestoneIcon, { color: TIER_STYLE[observation.tier].color }]}>
                  {TIER_STYLE[observation.tier].icon}
                </Text>
              </View>
            ) : <View style={styles.dot} />}
            {index < observations.length - 1 ? <View style={styles.line} /> : null}
          </View>
          <View style={styles.copy}>
            <View style={styles.tierRow}>
              <Text style={[styles.tier, playful && { color: TIER_STYLE[observation.tier].color }]}>{observation.tier}</Text>
              <Text style={styles.date}>
                {new Date(observation.observedAt).toLocaleDateString("en-GB", {
                  day: "numeric",
                  month: "short",
                  timeZone: "UTC",
                })}
              </Text>
            </View>
            <Text style={styles.context}>{observation.context}</Text>
            <Text style={styles.explanation}>{observation.explanation}</Text>
          </View>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  milestone: {
    width: 40,
    height: 40,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
  },
  milestoneIcon: {
    fontSize: 13,
    fontWeight: "900",
  },
  card: {
    gap: spacing.md,
    borderRadius: radii.large,
    backgroundColor: palette.surface,
    padding: spacing.lg,
    ...softShadow,
  },
  headingRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
  },
  iconBubble: {
    width: 42,
    height: 42,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 14,
    backgroundColor: palette.orangeSoft,
  },
  icon: {
    color: palette.orange,
    fontSize: 22,
    fontWeight: "900",
  },
  headingCopy: {
    flex: 1,
  },
  heading: {
    color: palette.ink,
    fontSize: 18,
    fontWeight: "900",
  },
  intro: {
    color: palette.muted,
    fontSize: 12,
    lineHeight: 17,
    marginTop: 2,
  },
  row: {
    flexDirection: "row",
    gap: spacing.md,
  },
  rail: {
    width: 40,
    alignItems: "center",
  },
  dot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    borderWidth: 3,
    borderColor: palette.tealSoft,
    backgroundColor: palette.teal,
  },
  line: {
    width: 2,
    flex: 1,
    minHeight: 58,
    backgroundColor: "#BDE8DF",
  },
  copy: {
    flex: 1,
    paddingBottom: 6,
  },
  tier: {
    flexShrink: 1,
    color: palette.ink,
    fontSize: 15,
    fontWeight: "900",
    textTransform: "capitalize",
  },
  tierRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  date: {
    color: palette.teal,
    fontSize: 12,
    fontWeight: "700",
  },
  context: {
    color: palette.ink,
    fontSize: 12,
    marginTop: 4,
  },
  explanation: {
    color: palette.muted,
    fontSize: 12,
    lineHeight: 17,
    marginTop: 3,
  },
});
