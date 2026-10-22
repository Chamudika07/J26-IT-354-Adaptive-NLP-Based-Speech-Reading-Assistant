import { fireEvent, render, screen } from "@testing-library/react-native";
import { StyleSheet } from "react-native";
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
