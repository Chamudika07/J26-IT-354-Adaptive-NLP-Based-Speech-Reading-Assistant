import { usePp1Connection } from "./Pp1Connection";
import { createPp1Client } from "../data/pp1Client";
import { publishScenario, selectedScenarioId, scenarioId } from "./selectedScenario";
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { nativeTestStorage, SyntheticSessionInputError } from "./developerSessionStorage";
import { selectConnectedPreview, selectConnectedReplay, connectedReplayLength, type ConnectedArtifact } from "./connectedSessionPreview";
import { exportDeveloperSessions } from "./exportDeveloperSessions";
import type { TestSession } from "./developerSessions";

function useDeveloperState() {
  const connection = usePp1Connection();
  const source = connection ? "laptop" : "offline";
  const lastSavedRequest = useRef<number | undefined>(undefined);
  const [savedMessage, setSavedMessage] = useState("");
  const [calculationError, setCalculationError] = useState("");
  const [calculating, setCalculating] = useState(false);
  const request = useRef<AbortController | null>(null);
  const generation = useRef(0);
  const cancelCalculation = useCallback(() => { generation.current++; request.current?.abort(); request.current = null; setCalculating(false); }, []);
  useEffect(() => () => { generation.current++; request.current?.abort(); }, [connection]);

  const [initial] = useState(() => {
    const id = connection ? null : selectedScenarioId();
    if (!id) return { index: null as number | null, attempted: false, artifact: null as ConnectedArtifact | null };
    try {
      const index: unknown = JSON.parse(id)[0];
      if (typeof index !== "number") throw Error();
      const artifact = index === -1 ? selectConnectedPreview({ enabled: true, development: true, demoMode: true, role: "learner" }) : selectConnectedReplay({ index, development: true, demoMode: true, role: "learner" });
      if (!artifact || scenarioId(index, artifact) !== id) throw Error();
      return { index: index === -1 ? null : index, attempted: true, artifact };
    } catch { return { index: null, attempted: true, artifact: null }; }
  });
  const [replayIndex, setReplayIndex] = useState<number | null>(initial.index);
  const [connected, setConnected] = useState<{ attempted: boolean; artifact: ConnectedArtifact | null }>({ attempted: initial.attempted, artifact: initial.artifact });
  const [records, setRecords] = useState<TestSession[]>([]);
  const [selected, setSelected] = useState(false);
  const [asOf, setAsOf] = useState(Date.now);
  const [message, setMessage] = useState("Nothing loaded. Save or Load explicitly to view synthetic records.");
  const [busy, setBusy] = useState(false);
  const alive = useRef(true);
  const running = useRef(false);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const run = async (operation: "save" | "load" | "clear", record?: TestSession) => {
    if (running.current || !alive.current) return false;
    const storage = nativeTestStorage(() => alive.current);
    running.current = true; setBusy(true);
    setMessage("Checking developer device storage...");
    try {
      const file = operation === "save" && record ? await storage.save(record)
        : operation === "clear" ? await storage.clear() : await storage.load();
      if (!alive.current) return false;
      publishScenario(null); setConnected({ attempted: false, artifact: null }); setReplayIndex(null);
      setRecords(file.records); setSelected(operation !== "clear"); setAsOf(Date.now());
      setMessage(operation === "save" ? "Synthetic record saved and read back from device storage."
        : operation === "clear" ? "Synthetic records cleared from device storage."
        : `Loaded ${file.records.length} synthetic records from device storage.`);
      return true;
    } catch (error) {
      if (alive.current) {
        if (!(error instanceof SyntheticSessionInputError)) { publishScenario(null); setConnected({ attempted: false, artifact: null }); setReplayIndex(null); setRecords([]); setSelected(true); }
        setMessage(error instanceof Error ? error.message : "Synthetic storage unavailable.");
      }
      return false;
    } finally { running.current = false; if (alive.current) setBusy(false); }
  };
  const selectConnected = () => {
    if (!alive.current || running.current || !__DEV__) return;
    if (connection) return;
    cancelCalculation(); setCalculationError("");
    setReplayIndex(null);
    const artifact = selectConnectedPreview({ enabled: true, development: __DEV__, demoMode: true, role: "learner" });
    publishScenario(-1, artifact); setConnected({ attempted: true, artifact }); setSelected(false);
  };
  const replay = (index: number) => {
    if (!alive.current || running.current || !__DEV__) return;
    const artifact = selectConnectedReplay({ index, development: __DEV__, demoMode: true, role: "learner" });
    publishScenario(index, artifact); setReplayIndex(index); setConnected({ attempted: true, artifact }); setSelected(false);
  };
  const applyScenario = async (index: number) => {
    if (source === "offline") { replay(index); return true; }
    cancelCalculation();
    if (!connection) { setCalculationError("Sign in to use the laptop connection."); return false; }
    const version = generation.current;
    const controller = new AbortController(); request.current = controller;
    setCalculating(true); setCalculationError("");
    setConnected({ attempted: true, artifact: null });
    try {
      const result = await createPp1Client(connection)(index, controller.signal);
      if (generation.current !== version || controller.signal.aborted || !alive.current) return false;
      setConnected({ attempted: true, artifact: result.result }); setReplayIndex(index); setSelected(false);
      return true;
    } catch {
      if (generation.current === version && alive.current) setCalculationError("We could not get your sample results. Please retry.");
      return false;
    } finally { if (generation.current === version && alive.current) { setCalculating(false); request.current = null; } }
  };
  const savedProgress = async (index?: number) => {
    lastSavedRequest.current = index;
    cancelCalculation(); setCalculationError(""); setSavedMessage("");
    if (!connection || source !== "laptop") { setCalculationError("Sign in and open the PP1 Sample Journey."); return false; }
    const version = generation.current;
    const controller = new AbortController(); request.current = controller;
    setCalculating(true); setConnected({ attempted: true, artifact: null });
    try {
      const client = createPp1Client(connection);
      const result = index === undefined ? await client.readSaved(controller.signal) : await client.save(index, controller.signal);
      if (version !== generation.current || controller.signal.aborted || !alive.current) return false;
      setConnected({ attempted: true, artifact: result.result }); setReplayIndex(result.selectedSessionCount); setSelected(false);
      setSavedMessage(`Synthetic Sample Data: ${result.selectedSessionCount} saved sessions loaded from PostgreSQL.`);
      return true;
    } catch {
      if (version === generation.current && alive.current) setCalculationError("Connection problem. Save or refresh not confirmed. Please retry.");
      return false;
    } finally { if (version === generation.current && alive.current) { setCalculating(false); request.current = null; } }
  };
  const exportSaved = async () => {
    if (!alive.current || running.current) return false;
    running.current = true; setBusy(true);
    try { const result = await exportDeveloperSessions(() => alive.current); if (alive.current) setMessage(result); return alive.current; }
    catch { if (alive.current) setMessage("Sample export unavailable. Your saved inputs are unchanged. Try exporting again."); return false; }
    finally { running.current = false; if (alive.current) setBusy(false); }
  };
  return { savedMessage, savedProgress, source, connectedAvailable: Boolean(connection), retrySavedProgress: () => savedProgress(lastSavedRequest.current), applyScenario, calculationError, calculating, cancelCalculation, replayIndex, replayLength: connectedReplayLength, replay: (index: number) => { if (source === "laptop") { void savedProgress(index); } else replay(index); }, connected, selectConnected, exportSaved, records, selected, asOf, message, busy, run, returnToDemo: () => { cancelCalculation(); setCalculationError(""); publishScenario(null); setReplayIndex(null); setSelected(false); setConnected({ attempted: Boolean(connection), artifact: null }); } };
}
const Context = createContext<ReturnType<typeof useDeveloperState> | null>(null);
function Active({ children }: { children: ReactNode }) {
  const value = useDeveloperState();
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
/** Separate from temporary settings/feedback; re-entry always requires explicit Load. */
export function DeveloperTestBoundary({ enabled, children }: { enabled: boolean; children: ReactNode }) {
  const connection = usePp1Connection();
  return enabled && __DEV__ ? <Active key={connection ? `${connection.baseUrl}:${connection.session.scopeKey}` : "offline"}>{children}</Active> : <>{children}</>;
}
export const useDeveloperTest = () => useContext(Context);
