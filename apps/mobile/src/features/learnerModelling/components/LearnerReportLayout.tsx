import { useState, type ReactNode } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { FeatureAccent } from "./FeatureAccent";
import { ReferenceHero } from "./ReferenceHero";
import { DemoBanner } from "./DemoBanner";
import { palette, radii, softShadow, spacing } from "../theme";
import type { LearnerDashboardPreview, ReportingPeriodDays } from "../types";

export interface LearnerReportProps {
  dashboard: LearnerDashboardPreview;
  demoMode: boolean;
  periodDays: ReportingPeriodDays;
}

export function EvidenceNotes({ dashboard }: Pick<LearnerReportProps, "dashboard">) {
  const [expanded, setExpanded] = useState(false);
  return (
    <View style={reportStyles.card}>
      <Pressable accessibilityRole="button" accessibilityState={{ expanded }} onPress={() => setExpanded(!expanded)} style={reportStyles.previewLink}><Text style={reportStyles.body}>About these results</Text></Pressable>
      {expanded ? <>
      {dashboard.limitations.map((note) => <Text key={note} style={reportStyles.body}>{note}</Text>)}
      <Text style={reportStyles.body}>{dashboard.disclaimer}</Text>
      </> : null}
    </View>
  );
}

export function LearnerReportLayout({
  dashboard, demoMode, periodDays, title, introduction, children,
}: LearnerReportProps & { title: string; introduction: string; children: ReactNode }) {
  const date = (value: string) => new Date(value).toLocaleDateString("en-GB", {
    day: "numeric", month: "short", year: "numeric", timeZone: "UTC",
  });
  return (
    <ScrollView style={reportStyles.scroll} contentContainerStyle={reportStyles.content}>
      {demoMode ? <DemoBanner /> : null}
      <ReferenceHero>
        <FeatureAccent title={title} />
        <Text accessibilityRole="header" style={reportStyles.title}>{title}</Text>
        <Text style={reportStyles.body}>{introduction}</Text>
        <Text style={reportStyles.period}>{periodDays}-day reporting period</Text>
        <Text style={reportStyles.body}>
          {date(dashboard.reportingStartUtc)} – {date(dashboard.reportingEndUtc)}
        </Text>

      </ReferenceHero>
      {children}
      <EvidenceNotes dashboard={dashboard} />
    </ScrollView>
  );
}

export const reportStyles = StyleSheet.create({
  primaryAction: { minHeight: 52, padding: spacing.md, borderRadius: radii.medium, backgroundColor: palette.primary, justifyContent: "center", ...softShadow },
  primaryLabel: { fontSize: 17, fontWeight: "800", color: palette.surface },
  previewLink: { minHeight: 48, padding: spacing.md, borderRadius: radii.small, backgroundColor: palette.primarySoft, gap: spacing.sm },
  scroll: { flex: 1, backgroundColor: palette.paper },
  content: { padding: spacing.lg, gap: spacing.lg, paddingBottom: spacing.xxl },
  intro: { backgroundColor: palette.primarySoft, padding: spacing.xl, borderRadius: radii.large, gap: spacing.md, borderTopWidth: 4, borderTopColor: palette.primary },
  card: { backgroundColor: palette.surface, padding: spacing.lg, borderRadius: radii.large, gap: spacing.md, borderWidth: 1, borderColor: palette.outline, ...softShadow },
  title: { fontSize: 24, fontWeight: "800", color: palette.primaryDark },
  heading: { fontSize: 18, fontWeight: "800", color: palette.ink },
  body: { fontSize: 15, lineHeight: 24, color: palette.ink },
  period: { fontSize: 14, fontWeight: "800", color: palette.teal },
});
