import { useCallback } from "react";
import { DashboardModeBoundary, type LiveScreenProps } from "../components/DashboardModeBoundary";

import { LearnerNavigation } from "../navigation/LearnerNavigation";
import {
  demoDashboardProvider,
  type Component4DashboardProvider,
} from "../data/dashboardProvider";
import { useDashboardPresentation } from "../data/useDashboardPresentation";
import type { ReportingPeriodDays } from "../types";

interface LearnerProgressScreenProps extends LiveScreenProps {
  periodDays: ReportingPeriodDays;
  provider?: Component4DashboardProvider;
}

export function LearnerProgressScreen(props: LearnerProgressScreenProps) {
  return <DashboardModeBoundary {...props} role="learner"><DemoLearnerProgressScreen {...props} /></DashboardModeBoundary>;
}

function DemoLearnerProgressScreen({
  periodDays,
  provider = demoDashboardProvider,
}: LearnerProgressScreenProps) {
  const loadDashboard = useCallback(
    () => provider.loadLearnerProgress(periodDays),
    [periodDays, provider],
  );
  const state = useDashboardPresentation(loadDashboard, provider.mode);

  return <LearnerNavigation state={state} periodDays={periodDays} />;
}
