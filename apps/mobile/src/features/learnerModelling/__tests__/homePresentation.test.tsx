import { HomeHero } from "../components/HomeHero";
import { ConnectedLearnerJourney } from "../components/ConnectedLearnerJourney";
import { DeveloperTestBoundary } from "../preview/DeveloperTestSession";
import { Pp1ConnectionContext } from "../preview/Pp1Connection";
import { selectConnectedReplay } from "../preview/connectedSessionPreview";
import { act, fireEvent, render, screen, within } from "@testing-library/react-native";
import { Dimensions, StyleSheet } from "react-native";
import App from "../../../../App";

it("keeps Home controls compact and restores other learner screens", async () => {
  render(<App />);
  await screen.findByText("Hi, Reader!");
  expect(screen.getAllByText("Demo Mode \u00b7 Fictional data")).toHaveLength(1);
  expect(screen.queryByText("Sample Data")).toBeNull();
  expect(screen.getByText("Reading Results")).toBeTruthy();
  const signIn = screen.getByRole("button", { name: "Sign In for Live Mode" });
  expect(StyleSheet.flatten(signIn.props.style).alignSelf).toBe("flex-end");
  expect(StyleSheet.flatten(signIn.props.style).minHeight).toBeGreaterThanOrEqual(44);
  const learner = screen.getByRole("tab", { name: "Learner sample preview" });
  expect(StyleSheet.flatten(learner.props.style).minHeight).toBe(44);
  const period = screen.getByRole("radio", { name: "7 day reporting period" });
  expect(StyleSheet.flatten(period.props.style).minHeight).toBe(44);
  fireEvent.press(period);
  await screen.findByText("4");
  expect(screen.getByRole("radio", { name: "7 day reporting period" }).props.accessibilityState.checked).toBe(true);
  fireEvent.press(screen.getByRole("tab", { name: "Analytics learner view" }));
  await screen.findByRole("header", { name: "My Reading Analytics" });
  expect(screen.queryByText("Demo Mode \u00b7 Fictional data")).toBeNull();
  expect(StyleSheet.flatten(screen.getByRole("radio", { name: "7 day reporting period" }).props.style).minHeight).toBe(48);
  expect(StyleSheet.flatten(screen.getByRole("tab", { name: "Learner sample preview" }).props.style).minHeight).toBe(56);
});

it("keeps sign-in reachable from compact Home", async () => {
  render(<App />);
  await screen.findByText("Hi, Reader!");
  fireEvent.press(screen.getByRole("button", { name: "Sign In for Live Mode" }));
  expect(screen.getByRole("header", { name: "Sign in to ReadBuddy" })).toBeTruthy();
  expect(screen.getByLabelText("HTTPS server address")).toBeTruthy();
});

it.each([0, 3, 6])("keeps scenario %s Home metrics and reading navigation unchanged", index => {
  const a = selectConnectedReplay({ index, development: true, demoMode: true, role: "learner" })!;
  const navigate = jest.fn();
  render(<DeveloperTestBoundary enabled><ConnectedLearnerJourney artifact={a} destination="home" onNavigate={navigate} /></DeveloperTestBoundary>);
  expect(within(screen.getByTestId("home-Completed Sessions")).getByText(String(a.includedSessionCount))).toBeTruthy();
  for (const [key, label, scale, unit] of [["reading_accuracy", "Reading Accuracy (%)", 100, "%"], ["reading_fluency_wpm", "Reading Speed (WPM)", 1, " WPM"]] as const) {
    const raw = a.metrics.find(m => m.metric_name === key)?.latest_value;
    const expected = raw == null ? "Not measured" : `${Number((Number(raw) * scale).toFixed(2))}${unit}`;
    expect(within(screen.getByTestId(`home-${label}`)).getByText(expected)).toBeTruthy();
  }
  fireEvent.press(screen.getByRole("button", { name: "Reading Results" })); expect(navigate).toHaveBeenCalledWith("test");
  expect(screen.queryByText(/streak|achievement|daily goal/i)).toBeNull();
});
it.each(["offline", "connected"])("preserves the subtle %s Home disclosure", mode => {
  const a = selectConnectedReplay({ index: 3, development: true, demoMode: true, role: "learner" })!;
  render(<Pp1ConnectionContext.Provider value={mode === "connected" ? { baseUrl: "https://example.test/api/v1", session: { scopeKey: "home-refresh-test", getAccessToken: async () => "test" } } : undefined}>
    <DeveloperTestBoundary enabled><ConnectedLearnerJourney artifact={a} destination="home" /></DeveloperTestBoundary>
  </Pp1ConnectionContext.Provider>);
  expect(screen.getAllByText(mode === "connected" ? "Demo Mode \u00b7 Fictional data \u00b7 Calculated on laptop" : "Demo Mode \u00b7 Fictional data")).toHaveLength(1);
  expect(screen.queryByText("Sample Data")).toBeNull();
});
it("uses the selected Home accents and readable text contrast without changing global styles", () => {
  render(<HomeHero sessions={0} accuracy="Unavailable" speed="Unavailable" onStart={() => {}} />);
  const button = screen.getByRole("button", { name: "Reading Results" });
  const background = StyleSheet.flatten(button.props.style).backgroundColor;
  const foreground = StyleSheet.flatten(screen.getByText("Reading Results").props.style).color;
  expect(background).toBe("#1D4ED8");
  expect(foreground).toBe("#FFFFFF");
  expect(StyleSheet.flatten(screen.getByText("\u2192").props.style).color).toBe("#FFFFFF"); expect(StyleSheet.flatten(button.props.style).minHeight).toBeGreaterThanOrEqual(44);
  for (const [label, accent] of [["Completed Sessions", "#22C55E"], ["Reading Accuracy (%)", "#3182F6"], ["Reading Speed (WPM)", "#8B5CF6"]]) expect(StyleSheet.flatten(screen.getByTestId(`home-${label}`).props.style).borderTopColor).toBe(accent);
  const luminance = (hex: string) => [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255).map(v => v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4).reduce((sum, v, i) => sum + v * [0.2126, 0.7152, 0.0722][i]!, 0);
  const light = Math.max(luminance(foreground), luminance(background)); const dark = Math.min(luminance(foreground), luminance(background));
  expect((light + 0.05) / (dark + 0.05)).toBeGreaterThanOrEqual(4.5);
});
it("stacks Home metrics on a small iPhone with large text and keeps the action reachable", () => {
  const original = { window: Dimensions.get("window"), screen: Dimensions.get("screen") };
  act(() => Dimensions.set({ window: { width: 320, height: 568, scale: 2, fontScale: 2 } }));
  const view = render(<HomeHero sessions={0} accuracy="Unavailable" speed="Unavailable" onStart={() => {}} />);
  try {
    for (const label of ["Completed Sessions", "Reading Accuracy (%)", "Reading Speed (WPM)"]) {
      const style = StyleSheet.flatten(screen.getByTestId(`home-${label}`).props.style);
      expect(style.flexBasis).toBe("100%"); expect(style.height).toBeUndefined();
    }
    expect(screen.getByRole("button", { name: "Reading Results" })).toBeTruthy();
    expect(screen.getByText("Hi, Reader!").props.allowFontScaling).not.toBe(false);
  } finally { view.unmount(); act(() => Dimensions.set(original)); }
});

it("shows concise Home labels and each measurement unit once", () => {
  render(<HomeHero sessions={3} accuracy="95%" speed="100" onStart={() => {}} />);
  const accuracy = within(screen.getByTestId("home-Reading Accuracy (%)"));
  expect(accuracy.getByText("Accuracy")).toBeTruthy();
  expect(accuracy.getAllByText("95%")).toHaveLength(1);
  expect(accuracy.queryByText("%")).toBeNull();
  const speed = within(screen.getByTestId("home-Reading Speed (WPM)"));
  expect(speed.getByText("Speed")).toBeTruthy();
  expect(speed.getAllByText("100 WPM")).toHaveLength(1);
  expect(screen.queryByText("Reading Speed (WPM)")).toBeNull();
  expect(screen.queryByText("Reading Accuracy (%)")).toBeNull();
});
