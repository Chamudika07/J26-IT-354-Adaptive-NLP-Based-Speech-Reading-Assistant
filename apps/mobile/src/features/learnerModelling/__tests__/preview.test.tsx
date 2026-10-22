import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";

import App from "../../../../App";
import { buildSyntheticDashboard } from "../preview/syntheticData";
import type { ReportingPeriodDays } from "../types";

const PERIODS: readonly ReportingPeriodDays[] = [7, 30, 90];

describe("Component 4 synthetic mobile preview", () => {
  it("shows an explicit synthetic-data banner and advisory-only recommendation", async () => {
    render(<App />);

    expect(screen.getByText("Sample Data")).toBeTruthy();
    expect(await screen.findByText("Hi, Reader!")).toBeTruthy();
    expect(await screen.findByText("ADVISORY ONLY")).toBeTruthy();
    expect(
      screen.getByText("This preview never applies a learner-setting change automatically."),
    ).toBeTruthy();
  });

  it("switches only among fixed synthetic role projections", async () => {
    render(<App />);

    await screen.findByText("Hi, Reader!");

    fireEvent.press(screen.getByRole("tab", { name: "Guardian sample preview" }));
    expect(await screen.findByText("Parent Dashboard")).toBeTruthy();
    expect(screen.queryByText("Hi, Reader!")).toBeNull();

    fireEvent.press(screen.getByRole("tab", { name: "Educator sample preview" }));
    fireEvent.press(await screen.findByRole("button", { name: "View separate example" }));
    expect(await screen.findByText("Educator reading analytics")).toBeTruthy();
    expect(screen.getAllByText(/formula version v1/)).toHaveLength(3);
  });

  it("updates the deterministic bounded reporting-period preview", async () => {
    render(<App />);

    expect(await screen.findByText("9")).toBeTruthy();
    fireEvent.press(screen.getByRole("radio", { name: "90 day reporting period" }));
    await waitFor(() => expect(screen.getAllByText("15").length).toBeGreaterThan(0));

    const first = buildSyntheticDashboard("learner", 90);
    const second = buildSyntheticDashboard("learner", 90);
    expect(first).toEqual(second);
    expect(first.reportingStartUtc).toBe("2026-07-17T12:00:00.000Z");
  });

  it("keeps educator-only detail out of learner and guardian models", () => {
    const learner = buildSyntheticDashboard("learner", 30);
    const guardian = buildSyntheticDashboard("guardian", 30);
    const educator = buildSyntheticDashboard("educator", 30);

    expect(learner.metrics.every((metric) => metric.detail === undefined)).toBe(true);
    expect(guardian.metrics.every((metric) => !metric.detail?.includes("formula version"))).toBe(
      true,
    );
    expect(educator.metrics.some((metric) => metric.detail?.includes("formula version"))).toBe(
      true,
    );
  });

  it.each(PERIODS)("keeps every %d-day projection internally consistent", (periodDays) => {
    const dashboards = [
      buildSyntheticDashboard("learner", periodDays),
      buildSyntheticDashboard("guardian", periodDays),
      buildSyntheticDashboard("educator", periodDays),
    ] as const;
    const [learner, guardian, educator] = dashboards;
    expect(learner).toBeDefined();
    expect(guardian).toBeDefined();
    expect(educator).toBeDefined();
    if (!learner || !guardian || !educator) {
      return;
    }

    expect(dashboards.map((dashboard) => dashboard.includedSessionCount)).toEqual([
      learner.includedSessionCount,
      learner.includedSessionCount,
      learner.includedSessionCount,
    ]);
    expect(guardian.metrics).toHaveLength(learner.metrics.length);
    expect(educator.metrics).toHaveLength(learner.metrics.length);

    const reportingStart = Date.parse(learner.reportingStartUtc);
    const reportingEnd = Date.parse(learner.reportingEndUtc);
    for (const dashboard of dashboards) {
      expect(dashboard.difficultyProgression.length).toBeGreaterThan(0);
      for (const observation of dashboard.difficultyProgression) {
        const observedAt = Date.parse(observation.observedAt);
        expect(observedAt).toBeGreaterThanOrEqual(reportingStart);
        expect(observedAt).toBeLessThanOrEqual(reportingEnd);
      }
    }

    learner.metrics.forEach((metric, index) => {
      expect(metric.detail).toBeUndefined();
      expect(metric.explanation).toContain(String(metric.firstValue));
      expect(metric.explanation).toContain(String(metric.latestValue));

      const guardianMetric = guardian.metrics[index];
      const educatorMetric = educator.metrics[index];
      expect(guardianMetric).toBeDefined();
      expect(educatorMetric).toBeDefined();
      if (!guardianMetric || !educatorMetric) {
        return;
      }
      expect(guardianMetric.firstValue).toBe(metric.firstValue);
      expect(guardianMetric.latestValue).toBe(metric.latestValue);
      expect(guardianMetric.changeDirection).toBe(metric.changeDirection);
      expect(educatorMetric.firstValue).toBe(metric.firstValue);
      expect(educatorMetric.latestValue).toBe(metric.latestValue);
      expect(educatorMetric.changeDirection).toBe(metric.changeDirection);

      const guardianCounts = guardianMetric.detail?.match(
        /^(\d+) valid observations; (?:(\d+) missing measurements?|no missing measurements)\.$/,
      );
      expect(guardianCounts).not.toBeNull();
      const validCount = Number(guardianCounts?.[1]);
      const missingCount = Number(guardianCounts?.[2] ?? 0);
      expect(validCount + missingCount).toBe(learner.includedSessionCount);

      const educatorCounts = educatorMetric.detail?.match(
        /windows contain (\d+) and (\d+) comparable observations/,
      );
      expect(educatorCounts).not.toBeNull();
      const earlyCount = Number(educatorCounts?.[1]);
      const lateCount = Number(educatorCounts?.[2]);
      expect(earlyCount + lateCount).toBeLessThanOrEqual(validCount);
      expect(earlyCount).toBeLessThanOrEqual(3);
      expect(lateCount).toBeLessThanOrEqual(3);
      if (metric.changeDirection === "insufficient_evidence") {
        expect(earlyCount).toBe(0);
        expect(lateCount).toBe(0);
        expect(educatorMetric.detail).not.toContain("Early-window mean");
        expect(educatorMetric.detail).not.toContain("late-window mean");
        expect(educatorMetric.detail).toContain("no window averages were calculated");
      } else {
        expect(earlyCount).toBe(3);
        expect(lateCount).toBe(3);
        expect(educatorMetric.detail).toContain("Early-window mean");
        expect(educatorMetric.detail).toContain("late-window mean");
      }
      expect(educatorMetric.detail).toContain("formula version v1");
    });

    expect(guardian.difficultyProgression).toEqual(learner.difficultyProgression);
    expect(educator.difficultyProgression).toEqual(learner.difficultyProgression);
    expect(guardian.recommendation).toEqual(learner.recommendation);
    expect(educator.recommendation).toEqual(learner.recommendation);
  });

  it("does not expose comparison results for the insufficient seven-day sequence", () => {
    const learner = buildSyntheticDashboard("learner", 7);
    const educator = buildSyntheticDashboard("educator", 7);

    expect(learner.includedSessionCount).toBe(4);
    expect(
      learner.metrics.every((metric) => metric.changeDirection === "insufficient_evidence"),
    ).toBe(true);
    expect(learner.metrics.every((metric) => metric.evidenceLabel.startsWith("Insufficient"))).toBe(
      true,
    );
    expect(
      educator.metrics.every(
        (metric) =>
          metric.detail?.includes("windows contain 0 and 0 comparable observations") &&
          metric.detail.includes("no window averages were calculated") &&
          !metric.detail.includes("Early-window mean") &&
          !metric.detail.includes("late-window mean"),
      ),
    ).toBe(true);
    expect(learner.recommendation.action).toBe("maintain");
    expect(learner.recommendation.reasonCodes).toContain("short_term_fluctuation");
  });
});
