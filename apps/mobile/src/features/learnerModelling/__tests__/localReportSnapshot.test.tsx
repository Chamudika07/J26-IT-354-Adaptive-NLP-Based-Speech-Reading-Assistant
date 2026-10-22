import { fireEvent, render, screen } from "@testing-library/react-native";

import * as local from "../preview/localReportSnapshot";
import contract from "../preview/syntheticReportDisplayContract.json";
import { buildSyntheticDashboard } from "../preview/syntheticData";
import { AIProgressReportScreen } from "../screens/AIProgressReportScreen";

function snapshot() {
  return { schemaVersion: "synthetic-local-report-v1", synthetic: true, validated: true,
    source: "local-ollama", role: "learner", model: "qwen3:4b",
    generatedAt: "2026-01-02T00:00:00+00:00", reportingStartUtc: contract.reportingStartUtc,
    reportingEndUtc: contract.reportingEndUtc, statements: [...contract.statements] };
}
const props = { dashboard: buildSyntheticDashboard("learner", 30), demoMode: true, periodDays: 30 as const };

beforeEach(() => { process.env.EXPO_PUBLIC_COMPONENT4_DEVELOPER_TOOLS = "1"; });
afterEach(() => { delete process.env.EXPO_PUBLIC_COMPONENT4_DEVELOPER_TOOLS; jest.restoreAllMocks(); });

it("never reads the snapshot without all explicit preview gates", () => {
  const read = jest.fn(() => snapshot());
  const enabled = { enabled: true, development: true, demoMode: true, role: "learner" as const, read };
  for (const gates of [{ enabled: false }, { development: false }, { demoMode: false },
    { role: "guardian" as const }, { role: "educator" as const }]) {
    expect(local.selectLocalReportSnapshot({ ...enabled, ...gates })).toBeNull();
  }
  expect(read).not.toHaveBeenCalled();
  expect(local.selectLocalReportSnapshot(enabled)?.source).toBe("local-ollama");
  expect(read).toHaveBeenCalledTimes(1);
});

it.each([
  null, {}, { ...snapshot(), validated: false }, { ...snapshot(), synthetic: false },
  { ...snapshot(), role: "guardian" }, { ...snapshot(), model: "remote:model" },
  { ...snapshot(), source: "live" }, { ...snapshot(), generatedAt: "yesterday" },
  { ...snapshot(), generatedAt: "2999-01-01T00:00:00+00:00" },
  { ...snapshot(), generatedAt: "2026-02-31T00:00:00+00:00" },
  { ...snapshot(), reportingStartUtc: "2026-02-01T00:00:00+00:00" },
  { ...snapshot(), learner_id: "PRIVATE" }, { ...snapshot(), secret: "PRIVATE" },
  { ...snapshot(), statements: ["Accuracy is 999%"] },
  { ...snapshot(), statements: contract.statements.slice(1) },
  { ...snapshot(), statements: [...contract.statements, contract.statements[0]] },
])("rejects malformed, mismatched, unvalidated or invented snapshot %#", (value) => {
  expect(local.validateLocalReportSnapshot(value, "learner")).toBeNull();
});

it("defaults to the existing demo and opts in to an explicitly saved offline report without networking", () => {
  const read = jest.spyOn(local, "readBundledLocalSnapshot").mockReturnValue(snapshot());
  const fetch = jest.spyOn(globalThis, "fetch");
  render(<AIProgressReportScreen {...props} />);
  expect(screen.getByText("Reading Progress Summary")).toBeTruthy();
  expect(screen.queryByText("SAVED AI REPORT")).toBeNull();
  expect(read).not.toHaveBeenCalled();
  fireEvent.press(screen.getByRole("button", { name: "Open saved AI report" }));
  expect(screen.getByText("My Reading Report")).toBeTruthy();
  expect(screen.getByText("Created earlier using sample reading data.")).toBeTruthy();
  expect(screen.getByText("See your reading progress, strengths and helpful tips.")).toBeTruthy();
  expect(screen.getByText("SAVED AI REPORT")).toBeTruthy();
  expect(screen.queryByText(/Source: local-ollama/)).toBeNull();
  expect(screen.queryByText(/Fixed sample period/)).toBeNull();
  expect(screen.queryByText("Production learner AI generation is not connected.")).toBeNull();
  expect(screen.getByText(/Opening it does not create a new report/)).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "Developer Details" }));
  expect(screen.getByText(/Model: qwen3:4b/)).toBeTruthy();
  expect(screen.getByText(/does not use the selected dashboard reporting period/)).toBeTruthy();
  expect(screen.getByText("Production learner AI generation is not connected.")).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "Developer Details" }));
  expect(screen.queryByText(/Model: qwen3:4b/)).toBeNull();
  expect(screen.getByText("ADVISORY ONLY")).toBeTruthy();
  for (const text of contract.statements) expect(screen.getByText(text)).toBeTruthy();
  expect(screen.queryByRole("button", { name: /generate/i })).toBeNull();
  expect(fetch).not.toHaveBeenCalled();
  fireEvent.press(screen.getByRole("button", { name: "Return to reading summary" }));
  expect(screen.getByText("Reading Progress Summary")).toBeTruthy();
});

it("shows unavailable state and clearly retains the deterministic demo for missing artifacts", () => {
  jest.spyOn(local, "readBundledLocalSnapshot").mockReturnValue(null);
  render(<AIProgressReportScreen {...props} />);
  fireEvent.press(screen.getByRole("button", { name: "Open saved AI report" }));
  expect(screen.getByRole("alert")).toHaveTextContent(/The saved AI report is unavailable/);
  expect(screen.getByText("Reading Progress Summary")).toBeTruthy();
  expect(screen.queryByText("SAVED AI REPORT")).toBeNull();
});

it("removes snapshot content immediately when leaving demo or learner mode", () => {
  const read = jest.spyOn(local, "readBundledLocalSnapshot").mockReturnValue(snapshot());
  const view = render(<AIProgressReportScreen {...props} />);
  fireEvent.press(screen.getByRole("button", { name: "Open saved AI report" }));
  view.rerender(<AIProgressReportScreen {...props} demoMode={false} />);
  expect(screen.queryByText("SAVED AI REPORT")).toBeNull();
  expect(screen.getByText("Report temporarily unavailable")).toBeTruthy();
  read.mockClear();
  view.rerender(<AIProgressReportScreen {...props} dashboard={{ ...props.dashboard, role: "guardian" } as never} />);
  expect(screen.queryByText("SAVED AI REPORT")).toBeNull();
  expect(read).not.toHaveBeenCalled();
});


it("hides the opt-in in release mode even with a valid saved artifact", () => {
  jest.replaceProperty(globalThis as typeof globalThis & { __DEV__: boolean }, "__DEV__", false);
  const read = jest.spyOn(local, "readBundledLocalSnapshot").mockReturnValue(snapshot());
  render(<AIProgressReportScreen {...props} />);
  expect(screen.queryByRole("button", { name: "Open saved AI report" })).toBeNull();
  expect(screen.getByText("Reading Progress Summary")).toBeTruthy();
  expect(read).not.toHaveBeenCalled();
});


it("keeps technical details collapsed when switching between the summary and saved report", () => {
  jest.spyOn(local, "readBundledLocalSnapshot").mockReturnValue(snapshot());
  render(<AIProgressReportScreen {...props} />);
  expect(screen.queryByText("Created earlier using sample reading data.")).toBeNull();
  fireEvent.press(screen.getByRole("button", { name: "Developer Details" }));
  expect(screen.getByText("AI GENERATION NOT CONNECTED")).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "Open saved AI report" }));
  expect(screen.getByText("Created earlier using sample reading data.")).toBeTruthy();
  expect(screen.queryByText(/Model: qwen3:4b/)).toBeNull();
  expect(screen.getByRole("button", { name: "Developer Details" }).props.accessibilityState.expanded).toBe(false);
  fireEvent.press(screen.getByRole("button", { name: "Developer Details" }));
  expect(screen.getByText(/Model: qwen3:4b/)).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "Return to reading summary" }));
  expect(screen.queryByText("AI GENERATION NOT CONNECTED")).toBeNull();
  expect(screen.getByText("Reading Progress Summary")).toBeTruthy();
});
