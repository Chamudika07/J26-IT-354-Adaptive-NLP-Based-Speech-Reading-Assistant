import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from "react-native";

import { DemoBanner } from "./DemoBanner";
import { PreviewDashboard } from "./PreviewDashboard";
import type { DashboardPresentationState, DashboardPreview } from "../types";

const STATE_COPY = {
  loading: {
    title: "Loading reading report",
    message: "Preparing the selected reporting period.",
  },
  empty: {
    title: "No results for this period",
    message: "No comparable reading observations are available for the selected period.",
  },
  consent_required: {
    title: "Consent required",
    message: "This report cannot be shown until approved learning-support consent is confirmed.",
  },
  learner_unavailable: {
    title: "Learner unavailable",
    message: "This learner report is unavailable for the current signed-in account.",
  },
  temporarily_unavailable: {
    title: "Report temporarily unavailable",
    message: "The educational report could not be loaded. Please try again later.",
  },
  reporting_limit_exceeded: {
    title: "Reporting limit exceeded",
    message: "Choose a shorter reporting period before trying again.",
  },
} as const;

interface DashboardStateViewProps<TDashboard extends DashboardPreview> {
  state: DashboardPresentationState<TDashboard>;
}

export function DashboardStateView<TDashboard extends DashboardPreview>({
  state,
}: DashboardStateViewProps<TDashboard>) {
  const demoMode = state.provenance === "demo";
  if (state.status === "ready") {
    return <PreviewDashboard dashboard={state.dashboard} demoMode={demoMode} />;
  }

  const copy = STATE_COPY[state.status];
  return (
    <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
      {demoMode ? <DemoBanner /> : null}
      <View accessibilityRole="alert" style={styles.card}>
        {state.status === "loading" ? (
          <ActivityIndicator accessibilityLabel="Loading reading report" color="#176B5B" />
        ) : null}
        <Text accessibilityRole="header" style={styles.title}>
          {copy.title}
        </Text>
        <Text style={styles.message}>{copy.message}</Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: {
    gap: 14,
    paddingHorizontal: 16,
    paddingBottom: 32,
  },
  card: {
    alignItems: "center",
    gap: 10,
    borderRadius: 18,
    backgroundColor: "#FFFFFF",
    paddingHorizontal: 20,
    paddingVertical: 28,
  },
  title: {
    color: "#183142",
    fontSize: 20,
    fontWeight: "800",
    textAlign: "center",
  },
  message: {
    color: "#526A7B",
    fontSize: 14,
    lineHeight: 21,
    textAlign: "center",
  },
});
