import { fireEvent, render, screen } from "@testing-library/react-native";

import * as selection from "../preview/backendRecommendationSnapshot";

import fixture from "../preview/backendRecommendationSnapshot.json";
import { selectBackendRecommendation, validateBackendRecommendation } from "../preview/backendRecommendationSnapshot";
import { buildSyntheticDashboard } from "../preview/syntheticData";
import { LearnerSuggestionsScreen } from "../screens/LearnerSuggestionsScreen";

const gates = { enabled: true, development: true, demoMode: true, role: "learner" as const };
it("validates the pinned minimized engine fixture and detaches returned data", () => {
  const result = validateBackendRecommendation(fixture, "learner");
  expect(result).toEqual(fixture);
  result!.presentation.proposed.push("changed");
  expect(validateBackendRecommendation(fixture, "learner")).toEqual(fixture);
  for (const field of ["learner_id", "session_id", "row_version", "raw_sessions"]) {
    expect(JSON.stringify(fixture)).not.toContain(field);
  }
  expect(fixture.presentation.changes_applied).toBe(false);
  expect(fixture.presentation.automatic_application_allowed).toBe(false);
});
it.each([
  { ...fixture, role: "guardian" }, { ...fixture, synthetic: false },
  { ...fixture, context: "unknown" }, { ...fixture, reporting_start: "2026-09-01" },
  { ...fixture, learner_id: "private" }, { ...fixture, source: "frontend" },
  { ...fixture, presentation: { ...fixture.presentation, action: "unknown" } },
  { ...fixture, presentation: { ...fixture.presentation, current: "unknown" } },
  { ...fixture, presentation: { ...fixture.presentation, reasons: ["invented claim"] } },
  { ...fixture, presentation: { ...fixture.presentation, global_lock: true } },
  { ...fixture, presentation: { ...fixture.presentation, changes_applied: true } },
  null,
])("rejects invalid or mismatched artifacts %#", (value) => {
  expect(validateBackendRecommendation(value, "learner")).toBeNull();
});
it.each([
  { ...gates, enabled: false }, { ...gates, development: false },
  { ...gates, demoMode: false }, { ...gates, role: "guardian" as const },
  { ...gates, role: "educator" as const },
])("checks opt-in, development, demo and learner gates before reading %#", (selection) => {
  const read = jest.fn(() => fixture);
  expect(selectBackendRecommendation({ ...selection, read })).toBeNull();
  expect(read).not.toHaveBeenCalled();
});
it("rejects unavailable snapshots without a demo substitution", () => {
  expect(selectBackendRecommendation({ ...gates, read: () => { throw Error("unavailable"); } })).toBeNull();
});
it("requires explicit selection and keeps the saved period separate from dashboard evidence", () => {
  const dashboard = buildSyntheticDashboard("learner", 30);
  const before = JSON.stringify(dashboard);
  render(<LearnerSuggestionsScreen dashboard={dashboard} demoMode periodDays={30} />);
  expect(screen.queryByText("SYNTHETIC BACKEND RECOMMENDATION ? ADVISORY ONLY")).toBeNull();
  fireEvent.press(screen.getByRole("button", { name: "View backend synthetic recommendation" }));
  expect(screen.getByText("SYNTHETIC BACKEND RECOMMENDATION ? ADVISORY ONLY")).toBeTruthy();
  expect(screen.getByText(fixture.presentation.action)).toBeTruthy();
  expect(screen.getByText(/2026-01-01 to 2026-01-31/)).toBeTruthy();
  expect(screen.queryByText(/Observed reading context:/)).toBeNull();
  expect(screen.getByText("No settings were changed. Review ideas with a parent or teacher.")).toBeTruthy();
  expect(JSON.stringify(dashboard)).toBe(before);
  fireEvent.press(screen.getByRole("button", { name: "Return to demo suggestions" }));
  fireEvent.press(screen.getByRole("button", { name: "Why This Tip?" }));
  expect(screen.getByText(/Reading context:/)).toBeTruthy();
});
it("does not render a learner snapshot in live mode or for other roles", () => {
  const { rerender } = render(<LearnerSuggestionsScreen dashboard={buildSyntheticDashboard("learner", 30)} demoMode={false} periodDays={30} />);
  expect(screen.queryByRole("button", { name: "View backend synthetic recommendation" })).toBeNull();
  // @ts-expect-error Deliberately bypass the learner prop type to verify the runtime role guard.
  rerender(<LearnerSuggestionsScreen dashboard={buildSyntheticDashboard("guardian", 30)} demoMode periodDays={30} />);
  expect(screen.queryByRole("button", { name: "View backend synthetic recommendation" })).toBeNull();
});


it("shows an unavailable selected preview without frontend recommendation fallback", () => {
  const spy = jest.spyOn(selection, "selectBackendRecommendation").mockReturnValue(null);
  try {
    render(<LearnerSuggestionsScreen dashboard={buildSyntheticDashboard("learner", 30)} demoMode periodDays={30} />);
    fireEvent.press(screen.getByRole("button", { name: "View backend synthetic recommendation" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Backend snapshot unavailable or invalid. No recommendation is substituted.");
    expect(screen.queryByText("Adaptive recommendation")).toBeNull();
    expect(screen.queryByText(/Observed reading context:/)).toBeNull();
  } finally { spy.mockRestore(); }
});
it("hides the selector in a production build", () => {
  jest.replaceProperty(globalThis as typeof globalThis & { __DEV__: boolean }, "__DEV__", false);
  try {
    render(<LearnerSuggestionsScreen dashboard={buildSyntheticDashboard("learner", 30)} demoMode periodDays={30} />);
    expect(screen.queryByRole("button", { name: "View backend synthetic recommendation" })).toBeNull();
    fireEvent.press(screen.getByRole("button", { name: "Why This Tip?" }));
    expect(screen.getByText(/Reading context:/)).toBeTruthy();
  } finally { jest.restoreAllMocks(); }
});

beforeEach(() => { process.env.EXPO_PUBLIC_COMPONENT4_DEVELOPER_TOOLS = "1"; });
afterEach(() => { delete process.env.EXPO_PUBLIC_COMPONENT4_DEVELOPER_TOOLS; });
