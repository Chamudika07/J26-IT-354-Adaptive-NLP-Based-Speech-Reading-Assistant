import { fireEvent, render, screen } from "@testing-library/react-native";
import App from "../../../../App";
import { selectConnectedReplay } from "../preview/connectedSessionPreview";
import { publishScenario, scenarioId } from "../preview/selectedScenario";
import { buildEducatorReport } from "../export/educatorReports";
import { buildLocalAiReportHtml } from "../export/localAiPdf";
import aiSnapshot from "../preview/localReportSnapshot.json";

it("rehearses PP1 with changing backend evidence, all roles and saved reports without network", async () => {
  publishScenario(null);
  delete process.env.EXPO_PUBLIC_COMPONENT4_DEVELOPER_TOOLS;
  const network = jest.spyOn(globalThis, "fetch").mockRejectedValue(new Error("PP1 must work offline"));
  const button = (name: string) => fireEvent.press(screen.getByRole("button", { name }));
  try {
    render(<App />);
    await screen.findByText("Hi, Reader!");
    button("Reading Results");
    fireEvent.press(screen.getByRole("radio", { name: "Sample scenario: Sample 6" }));
    button("Update My Progress");
    const artifact = selectConnectedReplay({ index: 6, development: true, demoMode: true, role: "learner" })!;
    expect(artifact.history).toHaveLength(6);
    for (const key of ["accuracy", "wpm", "hesitation"] as const) expect(new Set(artifact.history.map(h => h[key])).size).toBeGreaterThan(1);
    expect(artifact.metrics.map(m => m.change_direction)).toEqual(["increased", "increased", "decreased"]);
    expect(screen.getByRole("header", { name: "My Profile" })).toBeTruthy();
    button("Next: My Analytics");
    for (const title of ["Reading Performance", "Reading Behaviour", "Reading Progress"]) expect(screen.getByRole("header", { name: title })).toBeTruthy();
    expect(screen.getByText(/S6.*Completed/)).toBeTruthy();
    expect(screen.getByText("This research estimate is not scientifically validated. It does not measure attention or ability.")).toBeTruthy();
    button("View Reading Tips");
    expect(screen.getByText(artifact.recommendation!.action)).toBeTruthy();
    button("Why This Tip?");
    expect(screen.getByText("ADVISORY ONLY")).toBeTruthy();
    button("Next: My Reading Report");
    button("Read Current Summary");
    for (const statement of artifact.reportStatements) expect(screen.getByText(statement)).toBeTruthy();
    button("Open Saved AI Report");
    expect(screen.getByText("Created earlier using sample reading data.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Download AI Report PDF" })).toBeTruthy();
    const html = buildLocalAiReportHtml(aiSnapshot, { development: true, demoMode: true, role: "learner", enabled: true });
    expect(html).toContain("AI Progress Report");
    expect(html).not.toContain("break-before: page");
    fireEvent.press(screen.getByRole("tab", { name: "Guardian sample preview" }));
    await screen.findByText("Parent Dashboard");
    expect(screen.getByText("Selected reading scenario: Sample 6")).toBeTruthy();
    expect(screen.queryByText("ADVISORY ONLY")).toBeNull();
    fireEvent.press(screen.getByRole("tab", { name: "Educator sample preview" }));
    await screen.findByText("Teacher Dashboard");
    button("View Alex Storybook");
    expect(screen.getByText(/^Scenario 6/)).toBeTruthy();
    for (const student of [0, 1, 2, null]) {
      const pdf = buildEducatorReport({ development: true, demoMode: true, role: "educator", scenarioId: scenarioId(6, artifact), student });
      expect(pdf.html).toContain("Sample Data");
      expect(pdf.html).toContain("not AI-generated");
      expect(pdf.html).not.toMatch(/https?:|page-break-before:always/);
    }
    expect(network).not.toHaveBeenCalled();
  } finally { network.mockRestore(); publishScenario(null); }
});
