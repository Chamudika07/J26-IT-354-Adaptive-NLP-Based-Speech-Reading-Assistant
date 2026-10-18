import { useEffect, useState } from "react";

import { DashboardProviderError } from "./dashboardProvider";
import type {
  DashboardDataProvenance,
  DashboardPresentationState,
  DashboardPreview,
} from "../types";

interface RequestState<TDashboard extends DashboardPreview> {
  loadDashboard: () => Promise<TDashboard>;
  presentation: DashboardPresentationState<TDashboard>;
}

export function useDashboardPresentation<TDashboard extends DashboardPreview>(
  loadDashboard: () => Promise<TDashboard>,
  provenance: DashboardDataProvenance,
): DashboardPresentationState<TDashboard> {
  const [requestState, setRequestState] = useState<RequestState<TDashboard>>(() => ({
    loadDashboard,
    presentation: { status: "loading", provenance },
  }));

  useEffect(() => {
    let active = true;

    void loadDashboard()
      .then((dashboard) => {
        if (!active) {
          return;
        }
        setRequestState({
          loadDashboard,
          presentation:
            dashboard.includedSessionCount === 0
              ? { status: "empty", provenance }
              : { status: "ready", provenance, dashboard },
        });
      })
      .catch((error: unknown) => {
        if (!active) {
          return;
        }
        setRequestState({
          loadDashboard,
          presentation: {
            status:
              error instanceof DashboardProviderError
                ? error.failure
                : "temporarily_unavailable",
            provenance,
          },
        });
      });

    return () => {
      active = false;
    };
  }, [loadDashboard, provenance]);

  if (
    requestState.loadDashboard !== loadDashboard ||
    requestState.presentation.provenance !== provenance
  ) {
    return { status: "loading", provenance };
  }

  return requestState.presentation;
}
