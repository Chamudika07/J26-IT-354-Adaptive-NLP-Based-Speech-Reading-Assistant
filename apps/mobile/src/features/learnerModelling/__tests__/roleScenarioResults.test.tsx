import { act, fireEvent, render, screen } from "@testing-library/react-native";
import App from "../../../../App";
import { GuardianSummaryScreen } from "../screens/GuardianSummaryScreen";
import { EducatorAnalyticsScreen } from "../screens/EducatorAnalyticsScreen";
import { unavailableLiveDashboardProvider } from "../data/dashboardProvider";
import { publishScenario, scenarioId } from "../preview/selectedScenario";
import { selectConnectedReplay } from "../preview/connectedSessionPreview";
import { selectRoleScenario } from "../preview/roleScenarioResults";
import guardians from "../preview/guardianScenarioContract.json";
import educators from "../preview/educatorScenarioContract.json";

const sample = (index: number) => selectConnectedReplay({ index, development: true, demoMode: true, role: "learner" })!;
beforeEach(() => { publishScenario(null); delete process.env.EXPO_PUBLIC_COMPONENT4_DEVELOPER_TOOLS; });
afterEach(() => { publishScenario(null); jest.restoreAllMocks(); });

it("selects detached closed role projections for the same evidence and rejects leakage or wrong identities", () => {
  const id = scenarioId(3, sample(3));
  const guardian = selectRoleScenario("guardian", id)!;
  const educator = selectRoleScenario("educator", id)!;
  expect(guardian.projection.included_session_count).toBe(3);
  expect(educator.projection.included_session_count).toBe(3);
  expect(guardian.scenarioId).toBe(educator.scenarioId);
  expect(guardian.projection.contexts[0]!.metrics.map(m => m.latest_value)).toEqual(sample(3).metrics.map(m => m.latest_value));
  expect(educator.projection.partitions[0]!.metrics.map(m => m.latest_value)).toEqual(sample(3).metrics.map(m => m.latest_value));
  expect(JSON.stringify([guardian, educator])).not.toMatch(/engagement|recommendation|learner_id|"profile"|"feedback"/i);
  guardian.projection.included_session_count = 999;
  expect(selectRoleScenario("guardian", id)!.projection.included_session_count).toBe(3);
  expect(selectRoleScenario("guardian", "wrong")).toBeNull();
  const oldRevision = JSON.parse(id); oldRevision[7] = "2000-01-01T00:00:00Z";
  expect(selectRoleScenario("guardian", JSON.stringify(oldRevision))).toBeNull();
  expect(selectRoleScenario("guardian", id, () => educators)).toBeNull();
  expect(selectRoleScenario("educator", id, () => guardians)).toBeNull();
  expect(selectRoleScenario("guardian", id, () => guardians.map(g => ({ ...g, engagement: 100 })))).toBeNull();
  expect(selectRoleScenario("educator", id, () => null)).toBeNull();
});

it.each(["guardian", "educator"] as const)("updates the permitted %s view and fails closed rather than substituting", async role => {
  publishScenario(3, sample(3));
  render(role === "guardian" ? <GuardianSummaryScreen periodDays={30} /> : <EducatorAnalyticsScreen periodDays={30} />);
  await screen.findByText(role === "guardian" ? "Parent Dashboard" : "Teacher Dashboard");
  if (role === "educator") fireEvent.press(screen.getByRole("button", { name: "View Alex Storybook" }));
  expect(screen.getByText(role === "guardian" ? "Selected reading scenario: Sample 3" : /^Scenario 3/)).toBeTruthy();
  expect(screen.getByText(role === "guardian" ? "3 sessions completed" : "3 completed sessions")).toBeTruthy();
  expect(screen.queryByText(sample(3).recommendation!.action)).toBeNull();
  expect(screen.queryByText(/Experimental engagement/)).toBeNull();
  expect(screen.queryByRole("button", { name: "Download AI Report PDF" })).toBeNull();
  act(() => publishScenario(4, sample(4)));
  expect(screen.getByText(role === "guardian" ? "4 sessions completed" : "4 completed sessions")).toBeTruthy();
  act(() => publishScenario(999, sample(4)));
  expect(screen.getByText(/These sample results are unavailable/)).toBeTruthy();
  if (role === "guardian") expect(screen.queryByTestId("parent-reading_accuracy")).toBeNull();
  else expect(screen.queryByText("Educator reading analytics")).toBeNull();
  fireEvent.press(screen.getByRole("button", { name: "View separate example" }));
  expect(screen.getByText(role === "guardian" ? "Parent Dashboard" : "Educator reading analytics")).toBeTruthy();
  expect(screen.getByText(role === "guardian" ? /Independent example/ : /This view uses its own sample data/)).toBeTruthy();
});

it("shares only selection through role switching, preserving learner history and report boundaries", async () => {
  render(<App />); await screen.findByText("Hi, Reader!");
  fireEvent.press(screen.getByRole("button", { name: "Reading Results" }));
  fireEvent.press(screen.getByRole("radio", { name: "Sample scenario: Sample 3" }));
  fireEvent.press(screen.getByRole("button", { name: "Update My Progress" }));
  for (const role of ["Guardian", "Educator"]) {
    fireEvent.press(screen.getByRole("tab", { name: `${role} sample preview` }));
    if (role === "Educator") fireEvent.press(await screen.findByRole("button", { name: "View Alex Storybook" }));
    await screen.findByText(role === "Guardian" ? "Selected reading scenario: Sample 3" : /^Scenario 3/);
    expect(screen.queryByRole("button", { name: "Edit Profile" })).toBeNull();
    expect(screen.queryByText(/Your demo feedback/)).toBeNull();
  }
  fireEvent.press(screen.getByRole("tab", { name: "Learner sample preview" }));
  await screen.findByText("Hi, Reader!");
  fireEvent.press(screen.getByRole("tab", { name: "Analytics learner view" }));
  fireEvent.press(screen.getByRole("button", { name: "View Reading History" }));
  fireEvent.press(screen.getByRole("button", { name: "About these results" }));
  expect(screen.getByText(/Applied scenario: Sample 3 - 3 completed/)).toBeTruthy();
  expect(screen.getByText(/S3.*Completed/)).toBeTruthy();
});

it("never uses selected demo artifacts in a live or release view", async () => {
  publishScenario(3, sample(3));
  const view = render(<GuardianSummaryScreen periodDays={30} provider={unavailableLiveDashboardProvider} />);
  await screen.findByText("Report temporarily unavailable");
  expect(screen.queryByText("Selected reading scenario: Sample 3")).toBeNull();
  view.unmount();
  const id = scenarioId(3, sample(3));
  jest.replaceProperty(globalThis as typeof globalThis & { __DEV__: boolean }, "__DEV__", false);
  expect(selectRoleScenario("guardian", id)).toBeNull();
});
