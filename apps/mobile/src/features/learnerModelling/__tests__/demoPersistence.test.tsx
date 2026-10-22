import { act, fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import { Alert, Pressable, Text } from "react-native";
import * as fs from "expo-file-system/legacy";
import { PreviewSessionBoundary, usePreviewSession } from "../preview/PreviewSession";
import { DeveloperTestBoundary, useDeveloperTest } from "../preview/DeveloperTestSession";
import { SupportSettingsScreen } from "../screens/SupportSettingsScreen";
import { demoStorage, validateDemoData } from "../preview/demoPersistence";
import { publishScenario } from "../preview/selectedScenario";

let mockFiles: Record<string, string> = {};
jest.mock("expo-file-system/legacy", () => ({
  documentDirectory: "file://demo/",
  getInfoAsync: jest.fn(async (uri: string) => uri in mockFiles ? { exists: true, isDirectory: false, size: mockFiles[uri]!.length } : { exists: false }),
  readAsStringAsync: jest.fn(async (uri: string) => mockFiles[uri]),
  writeAsStringAsync: jest.fn(async (uri: string, text: string) => { mockFiles[uri] = text; }),
}));
beforeEach(() => { publishScenario(null); mockFiles = {}; jest.clearAllMocks(); });
afterEach(() => jest.restoreAllMocks());
function Controls() {
  const s = usePreviewSession(); const j = useDeveloperTest()!;
  return <>
    <Text>{s.storageMessage}</Text>
    <Text testID="values">{JSON.stringify({ profile: s.profile, settings: s.settings, feedback: s.feedback, index: j.replayIndex, count: j.connected.artifact?.includedSessionCount })}</Text>
    <Pressable accessibilityRole="button" onPress={() => { s.setProfile({ name: "Sample Fox", avatar: "fox" }); s.setSettings({ font: "large", spacing: "wide", highlight: true, audio: false }); s.setFeedback({ feeling: "Happy", difficulty: "Okay", continueReading: "Yes" }); j.replay(2); }}><Text>Edit</Text></Pressable>
    <Pressable accessibilityRole="button" onPress={j.selectConnected}><Text>Select calculated result</Text></Pressable>
    <Pressable accessibilityRole="button" onPress={s.resetSettings}><Text>Reset settings</Text></Pressable>
    <Pressable accessibilityRole="button" onPress={s.resetProfile}><Text>Reset profile</Text></Pressable>
    <Pressable accessibilityRole="button" onPress={s.resetDemo}><Text>Reset all</Text></Pressable>
  </>;
}
const App = ({ allowed = true }: { allowed?: boolean }) => <DeveloperTestBoundary enabled={allowed}><PreviewSessionBoundary enabled={allowed}>{allowed ? <Controls /> : <Text>Other role or live mode</Text>}</PreviewSessionBoundary></DeveloperTestBoundary>;
const values = () => JSON.parse(screen.getByTestId("values").props.children);
const saved = () => screen.findByText("Demo choices saved on this device. Not a real learner record.");
const uri = "file://demo/readbuddy-component4-learner-demo-v1.json";

it("saves profile, settings, feedback and validated journey; restores after restart and persists resets", async () => {
  const network = jest.spyOn(globalThis, "fetch");
  let view = render(<App />); await screen.findByText("Demo choices stay on this device only.");
  fireEvent.press(screen.getByText("Edit")); await saved();
  await waitFor(() => expect(JSON.parse(mockFiles[uri]!).journey.index).toBe(2));
  const before = values(); view.unmount(); publishScenario(null); view = render(<App />);
  await screen.findByText("Demo choices restored on this device.");
  expect(values()).toEqual(before); expect(before.count).toBe(2);
  fireEvent.press(screen.getByText("Reset settings"));
  await waitFor(() => expect(JSON.parse(mockFiles[uri]!).settings.font).toBe("comfortable"));
  fireEvent.press(screen.getByText("Reset profile"));
  await waitFor(() => expect(JSON.parse(mockFiles[uri]!).profile.name).toBe("Demo Learner"));
  view.unmount(); publishScenario(null); view = render(<App />); await screen.findByText("Demo choices restored on this device.");
  expect(values().profile.name).toBe("Demo Learner"); expect(values().settings.highlight).toBe(false);
  expect(values().feedback.feeling).toBe("Happy"); expect(values().index).toBe(2);
  fireEvent.press(screen.getByText("Reset all"));
  await waitFor(() => expect(JSON.parse(mockFiles[uri]!).journey).toBeNull());
  expect(values().feedback).toEqual({}); expect(network).not.toHaveBeenCalled();
});

it("never loads demo choices for another role or live context", async () => {
  const view = render(<App allowed={false} />);
  expect(fs.getInfoAsync).not.toHaveBeenCalled();
  view.rerender(<App />); await screen.findByText("Demo choices stay on this device only.");
  fireEvent.press(screen.getByText("Edit")); await saved();
  const reads = jest.mocked(fs.readAsStringAsync).mock.calls.length;
  view.rerender(<App allowed={false} />);
  expect(screen.queryByTestId("values")).toBeNull();
  expect(fs.readAsStringAsync).toHaveBeenCalledTimes(reads);
});

it.each(["{broken", '{"version":0}', '{"version":1,"scope":"live"}'])("rejects corrupt or outdated data without inventing replacements: %s", async text => {
  mockFiles[uri] = text; render(<App />);
  await screen.findByText("Saved demo data could not be opened. Choose again or reset the demo.");
  expect(values().profile.name).toBe("Demo Learner"); expect(values().index).toBeNull();
  expect(mockFiles[uri]).toBe(text); expect(fs.writeAsStringAsync).not.toHaveBeenCalled();
});

it("rejects unsupported journey identities, private fields, invalid enums and unavailable storage", async () => {
  render(<App />); await screen.findByText("Demo choices stay on this device only.");
  fireEvent.press(screen.getByText("Edit")); await saved();
  const valid = JSON.parse(mockFiles[uri]!);
  for (const bad of [{ ...valid, journey: { ...valid.journey, digest: "changed" } }, { ...valid, journey: { index: 999, digest: "changed" } }, { ...valid, learnerId: "private" }, { ...valid, feedback: { feeling: "Invented" } }, { ...valid, settings: { ...valid.settings, font: "giant" } }]) expect(() => validateDemoData(bad)).toThrow();
  await expect(demoStorage(() => false).load()).rejects.toThrow();
  jest.mocked(fs.writeAsStringAsync).mockRejectedValueOnce(Error("private internal error"));
  fireEvent.press(screen.getByText("Reset settings"));
  await screen.findByText("Demo choices could not be saved. Try again.");
  expect(screen.queryByText("private internal error")).toBeNull();
});


it("requires confirmation before resetting demo data and offers an explicit settings save", async () => {
  const alert = jest.spyOn(Alert, "alert");
  render(<DeveloperTestBoundary enabled><PreviewSessionBoundary enabled><SupportSettingsScreen /></PreviewSessionBoundary></DeveloperTestBoundary>);
  await screen.findByText("Demo choices stay on this device only.");
  fireEvent.press(screen.getByRole("radio", { name: "Reading font size: Large" }));
  await saved();
  fireEvent.press(screen.getByRole("button", { name: "Save My Settings" }));
  await waitFor(() => expect(JSON.parse(mockFiles[uri]!).settings.font).toBe("large"));
  fireEvent.press(screen.getByRole("button", { name: "Reset Demo Data" }));
  expect(alert).toHaveBeenCalledTimes(1);
  expect(JSON.parse(mockFiles[uri]!).settings.font).toBe("large");
  expect(alert.mock.calls[0]![2]![0]!.style).toBe("cancel");
  act(() => alert.mock.calls[0]![2]![1]!.onPress!());
  await waitFor(() => expect(JSON.parse(mockFiles[uri]!).settings.font).toBe("comfortable"));
});

it("rejects oversized files and never reads device storage in release builds", async () => {
  mockFiles[uri] = "x".repeat(16_385);
  await expect(demoStorage(() => true).load()).rejects.toThrow();
  expect(fs.readAsStringAsync).not.toHaveBeenCalled();
  jest.clearAllMocks();
  jest.replaceProperty(globalThis as typeof globalThis & { __DEV__: boolean }, "__DEV__", false);
  await expect(demoStorage(() => true).load()).rejects.toThrow();
  expect(fs.getInfoAsync).not.toHaveBeenCalled();
});


it("restores an explicitly selected calculated artifact only with its validated source identity", async () => {
  const view = render(<App />); await screen.findByText("Demo choices stay on this device only.");
  fireEvent.press(screen.getByText("Select calculated result"));
  await waitFor(() => expect(JSON.parse(mockFiles[uri]!).journey.index).toBe(-1));
  const before = values(); view.unmount(); publishScenario(null);
  render(<App />); await screen.findByText("Demo choices restored on this device.");
  expect(values()).toEqual(before); expect(values().count).toBeGreaterThan(0);
  const data = JSON.parse(mockFiles[uri]!);
  expect(() => validateDemoData({ ...data, journey: { index: -1, digest: "outdated" } })).toThrow();
});
