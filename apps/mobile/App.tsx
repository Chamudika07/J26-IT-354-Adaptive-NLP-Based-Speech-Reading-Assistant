import { useState } from "react";
import { StyleSheet, View } from "react-native";
import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context";

import { PeriodSelector } from "./src/features/learnerModelling/components/PeriodSelector";
import { RoleSwitcher } from "./src/features/learnerModelling/components/RoleSwitcher";
import { EducatorAnalyticsScreen } from "./src/features/learnerModelling/screens/EducatorAnalyticsScreen";
import { GuardianSummaryScreen } from "./src/features/learnerModelling/screens/GuardianSummaryScreen";
import { LearnerProgressScreen } from "./src/features/learnerModelling/screens/LearnerProgressScreen";
import type {
  PreviewRole,
  ReportingPeriodDays,
} from "./src/features/learnerModelling/types";

export default function App() {
  const [role, setRole] = useState<PreviewRole>("learner");
  const [periodDays, setPeriodDays] = useState<ReportingPeriodDays>(30);

  return (
    <SafeAreaProvider>
      <SafeAreaView edges={["top", "bottom"]} style={styles.safeArea}>
        <StatusBar style="dark" />
        <View style={styles.controls}>
          <RoleSwitcher selectedRole={role} onSelectRole={setRole} />
          <PeriodSelector selectedDays={periodDays} onSelectDays={setPeriodDays} />
        </View>
        {role === "learner" ? <LearnerProgressScreen periodDays={periodDays} /> : null}
        {role === "guardian" ? <GuardianSummaryScreen periodDays={periodDays} /> : null}
        {role === "educator" ? <EducatorAnalyticsScreen periodDays={periodDays} /> : null}
      </SafeAreaView>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: "#F4F7FB",
  },
  controls: {
    gap: 10,
    paddingHorizontal: 16,
    paddingBottom: 12,
    paddingTop: 12,
  },
});
