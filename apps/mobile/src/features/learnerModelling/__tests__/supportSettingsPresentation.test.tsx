import { act, fireEvent, render, screen } from "@testing-library/react-native";
import { Alert, Dimensions, StyleSheet } from "react-native";
import { PreviewSessionBoundary } from "../preview/PreviewSession";
import { SupportSettingsScreen } from "../screens/SupportSettingsScreen";

it("maps compact labels to existing appearance settings and keeps audio a preference", () => {
  render(<PreviewSessionBoundary enabled><SupportSettingsScreen /></PreviewSessionBoundary>);
  expect(screen.getByRole("header", { name: "Reading Settings" })).toBeTruthy();
  expect(screen.getAllByText("Demo \u00b7 Fictional data")).toHaveLength(1);
  expect(screen.queryByText("Sample Data")).toBeNull();
  const preview = () => StyleSheet.flatten(screen.getByTestId("support-sample-text").props.style);
  for (const [label, size] of [["Normal", 18], ["Large", 22], ["XL", 28]] as const) {
    const choice = screen.getByRole("radio", { name: `Reading font size: ${label}` });
    expect(StyleSheet.flatten(choice.props.style).minHeight).toBeGreaterThanOrEqual(44);
    fireEvent.press(choice);
    expect(preview().fontSize).toBe(size);
    expect(screen.getByRole("radio", { name: `Reading font size: ${label}` }).props.accessibilityState.checked).toBe(true);
  }
  fireEvent.press(screen.getByRole("radio", { name: "Line spacing: Wide" }));
  expect(preview().lineHeight).toBe(56);
  fireEvent.press(screen.getByRole("radio", { name: "Line spacing: Normal" }));
  expect(preview().lineHeight).toBe(28 * 1.6);
  fireEvent(screen.getByRole("switch", { name: "Text highlighting preference" }), "valueChange", true);
  expect(screen.getByRole("switch", { name: "Text highlighting preference" }).props.value).toBe(true);
  fireEvent(screen.getByRole("switch", { name: "Audio-support preference" }), "valueChange", true);
  expect(screen.getByRole("switch", { name: "Audio-support preference" }).props.value).toBe(true);
  expect(screen.getByText("Audio playback is not connected.")).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "Reset Settings" }));
  expect(preview().fontSize).toBe(18);
  expect(screen.getByRole("switch", { name: "Audio-support preference" }).props.value).toBe(false);
});
it("does not reset demo choices until the destructive confirmation is accepted", () => {
  const alert = jest.spyOn(Alert, "alert").mockImplementation(() => {});
  try {
    render(<PreviewSessionBoundary enabled><SupportSettingsScreen /></PreviewSessionBoundary>);
    fireEvent.press(screen.getByRole("radio", { name: "Reading font size: XL" }));
    for (const name of ["Save My Settings", "Reset Settings", "Reset Demo Data"]) expect(StyleSheet.flatten(screen.getByRole("button", { name }).props.style).minHeight).toBeGreaterThanOrEqual(44);
    fireEvent.press(screen.getByRole("button", { name: "Reset Demo Data" }));
    expect(screen.getByRole("radio", { name: "Reading font size: XL" }).props.accessibilityState.checked).toBe(true);
    expect(alert.mock.calls[0]![2]![0]!.style).toBe("cancel");
    act(() => alert.mock.calls[0]![2]![1]!.onPress!());
    expect(screen.getByRole("radio", { name: "Reading font size: Normal" }).props.accessibilityState.checked).toBe(true);
  } finally { alert.mockRestore(); }
});

it("stacks selections for larger text on a small phone without fixed control heights", () => {
  const original = { window: Dimensions.get("window"), screen: Dimensions.get("screen") };
  Dimensions.set({ window: { width: 320, height: 568, scale: 2, fontScale: 2 } });
  const view = render(<PreviewSessionBoundary enabled><SupportSettingsScreen /></PreviewSessionBoundary>);
  try {
    for (const label of ["Reading font size: Normal", "Reading font size: Large", "Reading font size: XL", "Line spacing: Normal", "Line spacing: Wide"]) {
      const style = StyleSheet.flatten(screen.getByRole("radio", { name: label }).props.style);
      expect(style.flexBasis).toBe("100%");
      expect(style.minHeight).toBeGreaterThanOrEqual(44);
      expect(style.height).toBeUndefined();
    }
  } finally { view.unmount(); act(() => Dimensions.set(original)); }
});
