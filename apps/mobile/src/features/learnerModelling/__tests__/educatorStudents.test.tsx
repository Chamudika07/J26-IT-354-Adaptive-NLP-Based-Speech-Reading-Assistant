import { act, fireEvent, render, screen } from "@testing-library/react-native";
import { EducatorStudents } from "../components/EducatorStudents";
import { selectEducatorStudent } from "../preview/educatorStudents";
import { publishScenario, scenarioId } from "../preview/selectedScenario";
import { selectConnectedReplay } from "../preview/connectedSessionPreview";
import { Text } from "react-native";

const sample = (index: number) => selectConnectedReplay({ index, development: true, demoMode: true, role: "learner" })!;
beforeEach(() => publishScenario(null));
afterEach(() => { publishScenario(null); jest.restoreAllMocks(); });

it("switches fictional students without sharing learner-only fields and follows scenario changes", () => {
  publishScenario(3, sample(3));
  render(<EducatorStudents><Text>Independent example</Text></EducatorStudents>);
  expect(screen.getByText("My Students")).toBeTruthy();
  expect(screen.getByText("3 completed sessions")).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "View Alex Storybook" }));
  expect(screen.getByText("3 completed sessions")).toBeTruthy();
  act(() => publishScenario(4, sample(4)));
  expect(screen.getByText("4 completed sessions")).toBeTruthy();
  fireEvent.press(screen.getByText("Back to My Students"));
  fireEvent.press(screen.getByRole("button", { name: "View Robin Page" }));
  expect(screen.getByText("6 completed sessions")).toBeTruthy();
  act(() => publishScenario(2, sample(2)));
  expect(screen.getByText("6 completed sessions")).toBeTruthy();
  fireEvent.press(screen.getByText("Back to My Students"));
  fireEvent.press(screen.getByRole("button", { name: "View Jamie Bookmark" }));
  expect(screen.getByText("2 completed sessions")).toBeTruthy();
  expect(screen.getAllByText("Unavailable").length).toBeGreaterThan(0);
  expect(screen.queryByText(/engagement|Why This Tip|Download AI Report/i)).toBeNull();
  fireEvent.press(screen.getByText("Back to My Students"));
  fireEvent.press(screen.getByRole("button", { name: "View Alex Storybook" }));
  expect(screen.getByText("2 completed sessions")).toBeTruthy();
  expect(scenarioId(2, sample(2))).toBeTruthy();
});

it("fails closed for absent or mismatched selected evidence and preserves explicit fallback", () => {
  render(<EducatorStudents><Text>Independent example</Text></EducatorStudents>);
  fireEvent.press(screen.getByRole("button", { name: "View Alex Storybook" }));
  expect(screen.getByRole("alert")).toBeTruthy();
  act(() => publishScenario(999, sample(3)));
  expect(screen.queryByText("3 completed sessions")).toBeNull();
  fireEvent.press(screen.getByText("View separate example"));
  expect(screen.getByText("Independent example")).toBeTruthy();
  fireEvent.press(screen.getByText("Back to My Students"));
  expect(screen.getByText("My Students")).toBeTruthy();
});

it("rejects corrupted, extra-field and release artifacts; returns detached role-only copies", () => {
  const p = selectEducatorStudent(0)!;
  expect(JSON.stringify(p)).not.toMatch(/engagement|recommendation|learner_id|feedback/);
  p.included_session_count = 999;
  expect(selectEducatorStudent(0)!.included_session_count).toBe(6);
  for (const index of [-1, 2, 0.5]) expect(selectEducatorStudent(index)).toBeNull();
  expect(selectEducatorStudent(0, () => [{ ...p, engagement: 100 }])).toBeNull();
  expect(selectEducatorStudent(0, () => { throw Error("unavailable"); })).toBeNull();
  jest.replaceProperty(globalThis as typeof globalThis & { __DEV__: boolean }, "__DEV__", false);
  expect(selectEducatorStudent(0)).toBeNull();
  render(<EducatorStudents><Text>Independent example</Text></EducatorStudents>);
  expect(screen.queryByText("My Students")).toBeNull();
});
