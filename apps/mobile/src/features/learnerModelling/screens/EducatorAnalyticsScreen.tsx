import { EducatorStudents } from "../components/EducatorStudents";
import { useCallback } from "react";
import { DashboardModeBoundary, type LiveScreenProps } from "../components/DashboardModeBoundary";

import { DashboardStateView } from "../components/DashboardStateView";
import {
  demoDashboardProvider,
  type Component4DashboardProvider,
} from "../data/dashboardProvider";
import { useDashboardPresentation } from "../data/useDashboardPresentation";
import type { ReportingPeriodDays } from "../types";

interface EducatorAnalyticsScreenProps extends LiveScreenProps {
  periodDays: ReportingPeriodDays;
  provider?: Component4DashboardProvider;
}

export function EducatorAnalyticsScreen(props: EducatorAnalyticsScreenProps) {
  return <DashboardModeBoundary {...props} role="educator"><DemoEducatorAnalyticsScreen {...props} /></DashboardModeBoundary>;
}

function DemoEducatorAnalyticsScreen({
  periodDays,
  provider = demoDashboardProvider,
}: EducatorAnalyticsScreenProps) {
  const loadDashboard = useCallback(
    () => provider.loadEducatorAnalytics(periodDays),
    [periodDays, provider],
  );
  const state = useDashboardPresentation(loadDashboard, provider.mode);

  const fallback = <DashboardStateView state={state} />;
  const enabled = state.status === "ready" && state.provenance === "demo" && state.dashboard.role === "educator";
  return <EducatorStudents enabled={enabled}>{fallback}</EducatorStudents>;
}
