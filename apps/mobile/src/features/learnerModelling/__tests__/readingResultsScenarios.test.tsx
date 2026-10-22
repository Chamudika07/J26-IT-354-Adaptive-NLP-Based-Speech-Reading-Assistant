import { act, fireEvent, render, screen, within } from "@testing-library/react-native";
import { Alert, StyleSheet } from "react-native";
import { Pp1ConnectionContext } from "../preview/Pp1Connection";
import App from "../../../../App";
import { selectConnectedReplay } from "../preview/connectedSessionPreview";
import { publishScenario } from "../preview/selectedScenario";

beforeEach(() => { publishScenario(null); delete process.env.EXPO_PUBLIC_COMPONENT4_DEVELOPER_TOOLS; });
const button = (name: string) => fireEvent.press(screen.getByRole("button", { name }));
const tab = (name: string) => fireEvent.press(screen.getByRole("tab", { name: `${name} learner view` }));
async function start(index: number) {
  render(<App />); await screen.findByText("Hi, Reader!");
  expect(screen.getAllByRole("button", { name: "Reading Results" })).toHaveLength(1);
  expect(screen.queryByRole("button", { name: "Open My Profile" })).toBeNull();
  button("Reading Results");
  expect(screen.getAllByRole("button", { name: "Update My Progress" })).toHaveLength(1);
  expect(screen.queryByLabelText("Words attempted")).toBeNull();
  fireEvent.press(screen.getByRole("radio", { name: `Sample scenario: Sample ${index}` }));
  button("Update My Progress");
}

it("guides one scenario from editable profile through analytics, evidence-based tips and separate reports", async () => {
  const network = jest.spyOn(globalThis, "fetch");
  try {
    await start(2);
    const sample = selectConnectedReplay({ index: 2, development: true, demoMode: true, role: "learner" })!;
    expect(screen.getByRole("header", { name: "My Profile" })).toBeTruthy();
    button("Profile Details");
    expect(screen.getByText("Applied scenario: Sample 2")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Edit Profile" })).toBeTruthy();
    expect(screen.getAllByRole("button", { name: "Reading Settings" })).toHaveLength(1);
    expect(screen.queryByRole("button", { name: "View Learner Profile" })).toBeNull();
    button("View Analytics");
    expect(screen.getByRole("header", { name: "My Reading Analytics" })).toBeTruthy();
    for (const title of ["Reading Performance", "Reading Behaviour", "Reading Progress"]) expect(screen.getByRole("header", { name: title })).toBeTruthy();
    fireEvent.press(screen.getByRole("button", { name: "View Reading History" }));
    expect(screen.getByText(/S2.*Completed/)).toBeTruthy();
    button("View Reading Tips");
    expect(screen.getByRole("header", { name: "My Reading Tips" })).toBeTruthy();
    expect(screen.getByText("There are not enough comparable reading results to recommend a change yet.")).toBeTruthy();
    button("Why This Tip?");
    for (const text of sample.recommendationExplanation) expect(screen.getByText(text)).toBeTruthy();
    button("Next: My Reading Report");
    button("View Current Summary");
    for (const text of sample.reportStatements) expect(screen.getByText(text)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Download AI Report PDF" })).toBeNull();
    button("View Saved AI Report");
    expect(screen.getByText("Created earlier using sample reading data.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Download AI Report PDF" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Hide Saved AI Report" })).toBeTruthy();
    expect(screen.getByRole("header", { name: "Current Progress Report" })).toBeTruthy();
    button("Hide Saved AI Report");
    expect(screen.getByRole("header", { name: "Current Progress Report" })).toBeTruthy();
    expect(network).not.toHaveBeenCalled();
  } finally { network.mockRestore(); }
});

it("applies another matching backend decision and keeps other-role data separate", async () => {
  await start(3); tab("Suggestions");
  const result = selectConnectedReplay({ index: 3, development: true, demoMode: true, role: "learner" })!;
  expect(screen.getByText(result.recommendation!.action)).toBeTruthy();
  button("Why This Tip?");
  for (const text of result.recommendationExplanation) expect(screen.getByText(text)).toBeTruthy();
  expect(screen.getByText("ADVISORY ONLY")).toBeTruthy();
  for (const role of ["Guardian", "Educator"]) {
    fireEvent.press(screen.getByRole("tab", { name: `${role} sample preview` }));
    await screen.findByText(role === "Guardian" ? "Parent Dashboard" : "Teacher Dashboard");
    if (role === "Educator") button("View Alex Storybook");
    expect(screen.getByText(role === "Guardian" ? "Selected reading scenario: Sample 3" : /^Scenario 3/)).toBeTruthy();
    expect(screen.queryByText(result.recommendation!.action)).toBeNull();
    expect(screen.queryByText("Applied scenario: Sample 3")).toBeNull();
  }
});

it("resets history, tips and the current report without replacing identity or inventing measurements", async () => {
  await start(3); button("View Analytics"); const confirm = jest.spyOn(Alert, "alert"); button("Reset Journey");
  act(() => confirm.mock.calls.at(-1)![2]!.find(b => b.text === "Reset Journey")!.onPress!());
  confirm.mockRestore();
  button("View Behaviour Details"); button("About these results");
  expect(screen.getByText(/Applied scenario: Sample 0 - 0 completed/)).toBeTruthy();
  expect(screen.getAllByText("Unavailable")).toHaveLength(3);
  expect(screen.getByText("Reading time: Unavailable.")).toBeTruthy();
  expect(screen.queryByText(/S3.*Completed/)).toBeNull();
  button("View Reading Tips");
  expect(screen.getByText("Keep reading to find a helpful tip.")).toBeTruthy();
  button("Next: My Reading Report"); button("View Current Summary");
  const empty = selectConnectedReplay({ index: 0, development: true, demoMode: true, role: "learner" })!;
  for (const text of empty.reportStatements) expect(screen.getByText(text)).toBeTruthy();
  tab("Profile");
  expect(screen.getByText("Demo Learner")).toBeTruthy();
  expect(screen.getByRole("button", { name: "Edit Profile" })).toBeTruthy();
});

it("uses compact accessible chips and shows the matching supplied metrics without invented values", async () => {
  render(<App />); await screen.findByText("Hi, Reader!"); button("Reading Results");
  expect(screen.getAllByText("Demo Mode \u00b7 Fictional data")).toHaveLength(1);
  expect(screen.queryByText("Sample Data")).toBeNull();
  expect(screen.queryByRole("radio", { name: /Results source:/ })).toBeNull();
  expect(screen.queryByText("Reading time: Unavailable.")).toBeNull();
  for (let index = 0; index <= 6; index++) {
    const chip = screen.getByRole("radio", { name: `Sample scenario: ${index === 0 ? "Before reading" : `Sample ${index}`}` });
    expect(StyleSheet.flatten(chip.props.style).minHeight).toBeGreaterThanOrEqual(44);
    fireEvent.press(chip);
    expect(screen.getByRole("radio", { name: `Sample scenario: ${index === 0 ? "Before reading" : `Sample ${index}`}` }).props.accessibilityState.checked).toBe(true);
    const sample = selectConnectedReplay({ index, development: true, demoMode: true, role: "learner" })!;
    expect(screen.getByText(`${sample.includedSessionCount} completed sample sessions`)).toBeTruthy();
    for (const [key, scale] of [["reading_accuracy", 100], ["reading_fluency_wpm", 1], ["hesitation_rate_per_word", 100]] as const) {
      const value = sample.metrics.find(m => m.metric_name === key)?.latest_value;
      expect(within(screen.getByTestId(`results-${key}`)).getByText(value == null ? "Unavailable" : String(Number((Number(value) * scale).toFixed(2))))).toBeTruthy();
    }
  }
  const details = screen.getByRole("button", { name: "Session Details" });
  expect(details.props.accessibilityState.expanded).toBe(false);
  expect(StyleSheet.flatten(details.props.style).minHeight).toBeGreaterThanOrEqual(44);
  fireEvent.press(details);
  expect(screen.getByText("Reading time: Unavailable.")).toBeTruthy();
  expect(screen.getByText("Pause count and duration: Unavailable.")).toBeTruthy();
  expect(screen.getByText("Replays: Unavailable.")).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "Session Details" }));
  expect(screen.queryByText("Reading time: Unavailable.")).toBeNull();
  expect(screen.getByRole("button", { name: "Update My Progress" })).toBeTruthy();
});

it("automatically exposes save and refresh only inside an authenticated PP1 journey", async () => {
  render(<Pp1ConnectionContext.Provider value={{ baseUrl: "https://example.test/api/v1", session: { scopeKey: "test", getAccessToken: async () => "test" } }}><App /></Pp1ConnectionContext.Provider>); await screen.findByText("Hi, Reader!"); button("Reading Results");
  expect(screen.getAllByText("Synthetic Sample Data \u00b7 Laptop connection")).toHaveLength(1);
  expect(screen.queryByText("Sample Data")).toBeNull();
  expect(screen.queryByRole("radio", { name: /Results source:/ })).toBeNull();
  for (const name of ["Save Sample Progress", "Refresh Saved Progress"]) {
    const action = screen.getByRole("button", { name });
    expect(StyleSheet.flatten(action.props.style).minHeight).toBeGreaterThanOrEqual(44);
    expect(action.props.accessibilityState.disabled).toBe(false);
  }
  expect(screen.getByRole("button", { name: "Session Details" }).props.accessibilityState.expanded).toBe(false);
  expect(screen.getAllByText("Unavailable")).toHaveLength(3);
});

it("separates essential session details from optional demo explanations", async () => {
  render(<App />); await screen.findByText("Hi, Reader!"); button("Reading Results");
  const explanation = "Selected sample values, not new phone measurements.";
  expect(screen.getByRole("button", { name: "Session Details" }).props.accessibilityState.expanded).toBe(false);
  expect(screen.getByRole("button", { name: "More information" }).props.accessibilityState.expanded).toBe(false);
  button("Session Details");
  expect(screen.getByText("Reading time: Unavailable.")).toBeTruthy();
  expect(screen.queryByText(explanation)).toBeNull();
  expect(screen.queryByText("Your demo choices")).toBeNull();
  const more = screen.getByRole("button", { name: "More information" });
  expect(StyleSheet.flatten(more.props.style).minHeight).toBeGreaterThanOrEqual(44);
  button("More information");
  expect(screen.getByText(explanation)).toBeTruthy();
  expect(screen.getByText("Your demo choices")).toBeTruthy();
  expect(screen.getByText(/Saved AI reports and PDFs stay unchanged/)).toBeTruthy();
  button("More information");
  expect(screen.queryByText(explanation)).toBeNull();
  expect(screen.getByText("Reading time: Unavailable.")).toBeTruthy();
  expect(screen.queryByText(/A cancelled save may have finished/)).toBeNull();
  expect(screen.getByRole("button", { name: "Update My Progress" })).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Save Sample Progress" })).toBeNull();
});
