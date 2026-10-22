import { fireEvent, render, screen, within } from "@testing-library/react-native";
import { StyleSheet } from "react-native";
import { ConnectedLearnerJourney } from "../components/ConnectedLearnerJourney";
import { DeveloperTestBoundary } from "../preview/DeveloperTestSession";
import { Pp1ConnectionContext } from "../preview/Pp1Connection";
import { selectConnectedReplay } from "../preview/connectedSessionPreview";
import { buildSyntheticDashboard } from "../preview/syntheticData";
import { publishScenario } from "../preview/selectedScenario";
import saved from "../preview/localReportSnapshot.json";

beforeEach(() => { publishScenario(null); delete process.env.EXPO_PUBLIC_COMPONENT4_DEVELOPER_TOOLS; });
it.each(["offline", "connected"])("keeps the %s current report separate from the saved AI content on one screen", mode => {
  const a = selectConnectedReplay({ index: 3, development: true, demoMode: true, role: "learner" })!;
  const reportProps = { dashboard: buildSyntheticDashboard("learner", 30), demoMode: true, periodDays: 30 as const };
  render(<Pp1ConnectionContext.Provider value={mode === "connected" ? { baseUrl: "https://example.test/api/v1", session: { scopeKey: "report-test", getAccessToken: async () => "test" } } : undefined}>
    <DeveloperTestBoundary enabled><ConnectedLearnerJourney artifact={a} destination="report" reportProps={reportProps} /></DeveloperTestBoundary>
  </Pp1ConnectionContext.Provider>);
  expect(screen.getAllByText("Demo \u00b7 Fictional data")).toHaveLength(1);
  expect(screen.queryByText("Sample Data")).toBeNull();
  expect(screen.getByRole("header", { name: "Current Progress Report" })).toBeTruthy();
  expect(screen.getByRole("header", { name: "Previously Saved AI Report" })).toBeTruthy();
  expect(within(screen.getByTestId("report-Completed Sessions")).getByText(String(a.includedSessionCount))).toBeTruthy();
  const accuracy = a.metrics.find(m => m.metric_name === "reading_accuracy")!.latest_value;
  expect(within(screen.getByTestId("report-Reading Accuracy (%)")).getByText(`${Number((Number(accuracy) * 100).toFixed(2))}%`)).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Download AI Report PDF" })).toBeNull();
  const summary = screen.getByRole("button", { name: "View Current Summary" });
  expect(StyleSheet.flatten(summary.props.style).minHeight).toBeGreaterThanOrEqual(44);
  fireEvent.press(summary);
  const current = within(screen.getByTestId("current-summary-content"));
  for (const statement of a.reportStatements) expect(current.getByText(statement)).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "View Saved AI Report" }));
  const prior = within(screen.getByTestId("saved-ai-report-content"));
  for (const statement of saved.statements) expect(prior.getByText(statement)).toBeTruthy();
  expect(within(screen.getByTestId("previously-saved-ai-report")).getByRole("button", { name: "Download AI Report PDF" })).toBeTruthy();
  expect(within(screen.getByTestId("current-progress-report")).queryByRole("button", { name: /PDF/ })).toBeNull();
  expect(screen.queryByRole("button", { name: /Back to|Return to/ })).toBeNull();
  fireEvent.press(screen.getByRole("button", { name: "Hide Saved AI Report" }));
  expect(screen.getByTestId("current-summary-content")).toBeTruthy();
});
it("shows unavailable metrics honestly for an empty current report", () => {
  const a = selectConnectedReplay({ index: 0, development: true, demoMode: true, role: "learner" })!;
  render(<DeveloperTestBoundary enabled><ConnectedLearnerJourney artifact={a} destination="report" /></DeveloperTestBoundary>);
  expect(screen.getAllByText("Unavailable")).toHaveLength(3);
  expect(within(screen.getByTestId("report-Completed Sessions")).getByText("0")).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "View Current Summary" }));
  for (const statement of a.reportStatements) expect(screen.getByText(statement)).toBeTruthy();
  expect(screen.queryByRole("button", { name: /Download/ })).toBeNull();
});
