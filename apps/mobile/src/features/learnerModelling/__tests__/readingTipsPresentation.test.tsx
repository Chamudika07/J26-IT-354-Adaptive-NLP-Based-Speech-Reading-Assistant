import { fireEvent, render, screen, within } from "@testing-library/react-native";
import { StyleSheet } from "react-native";
import { LearnerSuggestionsScreen } from "../screens/LearnerSuggestionsScreen";
import { ConnectedLearnerJourney } from "../components/ConnectedLearnerJourney";
import { DeveloperTestBoundary } from "../preview/DeveloperTestSession";
import { Pp1ConnectionContext } from "../preview/Pp1Connection";
import { selectConnectedReplay } from "../preview/connectedSessionPreview";
import { buildSyntheticDashboard } from "../preview/syntheticData";
import { publishScenario } from "../preview/selectedScenario";

beforeEach(() => { publishScenario(null); delete process.env.EXPO_PUBLIC_COMPONENT4_DEVELOPER_TOOLS; });
it("shows overview evidence and supplied reasons without inventing exact rules", () => {
  const dashboard = buildSyntheticDashboard("learner", 30);
  render(<LearnerSuggestionsScreen dashboard={dashboard} demoMode periodDays={30} />);
  expect(screen.getByRole("header", { name: "My Reading Tips" })).toBeTruthy();
  expect(screen.getAllByText("Demo \u00b7 Fictional data")).toHaveLength(1);
  expect(screen.queryByText("Sample Data")).toBeNull();
  expect(screen.getByText(dashboard.recommendation.explanation)).toBeTruthy();
  expect(screen.getByText(dashboard.recommendation.supportSuggestion)).toBeTruthy();
  expect(within(screen.getByTestId("tip-Completed Sessions")).getByText(String(dashboard.includedSessionCount))).toBeTruthy();
  const toggle = screen.getByRole("button", { name: "Why This Tip?" });
  expect(StyleSheet.flatten(toggle.props.style).minHeight).toBeGreaterThanOrEqual(44);
  fireEvent.press(toggle);
  for (const code of dashboard.recommendation.reasonCodes) expect(screen.getByText(`Reason code: ${code}`)).toBeTruthy();
  expect(screen.getByText("Exact rule conditions: Unavailable.")).toBeTruthy();
  expect(screen.getByText("Decision evidence: Unavailable")).toBeTruthy();
  for (const metric of dashboard.metrics) {
    const label = metric.key === "reading_accuracy" ? "Reading Accuracy (%)" : metric.key === "reading_fluency_wpm" ? "Reading Speed (WPM)" : "Hesitations per 100 attempted words";
    expect(within(screen.getByTestId(`tip-evidence-${label}`)).getByText(`Progress evidence: ${metric.evidenceLabel}`)).toBeTruthy();
  }
});
it.each(["offline", "connected"])("uses the active %s scenario and its backend explanations faithfully", mode => {
  const artifact = selectConnectedReplay({ index: 3, development: true, demoMode: true, role: "learner" })!;
  const navigate = jest.fn();
  const network = jest.spyOn(globalThis, "fetch");
  try {
    render(<Pp1ConnectionContext.Provider value={mode === "connected" ? { baseUrl: "https://example.test/api/v1", session: { scopeKey: "tips-test", getAccessToken: async () => "test" } } : undefined}>
      <DeveloperTestBoundary enabled><ConnectedLearnerJourney artifact={artifact} destination="suggestions" onNavigate={navigate} /></DeveloperTestBoundary>
    </Pp1ConnectionContext.Provider>);
    expect(screen.getByRole("header", { name: artifact.recommendation!.action })).toBeTruthy();
    expect(screen.getAllByText(mode === "connected" ? "Synthetic Sample Data \u00b7 Calculated on laptop" : "Demo \u00b7 Fictional data")).toHaveLength(1);
    for (const reason of new Set([...artifact.recommendationExplanation, ...artifact.recommendation!.reasons])) expect(screen.getAllByText(reason)).toHaveLength(1);
    const accuracy = artifact.metrics.find(metric => metric.metric_name === "reading_accuracy")!;
    expect(within(screen.getByTestId("tip-Reading Accuracy (%)")).getByText(`${Number((Number(accuracy.latest_value) * 100).toFixed(2))}%`)).toBeTruthy();
    expect(screen.getByText("ADVISORY ONLY")).toBeTruthy();
    expect(screen.getByText("No settings or reading level were changed automatically.")).toBeTruthy();
    fireEvent.press(screen.getByRole("button", { name: "Why This Tip?" }));
    expect(screen.getByText(`Decision evidence: ${artifact.recommendation!.evidence_state}`)).toBeTruthy();
    expect(within(screen.getByTestId("tip-evidence-Reading Accuracy (%)")).getByText(`Progress evidence: ${accuracy.evidence_state}`)).toBeTruthy();
    expect(screen.getByText("Evidence status is not a confidence score.")).toBeTruthy();
    expect(screen.getByText("Exact rule conditions: Unavailable.")).toBeTruthy();
    for (const limitation of new Set([...artifact.recommendation!.limitations, artifact.recommendation!.disclaimer, artifact.disclaimer])) expect(screen.getByText(limitation)).toBeTruthy();
    fireEvent.press(screen.getByRole("button", { name: "Next: My Reading Report" }));
    expect(navigate).toHaveBeenCalledWith("report");
    expect(network).not.toHaveBeenCalled();
  } finally { network.mockRestore(); }
});
it("does not fabricate measurements, evidence quality or a decision for an empty scenario", () => {
  const artifact = selectConnectedReplay({ index: 0, development: true, demoMode: true, role: "learner" })!;
  render(<DeveloperTestBoundary enabled><ConnectedLearnerJourney artifact={artifact} destination="suggestions" /></DeveloperTestBoundary>);
  expect(screen.getByText("Keep reading to find a helpful tip.")).toBeTruthy();
  expect(screen.getAllByText("Unavailable")).toHaveLength(3);
  for (const reason of artifact.recommendationExplanation) expect(screen.getByText(reason)).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "Why This Tip?" }));
  expect(screen.getByText("Decision evidence: Unavailable")).toBeTruthy();
  expect(screen.queryByText("Evidence status is not a confidence score.")).toBeNull();
});
