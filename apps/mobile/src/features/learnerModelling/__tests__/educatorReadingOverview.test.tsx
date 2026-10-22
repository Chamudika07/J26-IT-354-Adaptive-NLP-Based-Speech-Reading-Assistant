import { fireEvent, render, screen, within } from "@testing-library/react-native";
import { StyleSheet } from "react-native";
import { EducatorReadingOverview } from "../components/EducatorReadingOverview";
import { RoleSwitcher } from "../components/RoleSwitcher";
import fixtures from "../preview/educatorScenarioContract.json";

it("shows prominent permitted measurements and an honest insufficient-evidence summary", () => {
  const p = fixtures[3]!.projection;
  const separate = jest.fn();
  render(<EducatorReadingOverview projection={p} selection="Scenario 3" onSeparate={separate} />);
  expect(screen.getAllByText("Sample Data")).toHaveLength(1);
  expect(screen.getByText("3 completed sessions")).toBeTruthy();
  expect(within(screen.getByTestId("teacher-reading_accuracy")).getByText("95")).toBeTruthy();
  expect(within(screen.getByTestId("teacher-reading_accuracy")).getByText("%")).toBeTruthy();
  expect(within(screen.getByTestId("teacher-reading_fluency_wpm")).getByText("96.77")).toBeTruthy();
  expect(within(screen.getByTestId("teacher-reading_fluency_wpm")).getByText("WPM")).toBeTruthy();
  expect(within(screen.getByTestId("teacher-hesitation_rate_per_word")).getByText("3")).toBeTruthy();
  expect(within(screen.getByTestId("teacher-hesitation_rate_per_word")).getByText("per 100 attempted words")).toBeTruthy();
  expect(screen.getByText("Not enough reading sessions to show a reliable trend yet.")).toBeTruthy();
  expect(screen.queryByText(/increased between|decreased between/)).toBeNull();
  expect(screen.getByRole("header", { name: "Support History" })).toBeTruthy();
  const support = p.support_mode_exposures[0]!;
  expect(screen.getByText(`Active reading: ${support.active_duration_ms / 1000} seconds · Total session time: ${support.total_duration_ms / 1000} seconds`)).toBeTruthy();
  expect(screen.queryByText(/experimentalEngagement|engine_version|longitudinal_calculation_version/)).toBeNull();
  expect(screen.queryByText(p.disclaimer)).toBeNull();
  fireEvent.press(screen.getByRole("button", { name: "About These Results" }));
  expect(screen.getByText(p.disclaimer)).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "View separate example" }));
  expect(separate).toHaveBeenCalledTimes(1);
});

it("uses the backend comparison flags and averages without claiming causation", () => {
  render(<EducatorReadingOverview projection={fixtures[6]!.projection} selection="Scenario 6" onSeparate={() => {}} />);
  for (const [label, direction] of [["Reading Accuracy", "increased"], ["Reading Speed", "increased"], ["Hesitation Frequency", "decreased"]]) {
    expect(screen.getByText(`${label} ${direction} between the comparison periods.`)).toBeTruthy();
  }
  expect(screen.getByText("Earlier average: 94 · Recent average: 96 %")).toBeTruthy();
  expect(screen.getByText("Earlier average: 91.6 · Recent average: 100 WPM")).toBeTruthy();
  expect(screen.queryByText(/improved|declined|getting better/i)).toBeNull();
});

it("does not invent measurements or support history for an empty period", () => {
  render(<EducatorReadingOverview projection={fixtures[0]!.projection} selection="Scenario 0" onSeparate={() => {}} />);
  expect(screen.getByText("0 completed sessions")).toBeTruthy();
  expect(screen.getByText("Accuracy, speed and hesitation frequency are not measured yet.")).toBeTruthy();
  expect(screen.getByText("No recorded support use yet.")).toBeTruthy();
  expect(screen.queryByText(/Active reading: 0/)).toBeNull();
});

it("keeps compact educator role controls accessible and leaves other role layouts intact", () => {
  const select = jest.fn();
  const view = render(<RoleSwitcher selectedRole="educator" onSelectRole={select} />);
  const educator = screen.getByRole("tab", { name: "Educator sample preview" });
  expect(StyleSheet.flatten(educator.props.style).minHeight).toBe(48);
  fireEvent.press(screen.getByRole("tab", { name: "Guardian sample preview" }));
  expect(select).toHaveBeenCalledWith("guardian");
  view.rerender(<RoleSwitcher selectedRole="guardian" onSelectRole={select} />);
  expect(StyleSheet.flatten(screen.getByRole("tab", { name: "Guardian sample preview" }).props.style).minHeight).toBe(56);
});
