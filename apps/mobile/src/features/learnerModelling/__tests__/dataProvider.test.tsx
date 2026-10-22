import { fireEvent, act, render, screen } from "@testing-library/react-native";

import { DashboardStateView } from "../components/DashboardStateView";
import {
  DashboardProviderError,
  demoDashboardProvider,
  unavailableLiveDashboardProvider,
  type Component4DashboardProvider,
} from "../data/dashboardProvider";
import { buildSyntheticDashboard } from "../preview/syntheticData";
import { EducatorAnalyticsScreen } from "../screens/EducatorAnalyticsScreen";
import { GuardianSummaryScreen } from "../screens/GuardianSummaryScreen";
import { LearnerProgressScreen } from "../screens/LearnerProgressScreen";
import type {
  DashboardPresentationStatus,
  LearnerDashboardPreview,
} from "../types";

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((promiseResolve) => {
    resolve = promiseResolve;
  });
  return { promise, resolve };
}

function createTestProvider(): Component4DashboardProvider {
  return {
    mode: "demo",
    loadLearnerProgress: jest.fn(async (periodDays) =>
      buildSyntheticDashboard("learner", periodDays),
    ),
    loadGuardianSummary: jest.fn(async (periodDays) =>
      buildSyntheticDashboard("guardian", periodDays),
    ),
    loadEducatorAnalytics: jest.fn(async (periodDays) =>
      buildSyntheticDashboard("educator", periodDays),
    ),
  };
}

describe("Component 4 dashboard providers", () => {
  it("returns deterministic demo projections without network access", async () => {
    const fetchSpy = jest.spyOn(globalThis, "fetch");

    const first = await demoDashboardProvider.loadLearnerProgress(30);
    const second = await demoDashboardProvider.loadLearnerProgress(30);
    const guardian = await demoDashboardProvider.loadGuardianSummary(30);
    const educator = await demoDashboardProvider.loadEducatorAnalytics(30);

    expect(first).toEqual(second);
    expect(first.role).toBe("learner");
    expect(guardian.role).toBe("guardian");
    expect(educator.role).toBe("educator");
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });

  it(
    "keeps the unavailable live boundary closed without a demo fallback",
    async () => {
      render(
        <LearnerProgressScreen periodDays={30} provider={unavailableLiveDashboardProvider} />,
      );

      await act(async () => {
        await Promise.resolve();
        await Promise.resolve();
      });

      expect(screen.getByText("Report temporarily unavailable")).toBeTruthy();
      expect(screen.queryByText("Sample Data")).toBeNull();
      expect(screen.queryByText("Hi, Reader!")).toBeNull();
    },
    15_000,
  );

  it("hides settled demo data synchronously when the provider changes", async () => {
    const liveRequest = createDeferred<LearnerDashboardPreview>();
    const liveProvider: Component4DashboardProvider = {
      ...createTestProvider(),
      mode: "live_unavailable",
      loadLearnerProgress: jest.fn(() => liveRequest.promise),
    };
    const view = render(<LearnerProgressScreen periodDays={30} />);

    expect(await screen.findByText("Hi, Reader!")).toBeTruthy();
    expect(screen.getByText("Sample Data")).toBeTruthy();

    view.rerender(<LearnerProgressScreen periodDays={30} provider={liveProvider} />);

    expect(screen.getByText("Loading reading report")).toBeTruthy();
    expect(screen.queryByText("Hi, Reader!")).toBeNull();
    expect(screen.queryByText("Sample Data")).toBeNull();
    view.unmount();
  });

  it("ignores a late demo result after switching to unavailable live mode", async () => {
    const demoRequest = createDeferred<LearnerDashboardPreview>();
    const demoProvider: Component4DashboardProvider = {
      ...createTestProvider(),
      loadLearnerProgress: jest.fn(() => demoRequest.promise),
    };
    const view = render(<LearnerProgressScreen periodDays={30} provider={demoProvider} />);

    expect(screen.getByText("Loading reading report")).toBeTruthy();
    expect(screen.getByText("Sample Data")).toBeTruthy();

    view.rerender(
      <LearnerProgressScreen periodDays={30} provider={unavailableLiveDashboardProvider} />,
    );
    expect(await screen.findByText("Report temporarily unavailable")).toBeTruthy();

    await act(async () => {
      demoRequest.resolve(buildSyntheticDashboard("learner", 30));
      await demoRequest.promise;
    });

    expect(screen.queryByText("Hi, Reader!")).toBeNull();
    expect(screen.queryByText("Sample Data")).toBeNull();
    expect(screen.getByText("Report temporarily unavailable")).toBeTruthy();
  });

  it("calls only the fixed learner projection method with the reporting period", async () => {
    const provider = createTestProvider();
    render(<LearnerProgressScreen periodDays={7} provider={provider} />);

    expect(await screen.findByText("Hi, Reader!")).toBeTruthy();
    expect(provider.loadLearnerProgress).toHaveBeenCalledWith(7);
    expect(provider.loadGuardianSummary).not.toHaveBeenCalled();
    expect(provider.loadEducatorAnalytics).not.toHaveBeenCalled();
  });

  it("calls only the fixed guardian projection method with the reporting period", async () => {
    const provider = createTestProvider();
    render(<GuardianSummaryScreen periodDays={30} provider={provider} />);

    expect(await screen.findByText("Guardian progress summary")).toBeTruthy();
    expect(provider.loadGuardianSummary).toHaveBeenCalledWith(30);
    expect(provider.loadLearnerProgress).not.toHaveBeenCalled();
    expect(provider.loadEducatorAnalytics).not.toHaveBeenCalled();
  });

  it("calls only the fixed educator projection method with the reporting period", async () => {
    const provider = createTestProvider();
    render(<EducatorAnalyticsScreen periodDays={90} provider={provider} />);

    fireEvent.press(await screen.findByRole("button", { name: "View separate example" }));
    expect(await screen.findByText("Educator reading analytics")).toBeTruthy();
    expect(provider.loadEducatorAnalytics).toHaveBeenCalledWith(90);
    expect(provider.loadLearnerProgress).not.toHaveBeenCalled();
    expect(provider.loadGuardianSummary).not.toHaveBeenCalled();
  });

  it("sanitizes unknown provider failures", async () => {
    const provider = createTestProvider();
    provider.loadLearnerProgress = jest.fn(async () => {
      throw new Error("SQL failure for private learner 00000000-0000-0000-0000-000000000123");
    });

    render(<LearnerProgressScreen periodDays={30} provider={provider} />);

    expect(await screen.findByText("Report temporarily unavailable")).toBeTruthy();
    expect(screen.queryByText(/SQL failure/)).toBeNull();
    expect(screen.queryByText(/00000000-0000-0000-0000-000000000123/)).toBeNull();
  });

  it("shows an empty state when a provider returns no included sessions", async () => {
    const provider = createTestProvider();
    provider.loadGuardianSummary = jest.fn(async () => ({
      ...buildSyntheticDashboard("guardian", 30),
      includedSessionCount: 0,
    }));

    render(<GuardianSummaryScreen periodDays={30} provider={provider} />);

    expect(await screen.findByText("No results for this period")).toBeTruthy();
    expect(screen.queryByText("Adaptive recommendation")).toBeNull();
  });

  it.each<[DashboardPresentationStatus, string]>([
    ["loading", "Loading reading report"],
    ["empty", "No results for this period"],
    ["consent_required", "Consent required"],
    ["learner_unavailable", "Learner unavailable"],
    ["temporarily_unavailable", "Report temporarily unavailable"],
    ["reporting_limit_exceeded", "Reporting limit exceeded"],
  ])("renders the %s display-only state", (status, title) => {
    render(<DashboardStateView state={{ status, provenance: "demo" }} />);

    expect(screen.getByText(title)).toBeTruthy();
    expect(screen.getByText("Sample Data")).toBeTruthy();
  });

  it("maps typed consent and authorization failures without evaluating either policy", async () => {
    const provider = createTestProvider();
    provider.loadLearnerProgress = jest
      .fn<ReturnType<Component4DashboardProvider["loadLearnerProgress"]>, []>()
      .mockRejectedValue(new DashboardProviderError("consent_required"));

    const { unmount } = render(<LearnerProgressScreen periodDays={30} provider={provider} />);
    expect(await screen.findByText("Consent required")).toBeTruthy();
    unmount();

    provider.loadLearnerProgress = jest
      .fn<ReturnType<Component4DashboardProvider["loadLearnerProgress"]>, []>()
      .mockRejectedValue(new DashboardProviderError("learner_unavailable"));
    render(<LearnerProgressScreen periodDays={30} provider={provider} />);
    expect(await screen.findByText("Learner unavailable")).toBeTruthy();
  });
});

it.each(["loadLearnerProgress", "loadGuardianSummary", "loadEducatorAnalytics"] as const)(
  "keeps %s inactive for every reporting period without network or synthetic fallback",
  async (method) => {
    const fetch = jest.spyOn(globalThis, "fetch");
    try {
      for (const days of [7, 30, 90] as const) {
        await expect(unavailableLiveDashboardProvider[method](days)).rejects.toMatchObject({
          name: "DashboardProviderError", failure: "temporarily_unavailable",
        });
      }
      expect(fetch).not.toHaveBeenCalled();
    } finally { fetch.mockRestore(); }
  },
);
