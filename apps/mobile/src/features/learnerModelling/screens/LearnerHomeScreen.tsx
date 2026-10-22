import { developerToolsEnabled } from "../preview/developerTools";
import { Pressable, StyleSheet, Text, useWindowDimensions, View } from "react-native";

import { HomeHero } from "../components/HomeHero";
import { PreviewDashboard } from "../components/PreviewDashboard";
import type { LearnerReportProps } from "../components/LearnerReportLayout";
import { LEARNER_DESTINATIONS, SECONDARY_DESTINATIONS, type LearnerDestination } from "../navigation/learnerDestinations";
import { palette, radii, softShadow, spacing } from "../theme";

const FEATURE_VISUALS = {
  progress: { icon: "↗", background: palette.tealSoft, color: palette.teal },
  suggestions: { icon: "?", background: palette.yellowSoft, color: palette.yellow },
  profile: { icon: "Aa", background: palette.primarySoft, color: palette.primary },
  settings: { icon: "≡", background: palette.orangeSoft, color: palette.orange },
  feedback: { icon: "…", background: palette.tealSoft, color: palette.teal },
  report: { icon: "▤", background: palette.primarySoft, color: palette.primary },
} as const;

export function LearnerHomeScreen({ dashboard, demoMode, onNavigate }: LearnerReportProps & {
  onNavigate: (destination: LearnerDestination) => void;
}) {
  const { width, fontScale } = useWindowDimensions();
  const twoColumns = width >= 420 && fontScale <= 1.2;
  const accuracy = dashboard.metrics.find((m) => m.key === "reading_accuracy");
  const speed = dashboard.metrics.find((m) => m.key === "reading_fluency_wpm");
  return (
    <PreviewDashboard dashboard={dashboard} demoMode={demoMode} compactMetrics homeHeader={<HomeHero sessions={dashboard.includedSessionCount} accuracy={accuracy ? `${accuracy.latestValue}%` : "Unavailable"} speed={speed ? String(speed.latestValue) : "Unavailable"} onStart={() => onNavigate("test")} />}>
      <View style={styles.links}>
        <Text accessibilityRole="header" style={styles.heading}>Explore your reading</Text>
        <View style={styles.grid}>
        {[...(developerToolsEnabled() ? LEARNER_DESTINATIONS.filter((destination) => destination.key !== "home") : []), ...SECONDARY_DESTINATIONS].map((destination) => (
          <Pressable key={destination.key} accessibilityRole="button"
            accessibilityLabel={`Open ${destination.title}`}
            onPress={() => onNavigate(destination.key)}
            style={({ pressed }) => [styles.link, twoColumns && styles.gridLink, destination.key === "progress" && styles.primaryLink, pressed && styles.pressed]}>
            <View accessible={false} style={[styles.featureIcon, { backgroundColor: FEATURE_VISUALS[destination.key].background }]}>
              <Text style={[styles.iconText, { color: FEATURE_VISUALS[destination.key].color }]}>{FEATURE_VISUALS[destination.key].icon}</Text>
            </View>
            <View style={styles.copy}>
              <Text style={[styles.title, destination.key === "progress" && styles.primaryText]}>{destination.title}</Text>
              <Text style={[styles.description, destination.key === "progress" && styles.primaryText]}>{destination.description}</Text>
            </View>
            <Text accessible={false} style={[styles.arrow, destination.key === "progress" && styles.primaryText]}>→</Text>
          </Pressable>
        ))}
        </View>
        <View style={styles.familyCard}>
          <Text accessibilityRole="header" style={styles.title}>Parent / Teacher Dashboard</Text>
          <Text style={styles.description}>
            Choose Guardian or Educator above to explore their sample reports.
          </Text>
          <Text style={styles.description}>This preview does not grant access to real learner records.</Text>
        </View>
      </View>
    </PreviewDashboard>
  );
}

const styles = StyleSheet.create({
  links: { gap: spacing.md },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.md },
  gridLink: { flexBasis: "46%", flexDirection: "column", alignItems: "flex-start" },
  primaryLink: { backgroundColor: palette.primary, borderColor: palette.primary },
  primaryText: { color: palette.surface },
  featureIcon: { width: 44, height: 44, alignItems: "center", justifyContent: "center", borderRadius: 14 },
  iconText: { fontSize: 21, fontWeight: "800" },
  familyCard: { padding: spacing.lg, gap: spacing.sm, borderRadius: radii.medium, backgroundColor: palette.yellowSoft },
  heading: { fontSize: 20, fontWeight: "900", color: palette.ink },
  link: { minHeight: 72, flexGrow: 1, flexBasis: "100%", flexDirection: "row", alignItems: "center", gap: spacing.md, padding: spacing.md, borderRadius: radii.medium, backgroundColor: palette.surface, borderWidth: 1, borderColor: palette.outline, ...softShadow },
  copy: { flex: 1, gap: spacing.xs },
  title: { fontSize: 17, fontWeight: "800", color: palette.primaryDark },
  description: { fontSize: 14, lineHeight: 21, color: palette.ink },
  arrow: { fontSize: 24, color: palette.blue },
  pressed: { opacity: 0.8 },
});
