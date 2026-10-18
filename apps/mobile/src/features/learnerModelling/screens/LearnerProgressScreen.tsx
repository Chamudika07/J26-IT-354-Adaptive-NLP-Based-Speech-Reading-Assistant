import { useCallback } from "react";

import { DashboardStateView } from "../components/DashboardStateView";
import {
  demoDashboardProvider,
  type Component4DashboardProvider,
} from "../data/dashboardProvider";
import { useDashboardPresentation } from "../data/useDashboardPresentation";
import type { ReportingPeriodDays } from "../types";

interface LearnerProgressScreenProps {
  periodDays: ReportingPeriodDays;
  provider?: Component4DashboardProvider;
}

export function LearnerProgressScreen({
  periodDays,
  provider = demoDashboardProvider,
}: LearnerProgressScreenProps) {
  const loadDashboard = useCallback(
    () => provider.loadLearnerProgress(periodDays),
    [periodDays, provider],
  );
  const state = useDashboardPresentation(loadDashboard, provider.mode);

  return <DashboardStateView state={state} />;
}
