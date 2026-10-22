import { act, fireEvent, render, screen, within } from "@testing-library/react-native";
import { BackHandler, StyleSheet } from "react-native";
import { publishScenario } from "../preview/selectedScenario";

import App from "../../../../App";
import { demoDashboardProvider, unavailableLiveDashboardProvider } from "../data/dashboardProvider";
import { buildSyntheticDashboard } from "../preview/syntheticData";
import { LearnerProgressScreen } from "../screens/LearnerProgressScreen";
import { palette } from "../theme";

afterEach(() => { delete process.env.EXPO_PUBLIC_COMPONENT4_DEVELOPER_TOOLS; jest.restoreAllMocks(); });

async function open(title: string) {
  render(<App />);
  await screen.findByText("Hi, Reader!");
  fireEvent.press(screen.getByRole("button", { name: `Open ${title}` }));
}

it("keeps Home evidence accessible without initially overwhelming the overview", async () => {
  render(<App />);
  await screen.findByText("Hi, Reader!");
  const metric = buildSyntheticDashboard("learner", 30).metrics[0]!;
  const card = within(screen.getByTestId("reading_accuracy-card"));
  expect(card.getByText(metric.evidenceLabel)).toBeTruthy();
  expect(card.queryByText(metric.explanation)).toBeNull();
  const show = card.getByRole("button", { name: "Show Reading accuracy details" });
  expect(show.props.accessibilityState.expanded).toBe(false);
  fireEvent.press(show);
  expect(card.getByText(metric.explanation)).toBeTruthy();
  expect(card.getByTestId("reading_accuracy-first-bar")).toBeTruthy();
  const hide = card.getByRole("button", { name: "Hide Reading accuracy details" });
  expect(hide.props.accessibilityState.expanded).toBe(true);
  fireEvent.press(hide);
  expect(card.queryByText(metric.explanation)).toBeNull();
});

it("discovers all original areas without adding secondary bottom tabs", async () => {
  render(<App />);
  await screen.findByText("Hi, Reader!");
  for (const title of ["My Profile", "Support Settings", "Session Feedback", "My Reading Analytics", "My Reading Tips", "My Reading Report"]) {
    const tab = ({ "My Profile": "Profile", "My Reading Analytics": "Analytics", "My Reading Tips": "Suggestions" } as Record<string, string>)[title];
    const link = tab ? screen.getByRole("tab", { name: `${tab} learner view` }) : screen.getByRole("button", { name: `Open ${title}` });
    expect(StyleSheet.flatten(link.props.style).minHeight).toBeGreaterThanOrEqual(48);
    fireEvent.press(link);
    expect(screen.getByRole("header", { name: title === "Support Settings" ? "Reading Settings" : title === "My Reading Analytics" ? "My Reading Analytics" : title === "My Reading Report" ? "My Reading Report" : title })).toBeTruthy();
    expect(screen.getByText(["My Reading Analytics", "My Profile", "Support Settings", "My Reading Tips"].includes(title) ? "Demo \u00b7 Fictional data" : "Sample Data")).toBeTruthy();
    fireEvent.press(screen.getByRole("button", { name: "Back to reading Home" }));
  }
  const navigation = within(screen.getByLabelText("Learner feature navigation"));
  expect(navigation.getAllByRole("tab")).toHaveLength(4);
  expect(screen.getByText("Parent / Teacher Dashboard")).toBeTruthy();
  fireEvent.press(screen.getByRole("tab", { name: "Guardian sample preview" }));
  await screen.findByText("Guardian progress summary");
  for (const metric of buildSyntheticDashboard("guardian", 30).metrics) {
    expect(within(screen.getByTestId(`${metric.key}-card`)).getByText(metric.detail!)).toBeTruthy();
  }
  fireEvent.press(screen.getByRole("tab", { name: "Educator sample preview" }));
  fireEvent.press(await screen.findByRole("button", { name: "View separate example" }));
  await screen.findByText("Educator reading analytics");
  expect(screen.getAllByText(/formula version v1/)).toHaveLength(3);
  expect(screen.getAllByText(/windows contain 3 and 3 comparable observations/)).toHaveLength(3);
  expect(screen.getByText("Sample Data")).toBeTruthy();
  expect(screen.queryByLabelText("Learner feature navigation")).toBeNull();
});

it("previews font, highlighting and audio preferences across navigation until explicitly reset", async () => {
  await open("Support Settings");
  expect(screen.getByText("Save these choices on this device.")).toBeTruthy();
  expect(StyleSheet.flatten(screen.getByTestId("support-sample-text").props.style).fontSize).toBe(18);
  fireEvent.press(screen.getByRole("radio", { name: "Reading font size: XL" }));
  expect(StyleSheet.flatten(screen.getByTestId("support-sample-text").props.style).fontSize).toBe(28);
  expect(screen.getByRole("radio", { name: "Reading font size: XL" }).props.accessibilityState.checked).toBe(true);
  fireEvent(screen.getByRole("switch", { name: "Text highlighting preference" }), "valueChange", true);
  expect(screen.getByText("Highlighting is on in this sample.")).toBeTruthy();
  expect(StyleSheet.flatten(screen.getByText("The kind fox shares a book.").props.style).backgroundColor).toBe(palette.yellowSoft);
  fireEvent(screen.getByRole("switch", { name: "Audio-support preference" }), "valueChange", true);
  expect(screen.getByText("Audio playback is not connected.")).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "Back to reading Home" }));
  fireEvent.press(screen.getByRole("tab", { name: "Profile learner view" }));
  expect(screen.getByText("Reading Settings")).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "Reading Settings" }));
  expect(StyleSheet.flatten(screen.getByTestId("support-sample-text").props.style).fontSize).toBe(28);
  expect(screen.getByRole("switch", { name: "Audio-support preference" }).props.value).toBe(true);
  expect(screen.getByText("Highlighting is on in this sample.")).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "Reset Settings" }));
  expect(StyleSheet.flatten(screen.getByTestId("support-sample-text").props.style).fontSize).toBe(18);
  expect(screen.getByText("Highlighting is off in this sample.")).toBeTruthy();
  expect(screen.getByRole("switch", { name: "Audio-support preference" }).props.value).toBe(false);
});

it("collects only temporary feedback choices and can clear or discard them", async () => {
  await open("Session Feedback");
  expect(screen.getByText(/not sent or saved to a real reading session/)).toBeTruthy();
  for (const [question, answer] of [
    ["How did reading feel?", "Unsure"],
    ["Was it easy, okay, or difficult?", "Difficult"],
    ["Would you like to continue reading?", "Maybe later"],
  ]) {
    const radio = screen.getByRole("radio", { name: `${question}: ${answer}` });
    fireEvent.press(radio);
    expect(screen.getByRole("radio", { name: `${question}: ${answer}` }).props.accessibilityState.checked).toBe(true);
  }
  expect(screen.getByText("Feeling: Unsure\nDifficulty: Difficult\nContinue reading: Maybe later")).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "Clear preview responses" }));
  for (const question of ["How did reading feel?", "Was it easy, okay, or difficult?", "Would you like to continue reading?"]) {
    expect(within(screen.getByLabelText(question)).getAllByRole("radio").every((radio) => !radio.props.accessibilityState.checked)).toBe(true);
  }
  fireEvent.press(screen.getByRole("radio", { name: "How did reading feel?: Happy" }));
  fireEvent.press(screen.getByRole("button", { name: "Back to reading Home" }));
  fireEvent.press(screen.getByRole("button", { name: "Open Session Feedback" }));
  expect(screen.getByText("Feeling: Happy\nDifficulty: Not selected\nContinue reading: Not selected")).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "Clear preview responses" }));
  expect(screen.getByText("Feeling: Not selected\nDifficulty: Not selected\nContinue reading: Not selected")).toBeTruthy();
  expect(screen.getByText(/not sent or saved to a real reading session/)).toBeTruthy();
});

it("renders the deterministic report from the current projection for every reporting period", async () => {
  const fetchSpy = jest.spyOn(globalThis, "fetch");
  process.env.EXPO_PUBLIC_COMPONENT4_DEVELOPER_TOOLS = "1";
  await open("My Reading Report");
  for (const days of [7, 30, 90] as const) {
    fireEvent.press(screen.getByRole("radio", { name: `${days} day reporting period` }));
    await screen.findByText("My Reading Report");
    fireEvent.press(screen.getByRole("button", { name: "Read reading summary" }));
    fireEvent.press(screen.getByRole("button", { name: "Developer Details" }));
    expect(screen.getByText(`${days}-day reporting period`)).toBeTruthy();
    expect(screen.getByText("Reading Progress Summary")).toBeTruthy();
    expect(screen.getByText("AI GENERATION NOT CONNECTED")).toBeTruthy();
    expect(screen.getByText("Sample Data")).toBeTruthy();
    const dashboard = buildSyntheticDashboard("learner", days);
    for (const metric of dashboard.metrics) {
      const card = within(screen.getByTestId(`${metric.key}-card`));
      expect(card.getByText(metric.unit)).toBeTruthy();
      expect(card.getByText(metric.explanation)).toBeTruthy();
      expect(card.getByText(metric.evidenceLabel)).toBeTruthy();
      expect(card.getAllByText(metric.key === "reading_accuracy" ? `${metric.latestValue}%` : `${metric.latestValue}`)).toHaveLength(2);
    }
    for (const observation of dashboard.difficultyProgression) {
      expect(screen.getByText(observation.explanation)).toBeTruthy();
    }
    for (const limitation of dashboard.limitations) expect(screen.getByText(limitation)).toBeTruthy();
    expect(screen.getByText(dashboard.recommendation.explanation)).toBeTruthy();
    expect(screen.getByText("ADVISORY ONLY")).toBeTruthy();
    if (days === 7) {
      expect(screen.getAllByText("More evidence needed")).toHaveLength(3);
      expect(screen.queryByText(/Early-window mean/)).toBeNull();
    }
    // No export is available from the deterministic demo or without native packages.
    expect(screen.getByRole("button", { name: "Download AI Report PDF" })).toBeDisabled();
  }
  expect(fetchSpy).not.toHaveBeenCalled();
});

it("does not reload other role projections or change recommendations after local interactions", async () => {
  const provider = {
    ...demoDashboardProvider,
    loadLearnerProgress: jest.fn(demoDashboardProvider.loadLearnerProgress),
    loadGuardianSummary: jest.fn(demoDashboardProvider.loadGuardianSummary),
    loadEducatorAnalytics: jest.fn(demoDashboardProvider.loadEducatorAnalytics),
  };
  render(<LearnerProgressScreen periodDays={7} provider={provider} />);
  await screen.findByText("Hi, Reader!");
  fireEvent.press(screen.getByRole("button", { name: "Open Support Settings" }));
  fireEvent(screen.getByRole("switch", { name: "Audio-support preference" }), "valueChange", true);
  fireEvent.press(screen.getByRole("button", { name: "Back to reading Home" }));
  fireEvent.press(screen.getByRole("button", { name: "Open Session Feedback" }));
  fireEvent.press(screen.getByRole("radio", { name: "Was it easy, okay, or difficult?: Difficult" }));
  fireEvent.press(screen.getByRole("tab", { name: "Suggestions learner view" }));
  expect(screen.getByText(buildSyntheticDashboard("learner", 7).recommendation.supportSuggestion)).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "Why This Tip?" }));
  expect(screen.getByText("Exact rule conditions: Unavailable.")).toBeTruthy();
  expect(provider.loadLearnerProgress).toHaveBeenCalledTimes(1);
  expect(provider.loadGuardianSummary).not.toHaveBeenCalled();
  expect(provider.loadEducatorAnalytics).not.toHaveBeenCalled();
});

it.each(["Support Settings", "Session Feedback", "My Reading Report"])("hides %s synchronously on provider changes and supports Android Back", async (title) => {
  const remove = jest.fn();
  const back = jest.spyOn(BackHandler, "addEventListener").mockReturnValue({ remove });
  const view = render(<LearnerProgressScreen periodDays={30} />);
  await screen.findByText("Hi, Reader!");
  fireEvent.press(screen.getByRole("button", { name: `Open ${title}` }));
  expect(screen.getByRole("header", { name: title === "Support Settings" ? "Reading Settings" : title === "My Reading Report" ? "My Reading Report" : title })).toBeTruthy();
  act(() => { expect(back.mock.calls.at(-1)?.[1]({ type: "hardwareBackPress", timeStamp: 0 })).toBe(true); });
  expect(screen.getByText("Hi, Reader!")).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: `Open ${title}` }));
  view.rerender(<LearnerProgressScreen periodDays={30} provider={unavailableLiveDashboardProvider} />);
  expect(screen.queryByRole("header", { name: title === "Support Settings" ? "Reading Settings" : title })).toBeNull();
  expect(screen.queryByText("Sample Data")).toBeNull();
  expect(await screen.findByText("Report temporarily unavailable")).toBeTruthy();
});

beforeEach(() => { publishScenario(null); });
