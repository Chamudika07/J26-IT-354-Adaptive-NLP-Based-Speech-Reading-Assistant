import { render, screen, within } from "@testing-library/react-native";

import { MetricChart } from "../components/MetricChart";
import { PreviewDashboard } from "../components/PreviewDashboard";
import { buildSyntheticDashboard } from "../preview/syntheticData";

it.each([7, 30, 90] as const)("preserves learner observations in the playful %d-day report", (days) => {
  const dashboard = buildSyntheticDashboard("learner", days);
  render(<PreviewDashboard dashboard={dashboard} demoMode />);

  expect(screen.getByText("Hi, reader!")).toBeTruthy();
  expect(screen.getByRole("image", { name: "ReadBuddy smiling book character" })).toBeTruthy();
  expect(screen.getByText("Sample Data")).toBeTruthy();
  expect(screen.getByText("ADVISORY ONLY")).toBeTruthy();
  expect(screen.getByText(dashboard.recommendation.supportSuggestion)).toBeTruthy();
  expect(screen.getByText(dashboard.recommendation.explanation)).toBeTruthy();
  expect(screen.getByText("Review this suggestion with a parent or teacher before making changes.")).toBeTruthy();

  for (const metric of dashboard.metrics) {
    const card = within(screen.getByTestId(`${metric.key}-card`));
    expect(card.getByText(metric.label)).toBeTruthy();
    expect(card.getByText(metric.unit)).toBeTruthy();
    expect(card.getByText(metric.explanation)).toBeTruthy();
    expect(card.getByText(metric.evidenceLabel)).toBeTruthy();
    const latest = metric.key === "reading_accuracy" ? `${metric.latestValue}%` : String(metric.latestValue);
    expect(card.getAllByText(latest)).toHaveLength(2);
  }
  for (const observation of dashboard.difficultyProgression) {
    expect(screen.getByText(observation.explanation)).toBeTruthy();
  }
  expect(screen.queryByText("advanced")).toBeNull();
  if (days === 7) {
    expect(screen.getAllByText("We need a little more reading practice to see a clear trend.")).toHaveLength(3);
    expect(screen.queryByText(/Demo data shows/)).toBeNull();
  } else {
    expect(screen.getByText("Demo data shows more words read correctly.")).toBeTruthy();
    expect(screen.getByText("Demo data shows more words read each minute.")).toBeTruthy();
    expect(screen.getByText("Demo data shows fewer pauses per 100 attempted words.")).toBeTruthy();
  }
});

it.each(["no_observed_change", "decreased", "insufficient_evidence"] as const)(
  "does not celebrate accuracy when direction is %s",
  (changeDirection) => {
    const metric = { ...buildSyntheticDashboard("learner", 30).metrics[0]!, changeDirection };
    render(<MetricChart metric={metric} playful />);
    expect(screen.queryByText("Demo data shows more words read correctly.")).toBeNull();
    expect(screen.getByText(metric.explanation)).toBeTruthy();
  },
);

it.each(["guardian", "educator"] as const)("keeps the %s report detailed rather than child-directed", (role) => {
  const dashboard = role === "guardian"
    ? buildSyntheticDashboard("guardian", 30)
    : buildSyntheticDashboard("educator", 30);
  render(<PreviewDashboard dashboard={dashboard} demoMode />);
  expect(screen.getByText(dashboard.subtitle)).toBeTruthy();
  expect(screen.queryByText("Hi, reader!")).toBeNull();
  expect(screen.queryByText(/Demo data shows/)).toBeNull();
  for (const metric of dashboard.metrics) {
    const card = within(screen.getByTestId(`${metric.key}-card`));
    expect(card.getByText(metric.detail!)).toBeTruthy();
    expect(card.getByText(metric.evidenceLabel)).toBeTruthy();
  }
});
