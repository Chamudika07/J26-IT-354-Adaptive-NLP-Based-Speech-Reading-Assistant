import { fireEvent, render, screen, within } from "@testing-library/react-native";
import { StyleSheet } from "react-native";

import App from "../../../../App";
import { MetricChart } from "../components/MetricChart";
import { PreviewDashboard } from "../components/PreviewDashboard";
import { PeriodSelector } from "../components/PeriodSelector";
import { buildSyntheticDashboard } from "../preview/syntheticData";

it.each(["learner", "guardian", "educator"] as const)("preserves every %s metric and evidence field in the redesigned dashboard", (role) => {
  const dashboard = role === "learner" ? buildSyntheticDashboard("learner", 7) : role === "guardian" ? buildSyntheticDashboard("guardian", 7) : buildSyntheticDashboard("educator", 7);
  render(<PreviewDashboard dashboard={dashboard} demoMode />);
  expect(screen.getByText("Sample Data")).toBeTruthy();
  if (role === "learner") expect(screen.getByText("ADVISORY ONLY")).toBeTruthy();
  else expect(screen.queryByText("ADVISORY ONLY")).toBeNull();
  expect(screen.getByText("Reading journey")).toBeTruthy();
  expect(screen.getByLabelText("ReadBuddy smiling book character")).toBeTruthy();
  for (const metric of dashboard.metrics) {
    const card = within(screen.getByTestId(`${metric.key}-card`));
    expect(card.getByText(metric.label)).toBeTruthy();
    expect(card.getByText(metric.unit)).toBeTruthy();
    expect(card.getByText(metric.explanation)).toBeTruthy();
    expect(card.getByText(metric.evidenceLabel)).toBeTruthy();
    if (metric.detail) expect(card.getByText(metric.detail)).toBeTruthy();
  }
  expect(screen.getAllByText("More evidence needed")).toHaveLength(3);
  expect(screen.queryByText(/Early-window mean/)).toBeNull();
  for (const note of dashboard.limitations) expect(screen.getByText("• " + note)).toBeTruthy();
});

it("keeps zero observations at zero width and accuracy on a percentage scale", () => {
  const metric = { ...buildSyntheticDashboard("learner", 30).metrics[0]!, firstValue: 0 };
  render(<MetricChart metric={metric} />);
  expect(StyleSheet.flatten(screen.getByTestId("reading_accuracy-first-bar").props.style).width).toBe("0%");
  expect(StyleSheet.flatten(screen.getByTestId("reading_accuracy-latest-bar").props.style).width).toBe("86%");
  expect(screen.getByText(/Bars use a 0-100% scale/)).toBeTruthy();
});

it("provides comfortable reporting-period targets and selected states", () => {
  const select = jest.fn();
  render(<PeriodSelector selectedDays={30} onSelectDays={select} />);
  for (const days of [7, 30, 90]) {
    const radio = screen.getByRole("radio", { name: days + " day reporting period" });
    expect(radio.props.accessibilityState.checked).toBe(days === 30);
    expect(StyleSheet.flatten(radio.props.style).minHeight).toBeGreaterThanOrEqual(48);
    fireEvent.press(radio);
    expect(select).toHaveBeenLastCalledWith(days);
  }
});

it("retains the selected period when switching synthetic roles", async () => {
  render(<App />);
  await screen.findByText("Hi, Reader!");
  fireEvent.press(screen.getByRole("radio", { name: "7 day reporting period" }));
  await screen.findByText("4");
  fireEvent.press(screen.getByRole("tab", { name: "Educator sample preview" }));
  fireEvent.press(await screen.findByRole("button", { name: "View separate example" }));
  await screen.findByText("Educator reading analytics");
  expect(screen.getByRole("radio", { name: "7 day reporting period" }).props.accessibilityState.checked).toBe(true);
  expect(screen.getByRole("tab", { name: "Educator sample preview" }).props.accessibilityState.selected).toBe(true);
  expect(screen.getAllByText(/no window averages were calculated/)).toHaveLength(3);
  fireEvent.press(screen.getByRole("radio", { name: "90 day reporting period" }));
  await screen.findAllByText("15");
  expect(screen.getAllByText(/Early-window mean/)).toHaveLength(3);
});
