import { RoleScenarioView } from "../components/RoleScenarioView";
import { useCallback } from "react";
import { DashboardModeBoundary, type LiveScreenProps } from "../components/DashboardModeBoundary";

import { DashboardStateView } from "../components/DashboardStateView";
import {
  demoDashboardProvider,
  type Component4DashboardProvider,
} from "../data/dashboardProvider";
import { useDashboardPresentation } from "../data/useDashboardPresentation";
import type { ReportingPeriodDays } from "../types";

interface GuardianSummaryScreenProps extends LiveScreenProps {
  periodDays: ReportingPeriodDays;
  provider?: Component4DashboardProvider;
}

export function GuardianSummaryScreen(props: GuardianSummaryScreenProps) {
  return <DashboardModeBoundary {...props} role="guardian"><DemoGuardianSummaryScreen {...props} /></DashboardModeBoundary>;
}

function DemoGuardianSummaryScreen({
  periodDays,
  provider = demoDashboardProvider,
}: GuardianSummaryScreenProps) {
  const loadDashboard = useCallback(
    () => provider.loadGuardianSummary(periodDays),
    [periodDays, provider],
  );
  const state = useDashboardPresentation(loadDashboard, provider.mode);

  const fallback = <DashboardStateView state={state} />;
  return state.status === "ready" && state.provenance === "demo" && state.dashboard.role === "guardian"
    ? <RoleScenarioView role="guardian">{fallback}</RoleScenarioView> : fallback;
}
