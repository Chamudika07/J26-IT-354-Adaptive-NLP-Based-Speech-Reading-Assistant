import { useCallback } from "react";

import { DashboardStateView } from "../components/DashboardStateView";
import {
  demoDashboardProvider,
  type Component4DashboardProvider,
} from "../data/dashboardProvider";
import { useDashboardPresentation } from "../data/useDashboardPresentation";
import type { ReportingPeriodDays } from "../types";

interface GuardianSummaryScreenProps {
  periodDays: ReportingPeriodDays;
  provider?: Component4DashboardProvider;
}

export function GuardianSummaryScreen({
  periodDays,
  provider = demoDashboardProvider,
}: GuardianSummaryScreenProps) {
  const loadDashboard = useCallback(
    () => provider.loadGuardianSummary(periodDays),
    [periodDays, provider],
  );
  const state = useDashboardPresentation(loadDashboard, provider.mode);

  return <DashboardStateView state={state} />;
}
