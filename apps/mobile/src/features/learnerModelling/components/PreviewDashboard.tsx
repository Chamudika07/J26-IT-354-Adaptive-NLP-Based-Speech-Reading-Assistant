import { ScrollView, StyleSheet, Text, View } from "react-native";

import { DemoBanner } from "./DemoBanner";
import { DifficultyProgression } from "./DifficultyProgression";
import { MetricChart } from "./MetricChart";
import { RecommendationPanel } from "./RecommendationPanel";
import type { DashboardPreview } from "../types";

interface PreviewDashboardProps {
  dashboard: DashboardPreview;
  demoMode: boolean;
}

function shortDate(value: string): string {
  return new Date(value).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

export function PreviewDashboard({ dashboard, demoMode }: PreviewDashboardProps) {
  return (
    <ScrollView
      contentContainerStyle={styles.content}
      keyboardShouldPersistTaps="handled"
      showsVerticalScrollIndicator={false}
    >
      {demoMode ? <DemoBanner /> : null}
      <View style={styles.intro}>
        <Text accessibilityRole="header" style={styles.title}>
          {dashboard.title}
        </Text>
        <Text style={styles.subtitle}>{dashboard.subtitle}</Text>
        <Text style={styles.period}>
          {shortDate(dashboard.reportingStartUtc)} – {shortDate(dashboard.reportingEndUtc)}
        </Text>
      </View>
      <View style={styles.summaryCard}>
        <Text style={styles.summaryValue}>{dashboard.includedSessionCount}</Text>
        <Text style={styles.summaryLabel}>synthetic sessions in this reporting period</Text>
        <Text style={styles.context}>{dashboard.contextSummary}</Text>
      </View>
      <View style={styles.section}>
        <Text accessibilityRole="header" style={styles.sectionTitle}>
          Reading measures
        </Text>
        <Text style={styles.sectionDescription}>
          First and latest values are shown within one comparable synthetic context.
        </Text>
        {dashboard.metrics.map((metric) => (
          <MetricChart key={metric.key} metric={metric} />
        ))}
      </View>
      <DifficultyProgression observations={dashboard.difficultyProgression} />
      <RecommendationPanel recommendation={dashboard.recommendation} />
      <View style={styles.limitations}>
        <Text accessibilityRole="header" style={styles.sectionTitle}>
          Evidence limitations
        </Text>
        {dashboard.limitations.map((limitation) => (
          <Text key={limitation} style={styles.limitation}>
            • {limitation}
          </Text>
        ))}
      </View>
      <Text style={styles.disclaimer}>{dashboard.disclaimer}</Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: {
    gap: 14,
    paddingHorizontal: 16,
    paddingBottom: 32,
  },
  intro: {
    gap: 6,
  },
  title: {
    color: "#183142",
    fontSize: 28,
    fontWeight: "900",
    letterSpacing: -0.5,
  },
  subtitle: {
    color: "#526A7B",
    fontSize: 14,
    lineHeight: 21,
  },
  period: {
    color: "#176B5B",
    fontSize: 13,
    fontWeight: "700",
  },
  summaryCard: {
    borderRadius: 18,
    backgroundColor: "#183142",
    padding: 18,
  },
  summaryValue: {
    color: "#FFFFFF",
    fontSize: 34,
    fontWeight: "900",
  },
  summaryLabel: {
    color: "#D8E6EE",
    fontSize: 13,
  },
  context: {
    color: "#B9F0E4",
    fontSize: 12,
    lineHeight: 17,
    marginTop: 10,
  },
  section: {
    gap: 10,
  },
  sectionTitle: {
    color: "#183142",
    fontSize: 19,
    fontWeight: "800",
  },
  sectionDescription: {
    color: "#667C8B",
    fontSize: 13,
    lineHeight: 19,
  },
  limitations: {
    gap: 8,
    borderRadius: 16,
    backgroundColor: "#FFFFFF",
    padding: 16,
  },
  limitation: {
    color: "#40596B",
    fontSize: 13,
    lineHeight: 19,
  },
  disclaimer: {
    color: "#5F4A20",
    fontSize: 12,
    fontWeight: "700",
    lineHeight: 18,
    textAlign: "center",
    paddingHorizontal: 12,
  },
});
