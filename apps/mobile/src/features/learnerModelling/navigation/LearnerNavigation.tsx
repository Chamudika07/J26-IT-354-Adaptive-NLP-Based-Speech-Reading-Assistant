import { developerToolsEnabled } from "../preview/developerTools";
import { useContext, useEffect, useState } from "react";
import { BackHandler, Pressable, StyleSheet, Text, useWindowDimensions, View } from "react-native";

import { HomePresentationContext } from "./HomePresentation";
import { LEARNER_DESTINATIONS, type LearnerDestination } from "./learnerDestinations";
import { useDeveloperTest, DeveloperTestBoundary } from "../preview/DeveloperTestSession";
import { DeveloperReadingGate, DeveloperTestControls } from "../components/DeveloperReadingPreview";
import { ReadingSessionTestScreen } from "../screens/ReadingSessionTestScreen";
import { PreviewSessionBoundary } from "../preview/PreviewSession";
import { DashboardStateView } from "../components/DashboardStateView";
import { AIProgressReportScreen } from "../screens/AIProgressReportScreen";
import { LearnerHomeScreen } from "../screens/LearnerHomeScreen";
import { LearnerProfileScreen } from "../screens/LearnerProfileScreen";
import { LearnerProgressHistoryScreen } from "../screens/LearnerProgressHistoryScreen";
import { LearnerSuggestionsScreen } from "../screens/LearnerSuggestionsScreen";
import { SessionFeedbackScreen } from "../screens/SessionFeedbackScreen";
import { SupportSettingsScreen } from "../screens/SupportSettingsScreen";
import { palette, radii, spacing } from "../theme";
import type { DashboardPresentationState, LearnerDashboardPreview, ReportingPeriodDays } from "../types";

function SampleSourceLabel({ destination }: { destination: string }) {
  const session = useDeveloperTest();
  if (session?.source !== "laptop" || ["report", "home", "test"].includes(destination)) return null;
  return <Text accessibilityLiveRegion="polite" style={{ paddingHorizontal: 16 }}>{session.connected.artifact ? "Synthetic Sample Data \u00b7 Calculated on laptop" : "Synthetic Sample Data \u00b7 Choose Reading Results to update"}</Text>;
}

export function LearnerNavigation({ state, periodDays }: {
  state: DashboardPresentationState<LearnerDashboardPreview>;
  periodDays: ReportingPeriodDays;
}) {
  const [destination, setDestination] = useState<LearnerDestination>("home");
  const reportHome = useContext(HomePresentationContext);
  useEffect(() => {
    reportHome?.(destination === "home");
    return () => reportHome?.(false);
  }, [destination, reportHome]);
  const { width, fontScale } = useWindowDimensions();
  const wrapTabs = width < 390 || fontScale > 1.15;

  useEffect(() => {
    const subscription = BackHandler.addEventListener("hardwareBackPress", () => {
      if (destination === "home") return false;
      setDestination("home");
      return true;
    });
    return () => subscription.remove();
  }, [destination]);

  const props = state.status === "ready" ? {
    dashboard: state.dashboard, demoMode: state.provenance === "demo", periodDays,
  } : undefined;

  // Keep drafts during demo period reloads; failures, live provenance and other roles discard them.
  // The boundary sits above the destination key, and feature unmount also destroys its memory.
  const previewAllowed = state.provenance === "demo" && (
    state.status === "loading" || (state.status === "ready" && state.dashboard.role === "learner")
  );
  return (
    <DeveloperTestBoundary enabled={previewAllowed}>
      <PreviewSessionBoundary enabled={previewAllowed}>
        <View style={styles.root}>
          <SampleSourceLabel destination={destination} />
          {destination !== "home" ? (
            <Pressable accessibilityRole="button" accessibilityLabel="Back to reading Home"
              onPress={() => setDestination("home")} style={styles.back}>
              <Text style={styles.backLabel}>← Back to Home</Text>
            </Pressable>
          ) : null}
          {developerToolsEnabled() ? <DeveloperTestControls onOpen={() => setDestination("test")} /> : null}
          <View style={styles.content} key={`${destination}-${periodDays}-${state.provenance}`}>
            <DeveloperReadingGate destination={destination} days={periodDays} onNavigate={setDestination} reportProps={props}>
              {!props ? <DashboardStateView state={state} /> : (
                destination === "home" ? <LearnerHomeScreen {...props} onNavigate={setDestination} /> :
                destination === "progress" ? <LearnerProgressHistoryScreen {...props} onTips={() => setDestination("suggestions")} /> :
                destination === "suggestions" ? <LearnerSuggestionsScreen {...props} /> :
                destination === "profile" ? <LearnerProfileScreen {...props} onOpenSettings={() => setDestination("settings")} /> :
                !props.demoMode || props.dashboard.role !== "learner" ? <DashboardStateView state={{ status: "temporarily_unavailable", provenance: state.provenance }} /> :
                destination === "test" && __DEV__ ? <ReadingSessionTestScreen onNavigate={setDestination} /> :
                destination === "settings" ? <SupportSettingsScreen /> :
                destination === "feedback" ? <SessionFeedbackScreen /> :
                <AIProgressReportScreen {...props} />
              )}
              </DeveloperReadingGate>
          </View>
          <View accessibilityRole="tablist" accessibilityLabel="Learner feature navigation" style={styles.tabs}>
            {LEARNER_DESTINATIONS.map((item) => (
              <Pressable key={item.key} accessibilityRole="tab"
                accessibilityLabel={`${item.label} learner view`}
                accessibilityState={{ selected: destination === item.key }}
                onPress={() => setDestination(item.key)}
                style={({ pressed }) => [styles.tab, wrapTabs && styles.wrapTab, destination === item.key && styles.activeTab, pressed && styles.pressed]}>
                <Text accessible={false} style={[styles.icon, destination === item.key && styles.activeText]}>{item.icon}</Text>
                <Text style={[styles.label, destination === item.key && styles.activeText]}>{item.key === "suggestions" ? "Tips" : item.label}</Text>
              </Pressable>
            ))}
          </View>
        </View>
      </PreviewSessionBoundary>
    </DeveloperTestBoundary>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: palette.paper },
  content: { flex: 1, minHeight: 0 },
  back: { minHeight: 48, justifyContent: "center", paddingHorizontal: spacing.lg, paddingVertical: spacing.sm },
  backLabel: { color: palette.primaryDark, fontSize: 15, fontWeight: "800" },
  tabs: { flexDirection: "row", flexWrap: "wrap", gap: spacing.xs, padding: spacing.sm, borderTopWidth: 1, borderTopColor: palette.outline, backgroundColor: palette.surface },
  tab: { flexGrow: 1, flexBasis: 0, minHeight: 64, padding: spacing.sm, borderRadius: radii.small, alignItems: "center", justifyContent: "center", gap: spacing.xs },
  wrapTab: { flexBasis: "45%" },
  activeTab: { backgroundColor: palette.primarySoft, borderBottomWidth: 3, borderBottomColor: palette.primary },
  activeText: { color: palette.primary },
  icon: { fontSize: 19, fontWeight: "800", color: palette.muted },
  label: { fontSize: 12, fontWeight: "800", color: palette.ink, textAlign: "center", flexShrink: 1 },
  pressed: { opacity: 0.75 },
});
