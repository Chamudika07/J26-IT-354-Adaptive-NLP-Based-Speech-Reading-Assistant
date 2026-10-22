import App from "../../../../App";
import { act, fireEvent, render, screen } from "@testing-library/react-native";
import { Text } from "react-native";
import { DeveloperTestBoundary, useDeveloperTest } from "../preview/DeveloperTestSession";
import { Pp1ConnectionContext } from "../preview/Pp1Connection";
import { ReadingResultsScenarios } from "../components/ReadingResultsScenarios";
import { createPp1Client } from "../data/pp1Client";
import replay from "../preview/connectedSessionReplay.json";
import { publishScenario } from "../preview/selectedScenario";

jest.mock("../data/pp1Client", () => ({ createPp1Client: jest.fn() }));
const calculate = jest.fn();
function Evidence() {
  const state = useDeveloperTest()!;
  return <Text testID="evidence">{JSON.stringify({ source: state.source, count: state.connected.artifact?.includedSessionCount, index: state.replayIndex })}</Text>;
}
function setup() {
  return render(<Pp1ConnectionContext.Provider value={{ baseUrl: "https://example.test/api/v1", session: { scopeKey: "test", getAccessToken: async () => "test" } }}>
    <DeveloperTestBoundary enabled><ReadingResultsScenarios /><Evidence /></DeveloperTestBoundary>
  </Pp1ConnectionContext.Provider>);
}
beforeEach(() => { publishScenario(null); jest.clearAllMocks(); (createPp1Client as jest.Mock).mockReturnValue(Object.assign(calculate, { save: calculate, readSaved: calculate })); });
const choose = (label: string) => fireEvent.press(screen.getByRole("radio", { name: label }));
const update = () => fireEvent.press(screen.queryByRole("button", { name: "Save Sample Progress" }) ?? screen.getByRole("button", { name: "Update My Progress" }));
it("selects a source explicitly and publishes only successful matching learner evidence", async () => {
  calculate.mockResolvedValue({ result: replay[3], selectedSessionCount: 3 }); setup();
  choose("Results source: Connected sample (laptop)"); choose("Sample scenario: Sample 3"); update();
  await screen.findByTestId("evidence");
  await act(async () => {});
  expect(screen.getByTestId("evidence").props.children).toContain('"count":3');
  expect(screen.getByTestId("evidence").props.children).toContain('"index":3');
  expect(calculate).toHaveBeenCalledWith(3, expect.any(AbortSignal));
});
it("fails honestly and requires explicit offline selection", async () => {
  calculate.mockRejectedValue(new Error("private provider error")); setup();
  choose("Results source: Connected sample (laptop)"); update();
  await screen.findByText("Save or refresh not confirmed. Retry the same sample safely, or use offline examples.");
  expect(screen.getByTestId("evidence").props.children).toContain('"source":"laptop"');
  expect(screen.getByTestId("evidence").props.children).not.toContain('"count"');
  fireEvent.press(screen.getByRole("button", { name: "Use offline examples" }));
  choose("Sample scenario: Sample 2"); update();
  expect(screen.getByTestId("evidence").props.children).toContain('"count":2');
});
it("cancels requests and ignores late replies after choosing offline", async () => {
  let resolve!: (value: unknown) => void;
  calculate.mockImplementation(() => new Promise(r => { resolve = r; })); setup();
  choose("Results source: Connected sample (laptop)"); update();
  const signal = calculate.mock.calls[0][1] as AbortSignal;
  choose("Results source: Offline examples");
  expect(signal.aborted).toBe(true);
  await act(async () => { resolve({ result: replay[5] }); });
  expect(screen.getByTestId("evidence").props.children).toContain('"source":"offline"');
  expect(screen.getByTestId("evidence").props.children).not.toContain('"count"');
});
it("aborts on screen unmount", () => {
  calculate.mockImplementation(() => new Promise(() => {})); const view = setup();
  choose("Results source: Connected sample (laptop)"); update();
  const signal = calculate.mock.calls[0][1] as AbortSignal;
  view.unmount(); expect(signal.aborted).toBe(true);
});

it("keeps Profile, Analytics, Tips and Summary on the returned scenario", async () => {
  calculate.mockResolvedValue({ result: replay[3], selectedSessionCount: 3 });
  render(<Pp1ConnectionContext.Provider value={{ baseUrl: "https://example.test/api/v1", session: { scopeKey: "test", getAccessToken: async () => "test" } }}><App /></Pp1ConnectionContext.Provider>);
  await screen.findByText("Hi, Reader!");
  fireEvent.press(screen.getByRole("button", { name: "Reading Results" }));
  choose("Results source: Connected sample (laptop)"); choose("Sample scenario: Sample 3"); update();
  await screen.findByRole("header", { name: "My Profile" });
  expect(screen.getByText("Synthetic Sample Data \u00b7 Calculated on laptop")).toBeTruthy();
  expect(screen.getByText("Applied scenario: Sample 3")).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "Next: My Analytics" }));
  expect(screen.getByRole("header", { name: "My Analytics" })).toBeTruthy();
  expect(screen.getByText(/S3.*Completed/)).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "View Reading Tips" }));
  expect(screen.getByText(replay[3]!.recommendation!.action)).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "Next: My Reading Report" }));
  fireEvent.press(screen.getByRole("button", { name: "Read Current Summary" }));
  for (const text of replay[3]!.reportStatements) expect(screen.getByText(text)).toBeTruthy();
  expect(calculate).toHaveBeenCalledTimes(1);
  fireEvent.press(screen.getByRole("button", { name: "Open Saved AI Report" }));
  expect(screen.getByText("Created earlier using sample reading data.")).toBeTruthy();
  expect(screen.queryByText("Synthetic Sample Data \u00b7 Calculated on laptop")).toBeNull();
});
it("reloads persisted progress in a new mobile session without resaving", async () => {
  calculate.mockResolvedValue({ result: replay[2], selectedSessionCount: 2 });
  const first = setup(); first.unmount();
  setup(); choose("Results source: Connected sample (laptop)");
  fireEvent.press(screen.getByRole("button", { name: "Refresh Saved Progress" }));
  await act(async () => {});
  expect(screen.getByTestId("evidence").props.children).toContain('"count":2');
  expect(calculate).toHaveBeenCalledWith(expect.any(AbortSignal));
});
