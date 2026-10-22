import type { ReactNode } from "react";
import { ScrollView, StyleSheet, Text, useWindowDimensions, View } from "react-native";

import { DemoLearnerCard } from "./DemoLearnerCard";
import { FeatureAccent } from "./FeatureAccent";
import { DemoBanner } from "./DemoBanner";
import { DifficultyProgression } from "./DifficultyProgression";
import { MetricChart } from "./MetricChart";
import { ReadingBuddyIllustration } from "./ReadingBuddyIllustration";
import { RecommendationPanel } from "./RecommendationPanel";
import { palette, radii, softShadow, spacing } from "../theme";
import type { DashboardPreview, PreviewRole } from "../types";

interface PreviewDashboardProps {
  dashboard: DashboardPreview;
  demoMode: boolean;
  children?: ReactNode;
  compactMetrics?: boolean;
  homeHeader?: ReactNode;
}

function shortDate(value: string): string {
  return new Date(value).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

const ROLE_PRESENTATION: Record<
  PreviewRole,
  { eyebrow: string; greeting: string; summaryPrompt: string }
> = {
  learner: {
    eyebrow: "READBUDDY",
    greeting: "Hi, reader!",
    summaryPrompt: "Your reading practice",
  },
  guardian: {
    eyebrow: "READBUDDY FOR GUARDIANS",
    greeting: "A caring view of progress",
    summaryPrompt: "Reading practice summary",
  },
  educator: {
    eyebrow: "READBUDDY FOR EDUCATORS",
    greeting: "Evidence at a glance",
    summaryPrompt: "Comparable reading evidence",
  },
};

export function PreviewDashboard({ dashboard, demoMode, children, compactMetrics = false, homeHeader }: PreviewDashboardProps) {
  const { width, fontScale } = useWindowDimensions();
  const stacked = width < 380 || fontScale > 1.2;
  const rolePresentation = ROLE_PRESENTATION[dashboard.role];
  const playful = dashboard.role === "learner";
  return (
    <ScrollView
      contentContainerStyle={styles.content}
      keyboardShouldPersistTaps="handled"
      showsVerticalScrollIndicator={false}
      style={styles.scroll}
    >
      {demoMode && dashboard.role !== "learner" ? <Text style={{ fontSize: 15, lineHeight: 22, color: palette.ink }}>This view uses its own sample data. It does not follow the Learner&apos;s selected scenario.</Text> : null}
      {demoMode ? <><DemoBanner />{!homeHeader ? <DemoLearnerCard /> : null}</> : null}
      {homeHeader ?? <>
      <View style={[styles.hero, (stacked || playful) && styles.stacked, playful && styles.learnerHero]}>
        <View style={styles.heroCopy}>
          <FeatureAccent title={dashboard.role === "learner" ? "Reading Home" : dashboard.role} />
          <Text style={styles.eyebrow}>{rolePresentation.eyebrow}</Text>
          <Text accessibilityRole="header" style={styles.greeting}>
            {rolePresentation.greeting}
          </Text>
          <Text style={styles.heroTitle}>{dashboard.title}</Text>
          <Text style={styles.subtitle}>
            {playful ? "Explore your reading. Find your next step. This is a demo report." : dashboard.subtitle}
          </Text>
        </View>
        <ReadingBuddyIllustration large={playful} />
      </View>
      <View style={styles.summaryCard}>
        <View style={[styles.summaryTopRow, stacked && styles.stacked]}>
          <View style={styles.summaryCount}>
            <Text style={styles.summaryValue}>{dashboard.includedSessionCount}</Text>
            <Text style={styles.summaryLabel}>sample sessions</Text>
          </View>
          <View style={styles.periodBadge}>
            <Text style={styles.periodBadgeLabel}>Reporting period</Text>
            <Text style={styles.period}>
              {shortDate(dashboard.reportingStartUtc)} – {shortDate(dashboard.reportingEndUtc)}
            </Text>
          </View>
        </View>
        <Text style={styles.summaryPrompt}>{rolePresentation.summaryPrompt}</Text>
        <Text style={styles.context}>{dashboard.contextSummary}</Text>
      </View>
      </>}
      <View style={styles.section}>
        <View style={styles.sectionHeadingRow}>
          <View style={styles.sectionMark} />
          <Text accessibilityRole="header" style={styles.sectionTitle}>
            Reading progress
          </Text>
        </View>
        <Text style={styles.sectionDescription}>
          Compare first and latest sample results from the same reading context.
        </Text>
        {dashboard.metrics.map((metric) => (
          <MetricChart key={metric.key} metric={metric} playful={playful} collapsibleDetails={compactMetrics} />
        ))}
      </View>
      {children}
      <DifficultyProgression observations={dashboard.difficultyProgression} playful={playful} />
      {dashboard.role === "learner" ? <RecommendationPanel recommendation={dashboard.recommendation} playful={playful} /> : null}
      <View style={styles.limitations}>
        <View style={styles.sectionHeadingRow}>
          <View style={[styles.sectionMark, styles.limitationsMark]} />
          <Text accessibilityRole="header" style={styles.sectionTitle}>
            Evidence notes
          </Text>
        </View>
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
  scroll: {
    backgroundColor: palette.paper,
  },
  content: {
    gap: spacing.lg,
    paddingHorizontal: 16,
    paddingBottom: 36,
  },
  stacked: {
    flexDirection: "column",
    alignItems: "flex-start",
  },
  learnerHero: {
    alignItems: "center",
    paddingVertical: spacing.xxl,
    backgroundColor: palette.primarySoft,
    gap: spacing.xl,
  },
  hero: {
    minHeight: 180,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    borderRadius: radii.large,
    backgroundColor: palette.primarySoft,
    padding: spacing.lg,
  },
  heroCopy: {
    flexShrink: 1,
    alignSelf: "stretch",
    gap: spacing.xs,
  },
  eyebrow: {
    color: palette.primary,
    fontSize: 11,
    fontWeight: "900",
    letterSpacing: 1,
  },
  greeting: {
    color: palette.primaryDark,
    fontSize: 25,
    fontWeight: "900",
    letterSpacing: -0.4,
  },
  heroTitle: {
    color: palette.ink,
    fontSize: 17,
    fontWeight: "900",
  },
  subtitle: {
    color: palette.muted,
    fontSize: 13,
    lineHeight: 19,
  },
  summaryCard: {
    gap: spacing.md,
    borderRadius: radii.large,
    backgroundColor: palette.surface,
    borderWidth: 1,
    borderColor: palette.outline,
    padding: spacing.lg,
    ...softShadow,
  },
  summaryTopRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.md,
  },
  summaryCount: {
    flexShrink: 0,
  },
  summaryValue: {
    color: palette.primary,
    fontSize: 38,
    fontWeight: "900",
  },
  summaryLabel: {
    color: palette.muted,
    fontSize: 14,
  },
  periodBadge: {
    flexShrink: 1,
    alignItems: "flex-end",
    borderRadius: radii.medium,
    backgroundColor: palette.primarySoft,
    paddingHorizontal: spacing.md,
    paddingVertical: 9,
  },
  periodBadgeLabel: {
    color: palette.primaryDark,
    fontSize: 12,
    fontWeight: "700",
  },
  period: {
    color: palette.primaryDark,
    fontSize: 13,
    fontWeight: "800",
    textAlign: "right",
  },
  summaryPrompt: {
    color: palette.primaryDark,
    fontSize: 14,
    fontWeight: "900",
  },
  context: {
    color: palette.ink,
    fontSize: 14,
    lineHeight: 22,
  },
  section: {
    gap: spacing.md,
  },
  sectionHeadingRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  sectionMark: {
    width: 8,
    height: 24,
    borderRadius: 4,
    backgroundColor: palette.coral,
  },
  sectionTitle: {
    color: palette.ink,
    fontSize: 20,
    fontWeight: "900",
  },
  sectionDescription: {
    color: palette.muted,
    fontSize: 13,
    lineHeight: 19,
  },
  limitations: {
    gap: spacing.sm,
    borderRadius: radii.large,
    backgroundColor: palette.blueSoft,
    padding: spacing.lg,
  },
  limitationsMark: {
    backgroundColor: palette.blue,
  },
  limitation: {
    color: palette.ink,
    fontSize: 13,
    lineHeight: 19,
  },
  disclaimer: {
    color: palette.yellow,
    fontSize: 12,
    fontWeight: "700",
    lineHeight: 18,
    textAlign: "center",
    borderRadius: radii.medium,
    backgroundColor: palette.yellowSoft,
    padding: spacing.lg,
  },
});
