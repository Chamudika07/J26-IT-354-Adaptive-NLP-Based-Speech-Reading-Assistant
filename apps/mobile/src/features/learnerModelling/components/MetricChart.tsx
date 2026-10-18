import { StyleSheet, Text, View, type DimensionValue } from "react-native";

import type { MetricPreview } from "../types";

interface MetricChartProps {
  metric: MetricPreview;
}

function barWidth(value: number, maximum: number): DimensionValue {
  const percent = Math.max(8, Math.min(100, Math.round((value / maximum) * 100)));
  return `${percent}%`;
}

function formatValue(metric: MetricPreview, value: number): string {
  if (metric.key === "reading_accuracy") {
    return `${value}%`;
  }
  return `${value}`;
}

export function MetricChart({ metric }: MetricChartProps) {
  const maximum = Math.max(metric.firstValue, metric.latestValue, 1);
  const accessibleSummary = `${metric.label}: first ${formatValue(metric, metric.firstValue)}, latest ${formatValue(metric, metric.latestValue)} ${metric.unit}. ${metric.explanation}`;

  return (
    <View accessibilityLabel={accessibleSummary} style={styles.card}>
      <View style={styles.headingRow}>
        <Text style={styles.heading}>{metric.label}</Text>
        <Text style={styles.direction}>{metric.changeDirection.replaceAll("_", " ")}</Text>
      </View>
      <Text style={styles.unit}>{metric.unit}</Text>
      <View style={styles.barRow}>
        <Text style={styles.barLabel}>First</Text>
        <View style={styles.track}>
          <View style={[styles.firstBar, { width: barWidth(metric.firstValue, maximum) }]} />
        </View>
        <Text style={styles.value}>{formatValue(metric, metric.firstValue)}</Text>
      </View>
      <View style={styles.barRow}>
        <Text style={styles.barLabel}>Latest</Text>
        <View style={styles.track}>
          <View style={[styles.latestBar, { width: barWidth(metric.latestValue, maximum) }]} />
        </View>
        <Text style={styles.value}>{formatValue(metric, metric.latestValue)}</Text>
      </View>
      <Text style={styles.explanation}>{metric.explanation}</Text>
      <Text style={styles.evidence}>{metric.evidenceLabel}</Text>
      {metric.detail ? <Text style={styles.detail}>{metric.detail}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    gap: 8,
    borderRadius: 16,
    backgroundColor: "#FFFFFF",
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
    color: "#183142",
    fontSize: 17,
    fontWeight: "800",
  },
  direction: {
    color: "#176B5B",
    fontSize: 12,
    fontWeight: "700",
    textTransform: "capitalize",
  },
  unit: {
    color: "#667C8B",
    fontSize: 12,
  },
  barRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  barLabel: {
    width: 42,
    color: "#526A7B",
    fontSize: 12,
  },
  track: {
    flex: 1,
    height: 12,
    overflow: "hidden",
    borderRadius: 6,
    backgroundColor: "#E6EDF2",
  },
  firstBar: {
    height: 12,
    borderRadius: 6,
    backgroundColor: "#91A8B8",
  },
  latestBar: {
    height: 12,
    borderRadius: 6,
    backgroundColor: "#20A486",
  },
  value: {
    width: 38,
    color: "#183142",
    fontSize: 12,
    fontWeight: "700",
    textAlign: "right",
  },
  explanation: {
    color: "#314C5E",
    fontSize: 13,
    lineHeight: 19,
  },
  evidence: {
    color: "#176B5B",
    fontSize: 12,
    fontWeight: "700",
  },
  detail: {
    color: "#526A7B",
    fontSize: 12,
    lineHeight: 17,
  },
});
