import { fireEvent, render, screen } from "@testing-library/react-native";
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
    expect(screen.getByText("Applied scenario: Sample 2")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Edit Profile" })).toBeTruthy();
    expect(screen.getAllByRole("button", { name: "Reading Settings" })).toHaveLength(1);
    expect(screen.queryByRole("button", { name: "View Learner Profile" })).toBeNull();
    button("Next: My Analytics");
    expect(screen.getByRole("header", { name: "My Analytics" })).toBeTruthy();
    for (const title of ["Reading Performance", "Reading Behaviour", "Reading Progress"]) expect(screen.getByRole("header", { name: title })).toBeTruthy();
    expect(screen.getByText(/S2.*Completed/)).toBeTruthy();
    button("View Reading Tips");
    expect(screen.getByRole("header", { name: "My Reading Tips" })).toBeTruthy();
    expect(screen.getByText("There are not enough comparable reading results to recommend a change yet.")).toBeTruthy();
    button("Why This Tip?");
    for (const text of sample.recommendationExplanation) expect(screen.getByText(text)).toBeTruthy();
    button("Next: My Reading Report");
    button("Read Current Summary");
    for (const text of sample.reportStatements) expect(screen.getByText(text)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Download AI Report PDF" })).toBeNull();
    button("Open Saved AI Report");
    expect(screen.getByText("Created earlier using sample reading data.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Download AI Report PDF" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Open saved AI report" })).toBeNull();
    expect(screen.queryByRole("header", { name: "Current Reading Summary" })).toBeNull();
    button("Back to Current Reading Summary");
    expect(screen.getByRole("header", { name: "Current Reading Summary" })).toBeTruthy();
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
  await start(3); button("Next: My Analytics"); button("Reset Journey");
  expect(screen.getByText(/Applied scenario: Sample 0 - 0 completed/)).toBeTruthy();
  expect(screen.getAllByText("Not measured")).toHaveLength(3);
  expect(screen.getByText("Reading time: Not supplied.")).toBeTruthy();
  expect(screen.queryByText(/S3.*Completed/)).toBeNull();
  button("View Reading Tips");
  expect(screen.getByText("Keep reading to find a helpful tip.")).toBeTruthy();
  button("Next: My Reading Report"); button("Read Current Summary");
  const empty = selectConnectedReplay({ index: 0, development: true, demoMode: true, role: "learner" })!;
  for (const text of empty.reportStatements) expect(screen.getByText(text)).toBeTruthy();
  tab("Profile");
  expect(screen.getByText("Demo Learner")).toBeTruthy();
  expect(screen.getByRole("button", { name: "Edit Profile" })).toBeTruthy();
});
