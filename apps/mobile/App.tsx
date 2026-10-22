import { useState } from "react";
import { StyleSheet, View } from "react-native";
import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context";

import { HomePresentationContext } from "./src/features/learnerModelling/navigation/HomePresentation";
import { PeriodSelector } from "./src/features/learnerModelling/components/PeriodSelector";
import { Component4AccountBoundary } from "./src/features/learnerModelling/components/Component4AccountBoundary";
import { RoleSwitcher } from "./src/features/learnerModelling/components/RoleSwitcher";
import { EducatorAnalyticsScreen } from "./src/features/learnerModelling/screens/EducatorAnalyticsScreen";
import { GuardianSummaryScreen } from "./src/features/learnerModelling/screens/GuardianSummaryScreen";
import { LearnerProgressScreen } from "./src/features/learnerModelling/screens/LearnerProgressScreen";
import type {
  PreviewRole,
  ReportingPeriodDays,
} from "./src/features/learnerModelling/types";

export default function App() {
  const [learnerHome, setLearnerHome] = useState(true);
  const [role, setRole] = useState<PreviewRole>("learner");
  const [periodDays, setPeriodDays] = useState<ReportingPeriodDays>(30);

  const compactHome = role === "learner" && learnerHome;

  return (
    <SafeAreaProvider>
      <SafeAreaView edges={["top", "bottom"]} style={styles.safeArea}>
        <StatusBar style="dark" />
        <HomePresentationContext.Provider value={setLearnerHome}>
        <Component4AccountBoundary compactHome={compactHome} periodDays={periodDays} onSelectDays={setPeriodDays}>
        <View style={[styles.controls, compactHome && styles.homeControls]}>
          <RoleSwitcher compact={compactHome} selectedRole={role} onSelectRole={setRole} />
          <PeriodSelector compact={compactHome} selectedDays={periodDays} onSelectDays={setPeriodDays} />
        </View>
        {role === "learner" ? <LearnerProgressScreen periodDays={periodDays} /> : null}
        {role === "guardian" ? <GuardianSummaryScreen periodDays={periodDays} /> : null}
        {role === "educator" ? <EducatorAnalyticsScreen periodDays={periodDays} /> : null}
        </Component4AccountBoundary>
        </HomePresentationContext.Provider>
      </SafeAreaView>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: "#F4F7FB",
  },
  homeControls: { gap: 4, paddingTop: 0, paddingBottom: 6 },
  controls: {
    gap: 10,
    paddingHorizontal: 16,
    paddingBottom: 12,
    paddingTop: 12,
  },
});
