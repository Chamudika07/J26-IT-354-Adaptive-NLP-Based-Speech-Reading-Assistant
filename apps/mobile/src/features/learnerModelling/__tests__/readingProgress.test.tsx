import { fireEvent, render, screen } from "@testing-library/react-native";
import { ReadingProgress } from "../components/ReadingProgress";
import { selectConnectedReplay } from "../preview/connectedSessionPreview";

it("shows missing measurements honestly and opens reading tips", () => {
  const tips = jest.fn();
  const empty = { label: "Latest", accuracy: null, speed: null, hesitation: null };
  render(<ReadingProgress rows={[]} latest={empty} period="Sample period" onTips={tips} />);
  expect(screen.getAllByText("Not measured")).toHaveLength(3);
  expect(screen.getAllByText("No completed sessions yet.")).toHaveLength(3);
  expect(screen.getByText("Sample Data")).toBeTruthy();
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
  expect(screen.getByRole("header", { name: "My Analytics" })).toBeTruthy();
  expect(screen.getByText("0 completed sessions")).toBeTruthy();
  expect(screen.getByText("Reading time: Not supplied.")).toBeTruthy();
  expect(screen.getByText("Pauses and replays: Not supplied.")).toBeTruthy();
  expect(screen.getByText("Experimental engagement estimate: Not available yet.")).toBeTruthy();
  expect(screen.getByText("Keep reading to see your progress.")).toBeTruthy();
  view.rerender(<ReadingProgress rows={[]} latest={empty} period="Sample period" completedCount={2} engagement="0.75" />);
  expect(screen.getByText("Experimental engagement estimate: 0.75.")).toBeTruthy();
  expect(screen.getByText("This research estimate is not scientifically validated. It does not measure attention or ability.")).toBeTruthy();
});
