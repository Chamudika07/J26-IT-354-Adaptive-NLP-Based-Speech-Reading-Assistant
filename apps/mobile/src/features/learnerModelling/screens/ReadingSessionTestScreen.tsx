import { ReadingResultsScenarios } from "../components/ReadingResultsScenarios";
import { developerToolsEnabled } from "../preview/developerTools";
import { useState } from "react";
import { Pressable, Text, TextInput, View } from "react-native";
import { LocalPreviewLayout } from "../components/LocalPreviewLayout";
import { reportStyles } from "../components/LearnerReportLayout";
import { PreviewChoiceGroup } from "../components/PreviewChoiceGroup";
import { useDeveloperTest } from "../preview/DeveloperTestSession";
import { tasks, tiers, modes, completions, validateTestSession } from "../preview/developerSessions";

export function newTestInput() {
  return { id: "00000000-0000-4000-8000-000000000001", start: new Date(Date.now()-60000).toISOString(), end: new Date().toISOString(),
    attempted: "100", correct: "90", target: "100", activeMs: "60000", totalMs: "60000", hesitations: "", pauseCount: "", pauseMs: "", replayCount: "", completion: "completed", task: "independent_reading", tier: "intermediate", mode: "adaptive" };
}
const labels = { id: "Synthetic session UUID", start: "Start UTC (ISO timestamp)", end: "End UTC (ISO timestamp)", attempted: "Words attempted", correct: "Words correct", target: "Target word count", activeMs: "Active duration (milliseconds)", totalMs: "Total duration (milliseconds)", hesitations: "Hesitation count (blank = missing)", pauseCount: "Pause count (blank = missing)", pauseMs: "Total pause duration (milliseconds; blank = missing)", replayCount: "Replay count (blank = missing)" } as const;
export function ReadingSessionTestScreen({ onNavigate }: { onNavigate?: (destination: "home" | "progress" | "profile") => void } = {}) {
  const session = useDeveloperTest();
  const [input, setInput] = useState(newTestInput);
  const [details, setDetails] = useState(false);
  const [error, setError] = useState("");
  if (!session || !__DEV__) return <Text>Developer Learner demo only.</Text>;
  if (!developerToolsEnabled()) return <LocalPreviewLayout title="Reading Results" disclosure="Choose sample reading measurements"
    introduction="">
    <ReadingResultsScenarios onApplied={() => onNavigate?.("profile")} />
  </LocalPreviewLayout>;
  const save = async (calculate = false) => {
    try {
      const number = (value: string) => /^\d+$/.test(value) ? Number(value) : NaN;
      const record = validateTestSession({ ...input, attempted: number(input.attempted), correct: number(input.correct), target: number(input.target), activeMs: number(input.activeMs), totalMs: number(input.totalMs), hesitations: input.hesitations === "" ? null : number(input.hesitations), pauseCount: input.pauseCount === "" ? null : number(input.pauseCount), pauseMs: input.pauseMs === "" ? null : number(input.pauseMs), replayCount: input.replayCount === "" ? null : number(input.replayCount) });
      setError("");
      if (await session.run("save", record) && calculate) {
        const exported = await session.exportSaved();
        setError(exported ? "Next: save the shared file and calculate it on your laptop. No phone results have been calculated yet." : "Your inputs are saved, but sharing did not open. Try Calculate My Results again.");
      }
    } catch { setError("Invalid input. Use a UUID, valid UTC dates and non-negative whole counts/durations. Correct words cannot exceed attempted words; active time cannot exceed total time."); }
  };
  return <LocalPreviewLayout title="Try a Reading Session" disclosure="Developer synthetic test data — not a real learner record."
    introduction="Explore prepared reading samples or try your own sample inputs. Never enter personal data. Saved AI reports do not update.">
    <ReadingResultsScenarios onApplied={() => onNavigate?.("profile")} />
    <View style={reportStyles.card}>
      <Text accessibilityRole="header" style={reportStyles.heading}>Your sample reading results</Text>
      <Text style={reportStyles.body}>1. Enter your results below. 2. Calculate on your laptop. 3. Open the returned results.</Text>
      <Text style={reportStyles.body}>{session.records.length} saved sample inputs. They are not calculated results.</Text>
      <Pressable accessibilityRole="button" disabled={session.busy} accessibilityState={{ disabled: session.busy }} onPress={() => { session.selectConnected(); onNavigate?.("home"); }} style={reportStyles.previewLink}><Text style={reportStyles.body}>Open calculated sample results</Text></Pressable>
      <Text style={reportStyles.body}>Only open after importing your file on the laptop and reloading this app. Otherwise, this shows the separate bundled example.</Text>
    </View>
    <View style={reportStyles.card}>
      <Text style={reportStyles.heading}>Demo Reading Journey</Text>
      <Text style={reportStyles.body}>Explore reading results, progress, suggestions and report preparation using prepared samples. Your form inputs below are separate.</Text>
      <Pressable accessibilityRole="button" disabled={session.busy} accessibilityState={{ disabled: session.busy }} onPress={() => { session.replay(0); onNavigate?.("home"); }} style={reportStyles.primaryAction}><Text style={reportStyles.primaryLabel}>Start Demo Reading Journey</Text></Pressable>
    </View>
    <View style={reportStyles.card}>
      <Pressable accessibilityRole="button" accessibilityLabel={details ? "Hide Developer Details" : "Developer Details"} accessibilityState={{ expanded: details }} onPress={() => setDetails(!details)} style={reportStyles.previewLink}><Text style={reportStyles.body}>{details ? "Hide Developer Details" : "Developer Details"}</Text></Pressable>
      {Object.entries(labels).filter(([field]) => details || !["id", "start", "end"].includes(field)).map(([field, label]) => <View key={field}>
        <Text style={reportStyles.body}>{label}</Text>
        <TextInput accessibilityLabel={label} value={input[field as keyof typeof labels]} editable={!session.busy} autoCapitalize="none" autoCorrect={false}
          style={[reportStyles.previewLink, { borderWidth: 1, fontSize: 16 }]} onChangeText={(value) => setInput((old) => ({ ...old, [field]: value }))} />
      </View>)}
      <PreviewChoiceGroup label="Session completion" choices={completions.map((value) => ({ value, label: value === "completed" ? "Finished" : value === "abandoned" ? "Stopped early" : "Interrupted" }))} selected={input.completion} onSelect={(completion) => setInput((old) => ({ ...old, completion }))} />
      <PreviewChoiceGroup label="Task context" choices={tasks.map((value) => ({ value, label: value.replaceAll("_", " ") }))} selected={input.task} onSelect={(task) => setInput((old) => ({ ...old, task }))} />
      <PreviewChoiceGroup label="Difficulty context" choices={tiers.map((value) => ({ value, label: value }))} selected={input.tier} onSelect={(tier) => setInput((old) => ({ ...old, tier }))} />
      <PreviewChoiceGroup label="Support context" choices={modes.map((value) => ({ value, label: value.replaceAll("_", " ") }))} selected={input.mode} onSelect={(mode) => setInput((old) => ({ ...old, mode }))} />
      <Text style={reportStyles.body}>Custom inputs need export and computer calculation before analytics can update. Save is device-local; Load restores records after reopening. These are sample inputs, not verified reading measurements.</Text>
      <Text style={reportStyles.body}>Hesitations are simulated pause events of at least 2.5 seconds. Blank means missing, not zero. Pause and replay counts may also be missing. Total pause duration cannot exceed total duration. Completion describes only this simulated session.</Text>
      <Pressable accessibilityRole="button" disabled={session.busy} accessibilityState={{ disabled: session.busy }} onPress={() => void save(true)} style={reportStyles.primaryAction}><Text style={reportStyles.primaryLabel}>Calculate My Results</Text></Pressable>
      <Text style={reportStyles.body}>Laptop needed. This saves your inputs and opens sharing; it does not calculate on this phone.</Text>
      <Pressable accessibilityRole="button" onPress={() => {
        const next = Math.max(0, ...session.records.map((r) => Number.parseInt(r.id.slice(-12), 16))) + 1;
        setInput({ ...newTestInput(), id: `00000000-0000-4000-8000-${next.toString(16).padStart(12, "0")}` });
        setError("New sample input ready. Previously stored samples are unchanged.");
      }} style={reportStyles.previewLink}><Text style={reportStyles.body}>New sample session</Text></Pressable>
      {error ? <Text accessibilityRole="alert" style={reportStyles.body}>{error}</Text> : null}
      <Text accessibilityLiveRegion="polite" style={reportStyles.body}>{session.message}</Text>
      {[["Save", () => { void save(); }], ["Load", () => { setError(""); void session.run("load"); }], ["Clear", () => { setError(""); void session.run("clear"); }], ["Reset input", () => { setInput(newTestInput()); setError("Input reset only. Stored records are unchanged. Use a new UUID for each session."); }]] .map(([label, action]) => <Pressable key={label as string} accessibilityRole="button" accessibilityLabel={label as string} disabled={session.busy} accessibilityState={{ disabled: session.busy }} onPress={action as () => void} style={reportStyles.previewLink}><Text style={reportStyles.body}>{label as string}</Text></Pressable>)}
      {details ? <>
      <Pressable accessibilityRole="button" disabled={session.busy} accessibilityState={{ disabled: session.busy }} onPress={() => void session.exportSaved()} style={reportStyles.previewLink}><Text style={reportStyles.body}>Export saved sample sessions</Text></Pressable>

      <Text selectable style={reportStyles.body}>On your computer, from apps/backend: uv run --frozen python -m app.modules.learner_modelling.connected_demo --development-synthetic-only --input PATH_TO_EXPORTED_JSON --derive-window-context</Text>
      <Text style={reportStyles.body}>Then reload Expo and select connected backend preview. Automatic window/context selection requires a nonempty file with one shared context; mixed contexts need explicit developer filters.</Text>
      <Text style={reportStyles.body}>Instant offline replay uses only the prepared sample file, not values in this form. Add one prepared session at a time to see actual precomputed backend results. Custom inputs require Export, computer calculation and reload.</Text>
      <Pressable accessibilityRole="button" disabled={session.busy} accessibilityState={{ disabled: session.busy }} onPress={session.selectConnected} style={reportStyles.previewLink}><Text style={reportStyles.body}>Select connected backend preview</Text></Pressable>
      <Text style={reportStyles.body}>Export saved records to a local file, run the offline backend importer on your computer, reload Expo, then explicitly select its bundled result. The bundled example uses separate January sample sessions until you import your own file. This never regenerates the Qwen3 report.</Text>
      <Text style={reportStyles.body}>Save adds one record (maximum 100). Exact retries keep one observation; conflicting UUIDs are rejected. Clear deletes this developer file only. Reset input never deletes stored records. App removal or clearing Expo Go data can delete the file.</Text>
      </> : null}
    </View>
  </LocalPreviewLayout>;
}
// This simulator is intentionally not a ReadingSessionIngest API payload.
