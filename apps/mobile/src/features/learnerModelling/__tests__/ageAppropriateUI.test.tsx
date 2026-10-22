import { act, fireEvent, render, screen, within } from "@testing-library/react-native";
import * as Native from "react-native";

import { LearnerNavigation } from "../navigation/LearnerNavigation";
import { buildSyntheticDashboard } from "../preview/syntheticData";
import { LearnerHomeScreen } from "../screens/LearnerHomeScreen";
import { PreviewSessionBoundary } from "../preview/PreviewSession";
import { SessionFeedbackScreen } from "../screens/SessionFeedbackScreen";
import { palette } from "../theme";

const initialDimensions = { window: Native.Dimensions.get("window"), screen: Native.Dimensions.get("screen") };
afterEach(() => {
  jest.restoreAllMocks();
  Native.Dimensions.set(initialDimensions);
});

it("prioritizes metrics before the feature menu and keeps evidence visible on Home", () => {
  const dashboard = buildSyntheticDashboard("learner", 7);
  render(<LearnerHomeScreen dashboard={dashboard} demoMode periodDays={7} onNavigate={jest.fn()} />);
  expect(screen.getByText("Hi, Reader!")).toBeTruthy();
  expect(screen.queryByText(/little reader|grown-up/)).toBeNull();
  expect(screen.getByRole("image", { name: "ReadBuddy smiling book character" })).toBeTruthy();
  expect(screen.getAllByText(/^(Reading progress|Explore your reading)$/).map((element) => element.props.children))
    .toEqual(["Reading progress", "Explore your reading"]);
  for (const metric of dashboard.metrics) {
    const card = within(screen.getByTestId(`${metric.key}-card`));
    expect(card.getByText(metric.unit)).toBeTruthy();
    expect(card.getByText(metric.evidenceLabel)).toBeTruthy();
    expect(card.getByText("We need a little more reading practice to see a clear trend.")).toBeTruthy();
    fireEvent.press(card.getByRole("button", { name: `Show ${metric.label} details` }));
    expect(card.getByText(metric.explanation)).toBeTruthy();
  }
  expect(screen.queryByText(/Demo data shows/)).toBeNull();
  expect(screen.getByText("ADVISORY ONLY")).toBeTruthy();
});

it("uses one-column feature cards and wrapped navigation on narrow screens with large system text", () => {
  Native.Dimensions.set({ window: { width: 480, height: 800, scale: 2, fontScale: 1 } });
  const dashboard = buildSyntheticDashboard("learner", 30);
  const view = render(<LearnerNavigation state={{ status: "ready", provenance: "demo", dashboard }} periodDays={30} />);
  const link = () => screen.getByRole("button", { name: "Open Support Settings" });
  expect(Native.StyleSheet.flatten(link().props.style).flexBasis).toBe("46%");
  act(() => Native.Dimensions.set({ window: { width: 320, height: 568, scale: 2, fontScale: 2 } }));
  view.rerender(<LearnerNavigation state={{ status: "ready", provenance: "demo", dashboard }} periodDays={30} />);
  expect(Native.StyleSheet.flatten(link().props.style).flexBasis).toBe("100%");
  expect(Native.StyleSheet.flatten(link().props.style).minHeight).toBeGreaterThanOrEqual(48);
  const tabs = within(screen.getByLabelText("Learner feature navigation")).getAllByRole("tab");
  expect(tabs).toHaveLength(4);
  for (const tab of tabs) {
    expect(Native.StyleSheet.flatten(tab.props.style).flexBasis).toBe("45%");
  }
  fireEvent.press(screen.getByRole("tab", { name: "Analytics learner view" }));
  expect(screen.getByRole("header", { name: "My Reading Analytics" })).toBeTruthy();
  expect(screen.getByText("Demo \u00b7 Fictional data")).toBeTruthy();
});

it("adds a reading illustration to Feedback without replacing labeled response controls", () => {
  render(<PreviewSessionBoundary enabled><SessionFeedbackScreen /></PreviewSessionBoundary>);
  expect(screen.getByRole("image", { name: "A book and a speech bubble: your view matters" })).toBeTruthy();
  expect(screen.getByText(/not sent or saved to a real reading session/)).toBeTruthy();
  const happy = screen.getByRole("radio", { name: "How did reading feel?: Happy" });
  expect(Native.StyleSheet.flatten(happy.props.style).minHeight).toBeGreaterThanOrEqual(48);
  fireEvent.press(happy);
  expect(screen.getByRole("radio", { name: "How did reading feel?: Happy" }).props.accessibilityState.checked).toBe(true);
  expect(screen.getByText(/Feeling: Happy/)).toBeTruthy();
});

function luminance(hex: string): number {
  const channels = [1, 3, 5].map((index) => parseInt(hex.slice(index, index + 2), 16) / 255)
    .map((value) => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4);
  return channels[0]! * 0.2126 + channels[1]! * 0.7152 + channels[2]! * 0.0722;
}

it.each([
  [palette.surface, palette.primary],
  [palette.primaryDark, palette.primarySoft],
  [palette.teal, palette.tealSoft],
  [palette.orange, palette.orangeSoft],
  [palette.yellow, palette.yellowSoft],
  [palette.muted, palette.paper],
  [palette.ink, palette.surface],
])("keeps text contrast at least 4.5:1 for %s on %s", (foreground, background) => {
  const values = [luminance(foreground), luminance(background)].sort((a, b) => b - a);
  expect((values[0]! + 0.05) / (values[1]! + 0.05)).toBeGreaterThanOrEqual(4.5);
});
