import { fireEvent, render, screen } from "@testing-library/react-native";
import { Alert, StyleSheet } from "react-native";
import { ConfirmJourneyReset, ReadingProgress } from "../components/ReadingProgress";
import { selectConnectedReplay } from "../preview/connectedSessionPreview";

it("shows missing measurements honestly and opens reading tips", () => {
  const tips = jest.fn();
  const empty = { label: "Latest", accuracy: null, speed: null, hesitation: null };
  render(<ReadingProgress rows={[]} latest={empty} period="Sample period" onTips={tips} />);
  expect(screen.getAllByText("Unavailable")).toHaveLength(3);
  expect(screen.getAllByText("No completed sessions yet.")).toHaveLength(3);
  expect(screen.getByText("Demo \u00b7 Fictional data")).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "View Reading Tips" }));
  expect(tips).toHaveBeenCalledTimes(1);
});

it("renders the validated prepared prefix with correct units and updates without replacing missing values", () => {
  const props = (index: number) => {
    const artifact = selectConnectedReplay({ index, development: true, demoMode: true, role: "learner" })!;
    const rows = artifact.history.map(r => ({ label: `S${r.sequence}`, accuracy: r.accuracy === null ? null : Number(r.accuracy) * 100, speed: r.wpm === null ? null : Number(r.wpm), hesitation: r.hesitation === null ? null : Number(r.hesitation) * 100 }));
    return { rows, latest: rows.at(-1) ?? { label: "Latest", accuracy: null, speed: null, hesitation: null }, period: "Sample period" };
  };
  const view = render(<ReadingProgress {...props(0)} />);
  expect(screen.queryByText(/S1.*Completed/)).toBeNull();
  view.rerender(<ReadingProgress {...props(1)} />);
  fireEvent.press(screen.getByRole("button", { name: "View Reading History" }));
  const first = props(1).rows[0]!;
  expect(screen.getByLabelText(`S1: ${Number(first.accuracy!.toFixed(2))} %`)).toBeTruthy();
  expect(screen.getByLabelText(`S1: ${Number(first.hesitation!.toFixed(2))} per 100 attempted words`)).toBeTruthy();
  expect(screen.getByText(/S1.*Completed/)).toBeTruthy();
  view.rerender(<ReadingProgress {...props(2)} />);
  expect(screen.getByText(/S2.*Completed/)).toBeTruthy();
  expect(screen.queryByText(/getting better/i)).toBeNull();
});


it("labels experimental engagement separately and does not invent unavailable interactions", () => {
  const empty = { label: "Latest", accuracy: null, speed: null, hesitation: null };
  const view = render(<ReadingProgress rows={[]} latest={empty} period="Sample period" completedCount={0} />);
  expect(screen.getByRole("header", { name: "My Reading Analytics" })).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "View Behaviour Details" }));
  expect(screen.getByText("0 completed sessions")).toBeTruthy();
  expect(screen.getByText("Reading time: Unavailable.")).toBeTruthy();
  expect(screen.getByText("Pauses and replays: Unavailable.")).toBeTruthy();
  expect(screen.getByText("Experimental engagement estimate: Unavailable.")).toBeTruthy();
  expect(screen.getByText("Keep reading to see your progress.")).toBeTruthy();
  view.rerender(<ReadingProgress rows={[]} latest={empty} period="Sample period" completedCount={2} engagement="0.75" />);
  expect(screen.getByText("Experimental engagement estimate: 0.75.")).toBeTruthy();
  expect(screen.getByText("This research estimate is not scientifically validated. It does not measure attention or ability.")).toBeTruthy();
});

it.each([0, 1, 3, 6])("preserves scenario %s chart values, order, scales and collapsed details", index => {
  const a = selectConnectedReplay({ index, development: true, demoMode: true, role: "learner" })!;
  const number = (v: string | null, scale = 1) => v === null ? null : Number(v) * scale;
  const rows = a.history.map(h => ({ label: `S${h.sequence}`, accuracy: number(h.accuracy, 100), speed: number(h.wpm), hesitation: number(h.hesitation, 100) }));
  const metric = (key: string, scale = 1) => number(a.metrics.find(m => m.metric_name === key)?.latest_value ?? null, scale);
  render(<ReadingProgress rows={rows} latest={{ label: "Latest", accuracy: metric("reading_accuracy", 100), speed: metric("reading_fluency_wpm"), hesitation: metric("hesitation_rate_per_word", 100) }} period="Validated sample period" completedCount={a.includedSessionCount} insufficientHistory={a.metrics.some(m => m.change_direction === "insufficient_evidence")} details={a.metrics.map(m => m.explanation)} />);
  expect(screen.getByRole("button", { name: "View Reading History" }).props.accessibilityState).toMatchObject({ expanded: false });
  expect(screen.getByRole("button", { name: "View Behaviour Details" }).props.accessibilityState).toMatchObject({ expanded: false });
  expect(screen.queryByText(/research estimate is not scientifically/)).toBeNull();
  expect(screen.queryByText(/S1.*Completed/)).toBeNull();
  for (const key of ["accuracy", "speed", "hesitation"] as const) {
    const max = key === "accuracy" ? 100 : Math.max(1, ...rows.map(r => r[key] ?? 0));
    rows.forEach((row, i) => {
      if (row[key] === null) expect(screen.queryByTestId(`bar-${key}-${i}`)).toBeNull();
      else expect(StyleSheet.flatten(screen.getByTestId(`bar-${key}-${i}`).props.style).height).toBe(`${row[key]! / max * 100}%`);
    });
  }
  fireEvent.press(screen.getByRole("button", { name: "View Reading History" }));
  rows.forEach(row => expect(screen.getByText(new RegExp(`${row.label}.*Completed`))).toBeTruthy());
  fireEvent.press(screen.getByRole("button", { name: "View Behaviour Details" }));
  expect(screen.getByText("Reading time: Unavailable.")).toBeTruthy();
  expect(screen.getByText("This research estimate is not scientifically validated. It does not measure attention or ability.")).toBeTruthy();
  if (a.metrics.length) fireEvent.press(screen.getByRole("button", { name: "About these results" }));
  for (const m of a.metrics) expect(screen.getAllByText(m.explanation).length).toBeGreaterThan(0);
});
it("keeps missing chart measurements absent instead of drawing zero bars", () => {
  const row = { label: "S1", accuracy: null, speed: 50, hesitation: null };
  render(<ReadingProgress rows={[row]} latest={row} period="Test" />);
  expect(screen.getByLabelText("S1: Unavailable %")).toBeTruthy();
  expect(screen.queryByTestId("bar-accuracy-0")).toBeNull();
  expect(screen.getByTestId("bar-speed-0")).toBeTruthy();
});
it("requires explicit confirmation before resetting the journey", () => {
  const onReset = jest.fn(); const alert = jest.spyOn(Alert, "alert");
  render(<ConfirmJourneyReset onReset={onReset} />);
  fireEvent.press(screen.getByRole("button", { name: "Reset Journey" }));
  expect(onReset).not.toHaveBeenCalled();
  const buttons = alert.mock.calls.at(-1)![2]!;
  expect(buttons.find(b => b.text === "Cancel")!.style).toBe("cancel");
  buttons.find(b => b.text === "Reset Journey")!.onPress!();
  expect(onReset).toHaveBeenCalledTimes(1); alert.mockRestore();
});
