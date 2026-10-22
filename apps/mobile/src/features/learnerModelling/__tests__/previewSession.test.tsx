import { readFileSync } from "node:fs";
import { publishScenario } from "../preview/selectedScenario";

import { fireEvent, render, screen } from "@testing-library/react-native";
import { StyleSheet } from "react-native";

import App from "../../../../App";
import { demoDashboardProvider, unavailableLiveDashboardProvider } from "../data/dashboardProvider";
import { buildSyntheticDashboard } from "../preview/syntheticData";
import { LearnerProgressScreen } from "../screens/LearnerProgressScreen";

const open = (name: string) => fireEvent.press(name === "My Profile" ? screen.getByRole("tab", { name: "Profile learner view" }) : screen.getByRole("button", { name: `Open ${name}` }));
const home = () => fireEvent.press(screen.getByRole("button", { name: "Back to reading Home" }));
function chooseSettings() {
  fireEvent.press(screen.getByRole("radio", { name: "Line spacing: Wide" }));
  fireEvent.press(screen.getByRole("radio", { name: "Reading font size: XL" }));
  fireEvent(screen.getByRole("switch", { name: "Text highlighting preference" }), "valueChange", true);
  fireEvent(screen.getByRole("switch", { name: "Audio-support preference" }), "valueChange", true);
}
function expectSettingsDefaults() {
  expect(screen.getByRole("radio", { name: "Line spacing: Normal" }).props.accessibilityState.checked).toBe(true);
  expect(screen.getByRole("radio", { name: "Reading font size: Normal" }).props.accessibilityState.checked).toBe(true);
  expect(screen.getByRole("switch", { name: "Text highlighting preference" }).props.value).toBe(false);
  expect(screen.getByRole("switch", { name: "Audio-support preference" }).props.value).toBe(false);
}
function chooseFeedback() {
  for (const [question, answer] of [["How did reading feel?", "Happy"], ["Was it easy, okay, or difficult?", "Okay"], ["Would you like to continue reading?", "Yes"]]) {
    fireEvent.press(screen.getByRole("radio", { name: `${question}: ${answer}` }));
  }
}
const answers = "Feeling: Happy\nDifficulty: Okay\nContinue reading: Yes";
const empty = "Feeling: Not selected\nDifficulty: Not selected\nContinue reading: Not selected";

it("retains both drafts across screens and period changes; resets each independently", async () => {
  render(<App />);
  await screen.findByText("Hi, Reader!");
  open("Support Settings");
  chooseSettings();
  home();
  open("Session Feedback");
  chooseFeedback();
  home();
  open("Support Settings");
  expect(StyleSheet.flatten(screen.getByTestId("support-sample-text").props.style).fontSize).toBe(28);
  expect(StyleSheet.flatten(screen.getByTestId("support-sample-text").props.style).lineHeight).toBe(56);
  expect(screen.getByRole("switch", { name: "Text highlighting preference" }).props.value).toBe(true);
  expect(screen.getByRole("switch", { name: "Audio-support preference" }).props.value).toBe(true);
  fireEvent.press(screen.getByRole("radio", { name: "7 day reporting period" }));
  await screen.findByTestId("support-sample-text");
  expect(screen.getByRole("radio", { name: "Reading font size: XL" }).props.accessibilityState.checked).toBe(true);
  fireEvent.press(screen.getByRole("button", { name: "Reset Settings" }));
  expectSettingsDefaults();
  home();
  open("Session Feedback");
  expect(screen.getByText(answers)).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "Clear preview responses" }));
  expect(screen.getByText(empty)).toBeTruthy();
  home();
  open("Session Feedback");
  expect(screen.getByText(empty)).toBeTruthy();
});

it.each(["Guardian", "Educator"])("discards Learner drafts when switching to %s", async (role) => {
  render(<App />);
  await screen.findByText("Hi, Reader!");
  open("Support Settings"); chooseSettings(); home();
  open("Session Feedback"); chooseFeedback();
  fireEvent.press(screen.getByRole("tab", { name: `${role} sample preview` }));
  if (role === "Educator") fireEvent.press(await screen.findByRole("button", { name: "View separate example" }));
  await screen.findByText(role === "Guardian" ? "Guardian progress summary" : "Educator reading analytics");
  expect(screen.queryByText(answers)).toBeNull();
  expect(screen.queryByTestId("support-sample-text")).toBeNull();
  fireEvent.press(screen.getByRole("tab", { name: "Learner sample preview" }));
  await screen.findByText("Hi, Reader!");
  open("Support Settings"); expectSettingsDefaults(); home();
  open("Session Feedback"); expect(screen.getByText(empty)).toBeTruthy();
});

it("destroys drafts on entering live mode and does not restore them on returning to demo", async () => {
  const view = render(<LearnerProgressScreen periodDays={30} />);
  await screen.findByText("Hi, Reader!");
  open("Session Feedback"); chooseFeedback(); home();
  open("Support Settings"); chooseSettings();
  view.rerender(<LearnerProgressScreen periodDays={30} provider={unavailableLiveDashboardProvider} />);
  expect(screen.queryByTestId("support-sample-text")).toBeNull();
  view.rerender(<LearnerProgressScreen periodDays={30} provider={demoDashboardProvider} />);
  await screen.findByTestId("support-sample-text");
  expectSettingsDefaults(); home();
  open("Session Feedback"); expect(screen.getByText(empty)).toBeTruthy();
});

it("discards drafts when the feature unmounts; uses no network and never changes authoritative settings", async () => {
  const fetchSpy = jest.spyOn(globalThis, "fetch");
  try {
    const before = JSON.stringify(buildSyntheticDashboard("learner", 30));
    const view = render(<LearnerProgressScreen periodDays={30} />);
    await screen.findByText("Hi, Reader!");
    open("Support Settings"); chooseSettings(); home();
    open("Session Feedback"); chooseFeedback(); home();
    open("My Profile");
    expect(screen.getByText("Reading Settings")).toBeTruthy();
    expect(JSON.stringify(buildSyntheticDashboard("learner", 30))).toBe(before);
    expect(fetchSpy).not.toHaveBeenCalled();
    view.unmount();
    render(<LearnerProgressScreen periodDays={30} />);
    await screen.findByText("Hi, Reader!");
    open("Support Settings"); expectSettingsDefaults(); home();
    open("Session Feedback"); expect(screen.getByText(empty)).toBeTruthy();
  } finally { fetchSpy.mockRestore(); }
});


it("uses only the isolated demo storage and never production settings or network", () => {
  const source = readFileSync(require.resolve("../preview/PreviewSession"), "utf8");
  const dependencies = [...source.matchAll(/from ["']([^"']+)["']/g)].map((match) => match[1]);
  expect(dependencies).toEqual(["react", "./demoPersistence", "./DeveloperTestSession"]);
  expect(source).not.toMatch(/fetch\s*\(|XMLHttpRequest|AsyncStorage|SecureStore|localStorage|sessionStorage/);
});


it("previews, cancels, saves and resets a temporary profile across learner navigation", async () => {
  const network = jest.spyOn(globalThis, "fetch");
  render(<App />); await screen.findByText("Hi, Reader!");
  fireEvent.press(screen.getByRole("tab", { name: "Profile learner view" }));
  fireEvent.press(screen.getByRole("button", { name: "Edit Profile" }));
  fireEvent.changeText(screen.getByLabelText("Demo display name"), "Sample Robin");
  fireEvent.press(screen.getByRole("radio", { name: "Choose your avatar: Reading Owl" }));
  expect(screen.getByTestId("demo-profile-preview")).toHaveTextContent(/Sample Robin/);
  fireEvent.press(screen.getByRole("button", { name: "Cancel profile changes" }));
  expect(screen.queryByText("Sample Robin")).toBeNull();
  fireEvent.press(screen.getByRole("button", { name: "Edit Profile" }));
  fireEvent.changeText(screen.getByLabelText("Demo display name"), "Sample Robin");
  fireEvent.press(screen.getByRole("radio", { name: "Choose your avatar: Reading Owl" }));
  fireEvent.press(screen.getByRole("button", { name: "Save demo profile" }));
  home();
  expect(screen.getByText("Sample Robin")).toBeTruthy();
  expect(screen.getByRole("image", { name: "Reading Owl avatar" })).toBeTruthy();
  fireEvent.press(screen.getByRole("tab", { name: "Profile learner view" }));
  fireEvent.press(screen.getByRole("button", { name: "Edit Profile" }));
  fireEvent.changeText(screen.getByLabelText("Demo display name"), "   ");
  fireEvent.press(screen.getByRole("button", { name: "Save demo profile" }));
  expect(screen.getByText("Choose a name with 1 to 32 letters or characters.")).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "Reset demo profile" }));
  expect(screen.getByText("Demo Learner")).toBeTruthy();
  expect(screen.getByRole("image", { name: "Book Buddy avatar" })).toBeTruthy();
  expect(network).not.toHaveBeenCalled();
  network.mockRestore();
});

it("never shares edited identity with role demos and clears it on role change", async () => {
  render(<App />); await screen.findByText("Hi, Reader!");
  fireEvent.press(screen.getByRole("tab", { name: "Profile learner view" }));
  fireEvent.press(screen.getByRole("button", { name: "Edit Profile" }));
  fireEvent.changeText(screen.getByLabelText("Demo display name"), "Sample Fox");
  fireEvent.press(screen.getByRole("button", { name: "Save demo profile" }));
  fireEvent.press(screen.getByRole("tab", { name: "Guardian sample preview" }));
  await screen.findByText("Guardian progress summary");
  expect(screen.queryByText("Sample Fox")).toBeNull();
  expect(screen.queryByRole("button", { name: "Edit Profile" })).toBeNull();
  fireEvent.press(screen.getByRole("tab", { name: "Learner sample preview" }));
  await screen.findByText("Hi, Reader!");
  expect(screen.getByText("Demo Learner")).toBeTruthy();
});

beforeEach(() => { publishScenario(null); });
