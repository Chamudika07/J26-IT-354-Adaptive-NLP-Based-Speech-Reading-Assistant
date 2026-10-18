import { useCallback } from "react";

import { DashboardStateView } from "../components/DashboardStateView";
import {
  demoDashboardProvider,
  type Component4DashboardProvider,
} from "../data/dashboardProvider";
import { useDashboardPresentation } from "../data/useDashboardPresentation";
import type { ReportingPeriodDays } from "../types";

interface EducatorAnalyticsScreenProps {
  periodDays: ReportingPeriodDays;
  provider?: Component4DashboardProvider;
}

export function EducatorAnalyticsScreen({
  periodDays,
  provider = demoDashboardProvider,
}: EducatorAnalyticsScreenProps) {
  const loadDashboard = useCallback(
    () => provider.loadEducatorAnalytics(periodDays),
    [periodDays, provider],
  );
  const state = useDashboardPresentation(loadDashboard, provider.mode);

  return <DashboardStateView state={state} />;
}
