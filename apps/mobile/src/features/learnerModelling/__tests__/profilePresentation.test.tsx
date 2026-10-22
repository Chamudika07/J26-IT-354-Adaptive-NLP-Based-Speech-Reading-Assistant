import { fireEvent, render, screen, within } from "@testing-library/react-native";
import { StyleSheet } from "react-native";
import App from "../../../../App";
import { selectConnectedReplay } from "../preview/connectedSessionPreview";
import { publishScenario } from "../preview/selectedScenario";

beforeEach(() => { publishScenario(null); delete process.env.EXPO_PUBLIC_COMPONENT4_DEVELOPER_TOOLS; });
it("shows a local update, exact ordered history and compact profile actions", async () => {
  render(<App />); await screen.findByText("Hi, Reader!");
  fireEvent.press(screen.getByRole("button", { name: "Reading Results" }));
  fireEvent.press(screen.getByRole("radio", { name: "Sample scenario: Sample 3" }));
  fireEvent.press(screen.getByRole("button", { name: "Update My Progress" }));
  expect(screen.getByRole("header", { name: "My Profile" })).toBeTruthy();
  expect(screen.getByText("Progress updated").props.accessibilityLiveRegion).toBe("polite");
  expect(screen.getAllByText("Demo \u00b7 Fictional data")).toHaveLength(1);
  expect(screen.queryByText("Sample Data")).toBeNull();
  expect(screen.queryByText(/loaded from PostgreSQL/)).toBeNull();
  const sample = selectConnectedReplay({ index: 3, development: true, demoMode: true, role: "learner" })!;
  expect(within(screen.getByTestId("profile-Completed Sessions")).getByText(String(sample.includedSessionCount))).toBeTruthy();
  expect(screen.getAllByTestId(/^profile-session-/).map(row => row.props.testID)).toEqual(sample.history.map(row => `profile-session-${row.sequence}`));
  for (const row of sample.history) {
    const card = within(screen.getByTestId(`profile-session-${row.sequence}`));
    const accuracy = row.accuracy === null ? "Unavailable" : `${Number((Number(row.accuracy) * 100).toFixed(2))}%`;
    const speed = row.wpm === null ? "Unavailable" : `${Number(Number(row.wpm).toFixed(2))} WPM`;
    expect(card.getByText(`Accuracy: ${accuracy} \u00b7 Speed: ${speed}`)).toBeTruthy();
  }
  for (const label of ["Edit Profile", "Reading Settings", "View Analytics", "Reading Preferences", "Profile Details"]) {
    expect(StyleSheet.flatten(screen.getByRole("button", { name: label }).props.style).minHeight).toBeGreaterThanOrEqual(44);
  }
  expect(screen.getByRole("button", { name: "Reading Preferences" }).props.accessibilityState.expanded).toBe(false);
  expect(screen.getByRole("button", { name: "Profile Details" }).props.accessibilityState.expanded).toBe(false);
  fireEvent.press(screen.getByRole("button", { name: "View Analytics" }));
  expect(screen.getByRole("header", { name: "My Reading Analytics" })).toBeTruthy();
  fireEvent.press(screen.getByRole("tab", { name: "Profile learner view" }));
  expect(screen.queryByText("Progress updated")).toBeNull();
});
it("does not invent session history for an overview and keeps optional details collapsed", async () => {
  render(<App />); await screen.findByText("Hi, Reader!");
  fireEvent.press(screen.getByRole("tab", { name: "Profile learner view" }));
  expect(screen.getByText("Session details are unavailable for this overview.")).toBeTruthy();
  expect(screen.queryAllByTestId(/^profile-session-/)).toHaveLength(0);
  expect(screen.queryByText("Progress updated")).toBeNull();
  expect(screen.queryByText(/Latest observed difficulty:/)).toBeNull();
  fireEvent.press(screen.getByRole("button", { name: "Reading Preferences" }));
  expect(screen.getByText(/Highlighting:/)).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "Profile Details" }));
  expect(screen.getByText(/Latest observed difficulty:/)).toBeTruthy();
  expect(screen.queryByText(/Choices stay on this device|These observations describe recorded reading sessions|Your profile name is separate from reading results|Saved AI reports and PDFs stay unchanged/)).toBeNull();
  expect(screen.getAllByText("Demo \u00b7 Fictional data")).toHaveLength(1);
});
