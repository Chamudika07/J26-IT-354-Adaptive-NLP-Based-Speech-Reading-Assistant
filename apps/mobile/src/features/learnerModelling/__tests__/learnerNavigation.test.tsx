import { act, fireEvent, render, screen, within } from "@testing-library/react-native";
import { BackHandler, StyleSheet } from "react-native";
import { publishScenario } from "../preview/selectedScenario";

import App from "../../../../App";
import { unavailableLiveDashboardProvider, type Component4DashboardProvider } from "../data/dashboardProvider";
import { LearnerNavigation } from "../navigation/LearnerNavigation";
import { buildSyntheticDashboard } from "../preview/syntheticData";
import { LearnerProgressScreen } from "../screens/LearnerProgressScreen";
import type { DashboardPresentationStatus, LearnerDashboardPreview } from "../types";

afterEach(() => jest.restoreAllMocks());

it("opens four destinations with selected tabs, discovery links and a consistent Home action", async () => {
  render(<App />);
  await screen.findByText("Hi, Reader!");
  expect(within(screen.getByRole("button", { name: "Open My Reading Report" })).getByText(
    "View your demo reading report or a saved local AI-generated preview.",
  )).toBeTruthy();
  expect(screen.getByRole("tab", { name: "Home learner view" }).props.accessibilityState.selected).toBe(true);
  for (const [tab, title] of [
    ["Analytics", "My Reading Analytics"],
    ["Suggestions", "My Reading Tips"],
    ["Profile", "My Profile"],
  ]) {
    fireEvent.press(screen.getByRole("tab", { name: `${tab} learner view` }));
    expect(screen.getByRole("header", { name: title })).toBeTruthy();
    expect(screen.getByRole("tab", { name: `${tab} learner view` }).props.accessibilityState.selected).toBe(true);
    expect(screen.getByText(tab === "Analytics" ? "Demo \u00b7 Fictional data" : "Sample Data")).toBeTruthy();
    const home = screen.getByRole("tab", { name: "Home learner view" });
    expect(home.props.accessibilityState.selected).toBe(false);
    expect(StyleSheet.flatten(home.props.style).minHeight).toBeGreaterThanOrEqual(48);
    fireEvent.press(screen.getByRole("button", { name: "Back to reading Home" }));
    expect(screen.getByText("Hi, Reader!")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Back to reading Home" })).toBeNull();
  }
});

it("uses the shared reporting controls on Progress and retains the period across destinations", async () => {
  render(<App />);
  await screen.findByText("Hi, Reader!");
  fireEvent.press(screen.getByRole("tab", { name: "Analytics learner view" }));
  for (const days of [7, 30, 90] as const) {
    fireEvent.press(screen.getByRole("radio", { name: `${days} day reporting period` }));
    const hide = screen.queryByRole("button", { name: "Hide result details" });
    if (!hide) fireEvent.press(await screen.findByRole("button", { name: "About these results" }));
    await screen.findByText(new RegExp(`${days}-day reporting period`));
    const history = screen.queryByRole("button", { name: "View Reading History" });
    if (history) fireEvent.press(history);
    const dashboard = buildSyntheticDashboard("learner", days);
    for (const metric of dashboard.metrics) {
      expect(screen.getByText(metric.explanation)).toBeTruthy();
      expect(screen.getAllByText(`${metric.validObservationCount} valid observations \u00b7 ${metric.missingObservationCount} missing measurements`).length).toBeGreaterThan(0);
    }
    expect(screen.getByText(/This overview has no session-by-session history/)).toBeTruthy();

  }
  fireEvent.press(screen.getByRole("tab", { name: "Suggestions learner view" }));
  expect(screen.getByText("90-day reporting period")).toBeTruthy();
  expect(screen.getByText("ADVISORY ONLY")).toBeTruthy();
  expect(screen.getByText(buildSyntheticDashboard("learner", 90).recommendation.supportSuggestion)).toBeTruthy();
  expect(screen.getByText("Review this suggestion with a parent or teacher before making changes.")).toBeTruthy();
  fireEvent.press(screen.getByRole("tab", { name: "Profile learner view" }));
  expect(screen.getByText("90-day reporting period")).toBeTruthy();
  expect(screen.getByText("Latest observed difficulty: intermediate")).toBeTruthy();
  expect(screen.getByText("Choose your reading settings.")).toBeTruthy();
  expect(screen.getByText(/Your demo choices stay on this device/)).toBeTruthy();
  expect(screen.queryByRole("switch")).toBeNull();
});

it("keeps observed difficulty and missing preference states distinct when no observations exist", () => {
  const dashboard = { ...buildSyntheticDashboard("learner", 30), difficultyProgression: [] };
  render(<LearnerNavigation state={{ status: "ready", provenance: "demo", dashboard }} periodDays={30} />);
  fireEvent.press(screen.getByRole("tab", { name: "Profile learner view" }));
  expect(screen.getByText("Observed difficulty unavailable.")).toBeTruthy();
  expect(screen.getByText("Choose your reading settings.")).toBeTruthy();
  expect(screen.queryByText("Latest observed difficulty: intermediate")).toBeNull();
});

it.each<DashboardPresentationStatus>([
  "loading", "empty", "consent_required", "learner_unavailable", "temporarily_unavailable", "reporting_limit_exceeded",
])("retains the %s state rather than showing destination data", (status) => {
  render(<LearnerNavigation state={{ status, provenance: "demo" }} periodDays={30} />);
  for (const tab of ["Analytics", "Suggestions", "Profile"]) {
    fireEvent.press(screen.getByRole("tab", { name: `${tab} learner view` }));
    expect(screen.getByText("Sample Data")).toBeTruthy();
    expect(screen.queryByText("ADVISORY ONLY")).toBeNull();
    expect(screen.queryByText("Latest observed difficulty: intermediate")).toBeNull();
    expect(screen.queryByTestId("reading_accuracy-card")).toBeNull();
  }
});

it("removes settled Suggestions data immediately when the provider changes to unavailable live", async () => {
  const view = render(<LearnerProgressScreen periodDays={30} />);
  await screen.findByText("Hi, Reader!");
  fireEvent.press(screen.getByRole("tab", { name: "Suggestions learner view" }));
  expect(screen.getByText("ADVISORY ONLY")).toBeTruthy();
  view.rerender(<LearnerProgressScreen periodDays={30} provider={unavailableLiveDashboardProvider} />);
  expect(screen.queryByText("ADVISORY ONLY")).toBeNull();
  expect(screen.queryByText("Sample Data")).toBeNull();
  expect(await screen.findByText("Report temporarily unavailable")).toBeTruthy();
});

it("ignores a late demo request while Profile is selected in unavailable live mode", async () => {
  let resolve!: (dashboard: LearnerDashboardPreview) => void;
  const request = new Promise<LearnerDashboardPreview>((finish) => { resolve = finish; });
  const provider: Component4DashboardProvider = {
    ...unavailableLiveDashboardProvider, mode: "demo", loadLearnerProgress: () => request,
  };
  const view = render(<LearnerProgressScreen periodDays={7} provider={provider} />);
  fireEvent.press(screen.getByRole("tab", { name: "Profile learner view" }));
  view.rerender(<LearnerProgressScreen periodDays={7} provider={unavailableLiveDashboardProvider} />);
  await screen.findByText("Report temporarily unavailable");
  await act(async () => { resolve(buildSyntheticDashboard("learner", 7)); await request; });
  expect(screen.queryByText("Sample Data")).toBeNull();
  expect(screen.queryByText("Latest observed difficulty: intermediate")).toBeNull();
});

it("returns to Home on Android Back and leaves root Back to the host", () => {
  const remove = jest.fn();
  const back = jest.spyOn(BackHandler, "addEventListener").mockReturnValue({ remove });
  const view = render(<LearnerNavigation state={{ status: "loading", provenance: "demo" }} periodDays={30} />);
  const event = { type: "hardwareBackPress", timeStamp: 0 };
  expect(back.mock.calls.at(-1)?.[1](event)).toBe(false);
  fireEvent.press(screen.getByRole("tab", { name: "Analytics learner view" }));
  act(() => { expect(back.mock.calls.at(-1)?.[1](event)).toBe(true); });
  expect(screen.getByRole("tab", { name: "Home learner view" }).props.accessibilityState.selected).toBe(true);
  view.unmount();
  expect(remove).toHaveBeenCalled();
});

it.each([
  [7, [[4, 0], [4, 0], [3, 1]]],
  [30, [[9, 0], [9, 0], [8, 1]]],
  [90, [[15, 0], [14, 1], [13, 2]]],
] as const)("exposes the original %d-day observation counts without changing role projections", (days, counts) => {
  const learner = buildSyntheticDashboard("learner", days);
  const guardian = buildSyntheticDashboard("guardian", days);
  const educator = buildSyntheticDashboard("educator", days);
  for (const dashboard of [learner, guardian, educator]) {
    expect(dashboard.metrics.map((metric) => [metric.validObservationCount, metric.missingObservationCount])).toEqual(counts);
    expect(dashboard.metrics.every((metric) => metric.validObservationCount! + metric.missingObservationCount! === dashboard.includedSessionCount)).toBe(true);
  }
  expect(learner.metrics.every((metric) => metric.detail === undefined)).toBe(true);
  expect(educator.metrics.every((metric) => metric.detail?.includes("formula version v1"))).toBe(true);
});

it("shows unavailable counts instead of inferring zeros from display text", () => {
  const dashboard = buildSyntheticDashboard("learner", 30);
  dashboard.metrics = dashboard.metrics.map((metric) => ({
    ...metric, validObservationCount: undefined, missingObservationCount: undefined,
  }));
  render(<LearnerNavigation state={{ status: "ready", provenance: "demo", dashboard }} periodDays={30} />);
  fireEvent.press(screen.getByRole("tab", { name: "Analytics learner view" }));
  fireEvent.press(screen.getByRole("button", { name: "About these results" }));
  expect(screen.getAllByText("Valid observation count unavailable. · Missing measurement count unavailable.")).toHaveLength(3);
});


it("starts reading from the compact Home action without changing the sample source", async () => {
  render(<App />);
  await screen.findByText("Hi, Reader!");
  expect(screen.getByText("Let's grow your reading skills!")).toBeTruthy();
  expect(screen.getByText("Completed Sessions")).toBeTruthy();
  expect(screen.getByText("Reading Accuracy (%)")).toBeTruthy();
  expect(screen.getByText("Reading Speed (WPM)")).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "Reading Results" }));
  expect(screen.getByRole("button", { name: "Update My Progress" })).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Start Demo Reading Journey" })).toBeNull();
});

beforeEach(() => { publishScenario(null); });
