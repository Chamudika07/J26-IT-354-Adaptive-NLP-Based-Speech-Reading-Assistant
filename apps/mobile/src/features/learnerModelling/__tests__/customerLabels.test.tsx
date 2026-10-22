import { fireEvent, render, screen } from "@testing-library/react-native";
import App from "../../../../App";

it("shows one small sample disclosure and keeps developer tools out of normal navigation", async () => {
  delete process.env.EXPO_PUBLIC_COMPONENT4_DEVELOPER_TOOLS;
  render(<App />); await screen.findByText("Hi, Reader!");
  for (const title of ["My Profile", "My Reading Analytics", "My Reading Tips", "Support Settings", "Session Feedback", "My Reading Report"]) {
    const tab = ({ "My Profile": "Profile", "My Reading Analytics": "Analytics", "My Reading Tips": "Suggestions" } as Record<string, string>)[title];
    fireEvent.press(tab ? screen.getByRole("tab", { name: `${tab} learner view` }) : screen.getByRole("button", { name: `Open ${title}` }));
    expect(screen.getByRole("header", { name: title })).toBeTruthy();
    expect(screen.getAllByText(title === "My Reading Analytics" ? "Demo \u00b7 Fictional data" : "Sample Data")).toHaveLength(1);
    expect(screen.queryByRole("button", { name: "Developer Details" })).toBeNull();
    expect(screen.queryByRole("button", { name: /Export.*JSON|Select connected backend/ })).toBeNull();
    if (title === "My Reading Report") {
      fireEvent.press(screen.getByRole("button", { name: "Open saved AI report" }));
      expect(screen.getByText("Created earlier using sample reading data.")).toBeTruthy();
      expect(screen.getAllByText("Sample Data")).toHaveLength(1);
      expect(screen.queryByRole("button", { name: "Developer Details" })).toBeNull();
      expect(screen.getByRole("button", { name: "Download AI Report PDF" })).toBeTruthy();
    }
    fireEvent.press(screen.getByRole("button", { name: "Back to reading Home" }));
  }
});
