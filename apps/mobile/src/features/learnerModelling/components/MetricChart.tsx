import { useState } from "react";
import { Pressable, StyleSheet, Text, useWindowDimensions, View, type DimensionValue } from "react-native";

import { palette, radii, softShadow, spacing } from "../theme";
import type { MetricPreview } from "../types";

interface MetricChartProps {
  metric: MetricPreview;
  playful?: boolean;
  collapsibleDetails?: boolean;
}

function barWidth(value: number, maximum: number): DimensionValue {
  const percent = Math.max(0, Math.min(100, (value / maximum) * 100));
  return `${percent}%`;
}

function formatValue(metric: MetricPreview, value: number): string {
  if (metric.key === "reading_accuracy") {
    return `${value}%`;
  }
  return `${value}`;
}

const METRIC_STYLE = {
  reading_accuracy: {
    icon: "✓",
    background: palette.primarySoft,
    accent: palette.primary,
  },
  reading_fluency_wpm: {
    icon: "››",
    background: palette.tealSoft,
    accent: palette.teal,
  },
  hesitation_rate_per_word: {
    icon: "…",
    background: palette.orangeSoft,
    accent: palette.orange,
  },
} as const;

function directionLabel(metric: MetricPreview): string {
  if (metric.changeDirection === "insufficient_evidence") {
    return "More evidence needed";
  }
  if (metric.changeDirection === "no_observed_change") {
    return "No observed change";
  }
  return metric.changeDirection;
}

function learnerInsight(metric: MetricPreview): string {
  if (metric.changeDirection === "insufficient_evidence") {
    return "We need a little more reading practice to see a clear trend.";
  }
  if (metric.key === "reading_accuracy" && metric.changeDirection === "increased") {
    return "Demo data shows more words read correctly.";
  }
  if (metric.key === "reading_fluency_wpm" && metric.changeDirection === "increased") {
    return "Demo data shows more words read each minute.";
  }
  if (metric.key === "hesitation_rate_per_word" && metric.changeDirection === "decreased") {
    return "Demo data shows fewer pauses per 100 attempted words.";
  }
  return "Every reading session helps us learn about practice. See the observations below.";
}

export function MetricChart({ metric, playful = false, collapsibleDetails = false }: MetricChartProps) {
  const [detailsOpen, setDetailsOpen] = useState(!collapsibleDetails);
  const { width, fontScale } = useWindowDimensions();
  const stacked = width < 380 || fontScale > 1.2;
  const maximum = metric.key === "reading_accuracy" ? 100 : Math.max(metric.firstValue, metric.latestValue, 1);
  const visual = METRIC_STYLE[metric.key];
  const accessibleSummary = `${metric.label}: first ${formatValue(metric, metric.firstValue)}, latest ${formatValue(metric, metric.latestValue)} ${metric.unit}. ${metric.explanation}`;

  return (
    <View
      testID={`${metric.key}-card`}
      accessibilityLabel={accessibleSummary}
      style={[styles.card, { borderTopColor: visual.accent }, playful && { backgroundColor: visual.background }]}
    >
      <View style={[styles.headingRow, stacked && styles.stacked]}>
        <View style={[styles.metricIcon, { backgroundColor: visual.background }]}>
          <Text style={[styles.metricIconText, { color: visual.accent }]}>{visual.icon}</Text>
        </View>
        <View style={[styles.headingCopy, stacked && styles.stackedCopy]}>
          <Text style={styles.heading}>{metric.label}</Text>
          <Text style={styles.unit}>{metric.unit}</Text>
        </View>
        <View style={[styles.latestBadge, { backgroundColor: visual.background }]}>
          <Text style={[styles.latestValue, playful && styles.playfulValue, { color: visual.accent }]}>
            {formatValue(metric, metric.latestValue)}
          </Text>
          <Text style={styles.latestLabel}>latest</Text>
        </View>
      </View>
      <Text style={[styles.direction, { color: visual.accent }]}>{directionLabel(metric)}</Text>
      {playful ? <Text style={styles.insight}>{learnerInsight(metric)}</Text> : null}
      <Text style={styles.evidence}>{metric.evidenceLabel}</Text>
      {collapsibleDetails ? (
        <Pressable accessibilityRole="button"
          accessibilityLabel={`${detailsOpen ? "Hide" : "Show"} ${metric.label} details`}
          accessibilityState={{ expanded: detailsOpen }}
          onPress={() => setDetailsOpen((open) => !open)} style={styles.detailsButton}>
          <Text style={styles.detailsLabel}>{detailsOpen ? "Hide details −" : "Show details +"}</Text>
        </Pressable>
      ) : null}
      {detailsOpen ? <>
      <View style={styles.barRow}>
        <Text style={styles.barLabel}>First</Text>
        <View style={styles.track}>
          <View
            testID={`${metric.key}-first-bar`}
            style={[
              styles.bar,
              styles.firstBar,
              { width: barWidth(metric.firstValue, maximum) },
            ]}
          />
        </View>
        <Text style={styles.value}>{formatValue(metric, metric.firstValue)}</Text>
      </View>
      <View style={styles.barRow}>
        <Text style={styles.barLabel}>Latest</Text>
        <View style={styles.track}>
          <View
            testID={`${metric.key}-latest-bar`}
            style={[
              styles.bar,
              { width: barWidth(metric.latestValue, maximum), backgroundColor: visual.accent },
            ]}
          />
        </View>
        <Text style={styles.value}>{formatValue(metric, metric.latestValue)}</Text>
      </View>
      <Text style={styles.scale}>
        {metric.key === "reading_accuracy"
          ? "Bars use a 0-100% scale."
          : `Bars share a 0-${maximum} scale (${metric.unit}).`}
        {" First and latest observations are not comparison-window averages."}
      </Text>
      <Text style={styles.explanation}>{metric.explanation}</Text>
      {metric.detail ? <Text style={styles.detail}>{metric.detail}</Text> : null}
      </> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  stackedCopy: { flex: 0, alignSelf: "stretch" },
  detailsButton: { minHeight: 48, justifyContent: "center", paddingVertical: spacing.sm },
  detailsLabel: { fontSize: 14, fontWeight: "800", color: palette.primaryDark },
  playfulValue: {
    fontSize: 40,
  },
  insight: {
    color: palette.ink,
    fontSize: 18,
    fontWeight: "800",
    lineHeight: 26,
  },
  card: {
    gap: spacing.sm,
    borderRadius: radii.large,
    borderTopWidth: 5,
    backgroundColor: palette.surface,
    padding: spacing.lg,
    ...softShadow,
  },
  stacked: {
    flexDirection: "column",
    alignItems: "flex-start",
  },
  scale: {
    color: palette.muted,
    fontSize: 14,
    lineHeight: 22,
  },
  headingRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  metricIcon: {
    width: 42,
    height: 42,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 14,
  },
  metricIconText: {
    fontSize: 19,
    fontWeight: "900",
  },
  headingCopy: {
    flex: 1,
  },
  heading: {
    color: palette.ink,
    fontSize: 17,
    fontWeight: "900",
  },
  direction: {
    fontSize: 14,
    fontWeight: "800",
  },
  latestBadge: {
    minWidth: 60,
    alignItems: "center",
    borderRadius: radii.medium,
    paddingHorizontal: 9,
    paddingVertical: 7,
  },
  latestValue: {
    fontSize: 26,
    fontWeight: "900",
  },
  latestLabel: {
    color: palette.muted,
    fontSize: 12,
    fontWeight: "700",
  },
  unit: {
    color: palette.muted,
    fontSize: 14,
    marginTop: 2,
  },
  barRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  barLabel: {
    width: 48,
    color: palette.muted,
    fontSize: 14,
  },
  track: {
    flex: 1,
    height: 14,
    overflow: "hidden",
    borderRadius: 7,
    backgroundColor: "#EDF0F5",
  },
  bar: {
    height: 14,
    borderRadius: 7,
  },
  firstBar: {
    backgroundColor: palette.violet,
  },
  value: {
    minWidth: 38,
    flexShrink: 1,
    color: palette.ink,
    fontSize: 14,
    fontWeight: "700",
    textAlign: "right",
  },
  explanation: {
    color: palette.ink,
    fontSize: 15,
    lineHeight: 24,
  },
  evidence: {
    color: palette.teal,
    fontSize: 14,
    lineHeight: 22,
    fontWeight: "700",
  },
  detail: {
    color: palette.muted,
    fontSize: 14,
    lineHeight: 22,
  },
});
