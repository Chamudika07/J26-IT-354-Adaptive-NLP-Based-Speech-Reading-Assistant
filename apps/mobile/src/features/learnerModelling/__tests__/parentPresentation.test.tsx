import { fireEvent, render, screen, within } from "@testing-library/react-native";
import { Dimensions, StyleSheet } from "react-native";
import { ParentDashboard } from "../components/ParentDashboard";
import { selectRoleScenario } from "../preview/roleScenarioResults";
import { selectConnectedReplay } from "../preview/connectedSessionPreview";
import { scenarioId } from "../preview/selectedScenario";
import { buildSyntheticDashboard } from "../preview/syntheticData";
const projection = (index: number) => selectRoleScenario("guardian", scenarioId(index, selectConnectedReplay({ index, development: true, demoMode: true, role: "learner" })!))!.projection;
it.each([0, 1, 3, 6])("renders scenario %s from Guardian evidence without single-session comparisons or repeated notices", index => {
  const p = projection(index); const separate = jest.fn();
  render(<ParentDashboard projection={p} selection={`Sample ${index}`} onSeparate={separate} />);
  expect(screen.getAllByText("Demo \u00b7 Fictional data")).toHaveLength(1);
  expect(screen.queryByText("Sample Data")).toBeNull();
  expect(screen.getByText(`${index} ${index === 1 ? "session" : "sessions"} completed`)).toBeTruthy();
  expect(screen.queryByText(/1 sessions/)).toBeNull();
  if (index < 2) expect(screen.queryAllByTestId(/^parent-comparison-/)).toHaveLength(0);
  for (const c of p.contexts) for (const m of c.metrics) {
    const metric = within(screen.getByTestId(`parent-${m.metric_name}`));
    expect(metric.getByText(m.latest_value === null ? "Unavailable" : String(Number((Number(m.latest_value) * (m.metric_name === "reading_fluency_wpm" ? 1 : 100)).toFixed(2))))).toBeTruthy();
    if (m.valid_observation_count > 1) expect(screen.getByTestId(`parent-comparison-0-${m.metric_name}`)).toBeTruthy();
  }
  if (index < 6) expect(screen.getAllByText("More reading sessions are needed to see a trend")).toHaveLength(1);
  expect(screen.queryByText(p.disclaimer)).toBeNull();
  fireEvent.press(screen.getByRole("button", { name: "About these results" }));
  expect(screen.getByText(p.disclaimer)).toBeTruthy();
  for (const c of p.contexts) for (const m of c.metrics) expect(screen.getAllByText(`${m.metric_name === "reading_accuracy" ? "Reading Accuracy" : m.metric_name === "reading_fluency_wpm" ? "Reading Speed" : "Hesitation Frequency"}: ${m.explanation}`).length).toBeGreaterThan(0);
  fireEvent.press(screen.getByRole("button", { name: "View separate example" })); expect(separate).toHaveBeenCalledTimes(1);
  expect(screen.queryByText(/Experimental engagement|ADVISORY ONLY/)).toBeNull();
});
it("shows missing metrics without fake bars or values", () => {
  const p = projection(1); p.contexts[0]!.metrics.splice(0, 1);
  render(<ParentDashboard projection={p} />);
  expect(within(screen.getByTestId("parent-reading_accuracy")).getByText("Unavailable")).toBeTruthy();
  expect(screen.queryAllByTestId(/^parent-comparison-/)).toHaveLength(0);
});
it("keeps the independent example explicit and readable at narrow widths with large text", () => {
  Dimensions.set({ window: { width: 320, height: 568, scale: 2, fontScale: 2 } });
  render(<ParentDashboard dashboard={buildSyntheticDashboard("guardian", 30)} />);
  expect(screen.getByText(/Independent example/)).toBeTruthy();
  const button = screen.getByRole("button", { name: "About these results" });
  expect(StyleSheet.flatten(button.props.style).minHeight).toBeGreaterThanOrEqual(44);
  expect(screen.getByText("Support history: Unavailable")).toBeTruthy();
  fireEvent.press(button);
  for (const text of buildSyntheticDashboard("guardian", 30).limitations) expect(screen.getByText(text)).toBeTruthy();
  Dimensions.set({ window: { width: 390, height: 844, scale: 2, fontScale: 1 } });
});
it("fails closed when a matching Guardian artifact is missing", () => {
  render(<ParentDashboard projection={null} selection="Sample 3" onSeparate={jest.fn()} />);
  expect(screen.getByRole("alert")).toBeTruthy(); expect(screen.queryByTestId("parent-reading_accuracy")).toBeNull();
  expect(screen.getByRole("button", { name: "View separate example" })).toBeTruthy();
});

it("adds restrained Guardian artwork, metric colors and a styled PDF action while retaining evidence", () => {
  const p = projection(3);
  render(<ParentDashboard projection={p} selection="Sample 3" />);
  expect(StyleSheet.flatten(screen.getByTestId("parent-header").props.style).backgroundColor).toBe("#EEF5FF");
  expect(screen.getByRole("header", { name: "Reading Overview" })).toBeTruthy();
  expect(screen.getByText("3 sessions completed")).toBeTruthy();
  for (const [key, background, accent] of [
    ["reading_accuracy", "#EEF5FF", "#3182F6"], ["reading_fluency_wpm", "#EAFBF1", "#22C55E"], ["hesitation_rate_per_word", "#F4EFFF", "#8B5CF6"],
  ]) expect(StyleSheet.flatten(screen.getByTestId(`parent-${key}`).props.style)).toMatchObject({ backgroundColor: background, borderTopColor: accent });
  expect(StyleSheet.flatten(screen.getByTestId("parent-sessions").props.style).backgroundColor).toBe("#FFF7E6");
  for (const name of ["parent-reading-art", "parent-book-art"]) {
    const art = screen.getByTestId(name, { includeHiddenElements: true });
    expect(art.props.accessibilityElementsHidden).toBe(true);
    expect(art.props.importantForAccessibility).toBe("no-hide-descendants");
    expect(art.props.pointerEvents).toBe("none");
  }
  expect(screen.queryByLabelText("ReadBuddy smiling book character")).toBeNull();
  expect(screen.getAllByTestId("parent-metric-art", { includeHiddenElements: true })).toHaveLength(4);
  expect(StyleSheet.flatten(screen.getByRole("button", { name: "Download Progress Report" }).props.style)).toMatchObject({ backgroundColor: "#1D4ED8", minHeight: 48 });
  expect(screen.getAllByText("Demo \u00b7 Fictional data")).toHaveLength(1);
  expect(screen.getByRole("button", { name: "About these results" }).props.accessibilityState.expanded).toBe(false);
});
