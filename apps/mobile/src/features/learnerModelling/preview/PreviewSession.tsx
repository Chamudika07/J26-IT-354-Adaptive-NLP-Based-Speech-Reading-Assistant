import { createContext, useContext, useState, useEffect, useRef, type ReactNode } from "react";
import { demoStorage, type DemoData } from "./demoPersistence";
import { useDeveloperTest } from "./DeveloperTestSession";

export type PreviewSettings = Readonly<{
  font: "comfortable" | "large" | "extraLarge";
  spacing: "comfortable" | "wide";
  highlight: boolean;
  audio: boolean;
}>;
export type PreviewFeedback = Readonly<{
  feeling?: string;
  difficulty?: string;
  continueReading?: string;
}>;
const defaults: PreviewSettings = Object.freeze({ font: "comfortable", spacing: "comfortable", highlight: false, audio: false });
export const DEFAULT_DEMO_PROFILE: Readonly<{ name: string; avatar: "book" | "fox" | "owl" }> = Object.freeze({ name: "Demo Learner", avatar: "book" as "book" | "fox" | "owl" });
function useDraftState() {
  const [profile, updateProfile] = useState(DEFAULT_DEMO_PROFILE);
  const [settings, updateSettings] = useState<PreviewSettings>(defaults);
  const [feedback, updateFeedback] = useState<PreviewFeedback>({});
  const [ready, setReady] = useState(false);
  const [storageMessage, setStorageMessage] = useState("Loading this device's demo choices...");
  const alive = useRef(true);
  const dirty = useRef(false);
  const previousJourney = useRef<number | null>(null);
  const queue = useRef(Promise.resolve());
  const journey = useDeveloperTest();
  const journeyRef = useRef(journey);
  useEffect(() => { journeyRef.current = journey; }, [journey]);
  useEffect(() => {
    alive.current = true;
    const storage = demoStorage(() => alive.current);
    void storage.load().then(data => {
      if (!alive.current) return;
      if (data && !dirty.current) {
        updateProfile(data.profile); updateSettings(data.settings); updateFeedback(data.feedback);
        if (!journeyRef.current?.connected.attempted) {
          previousJourney.current = data.journey?.index ?? null;
          if (data.journey?.index === -1) journeyRef.current?.selectConnected();
          else if (data.journey) journeyRef.current?.replay(data.journey.index);
        }
      }
      setStorageMessage(data ? "Demo choices restored on this device." : "Demo choices stay on this device only.");
    }).catch(() => {
      if (alive.current) setStorageMessage("Saved demo data could not be opened. Choose again or reset the demo.");
    }).finally(() => { if (alive.current) setReady(true); });
    return () => { alive.current = false; };
  }, []);
  const index = journey?.connected.artifact ? journey.replayIndex ?? -1 : null;
  const data: DemoData = { version: 1, scope: "component4-learner-demo", profile, settings, feedback,
    journey: index === null || !journey?.connected.artifact ? null : { index, digest: journey.connected.artifact.sourceDigest } };
  const latest = useRef(data);
  useEffect(() => { latest.current = data; });
  const save = () => {
    const next = latest.current;
    queue.current = queue.current.catch(() => undefined).then(async () => {
      if (!alive.current) return;
      try {
        await demoStorage(() => alive.current).save(next);
        if (alive.current) setStorageMessage("Demo choices saved on this device. Not a real learner record.");
      } catch { if (alive.current) setStorageMessage("Demo choices could not be saved. Try again."); }
    });
    return queue.current;
  };
  useEffect(() => {
    if (!ready) return;
    if (previousJourney.current !== index) { dirty.current = true; previousJourney.current = index; }
    if (dirty.current) void save();
    // Values only: storage messages and provider object identities must not cause writes.
  }, [ready, profile, settings, feedback, index]);
  const setProfile: typeof updateProfile = value => { dirty.current = true; updateProfile(value); };
  const setSettings: typeof updateSettings = value => { dirty.current = true; updateSettings(value); };
  const setFeedback: typeof updateFeedback = value => { dirty.current = true; updateFeedback(value); };
  const resetDemo = () => {
    dirty.current = true; updateProfile(DEFAULT_DEMO_PROFILE); updateSettings(defaults); updateFeedback({});
    journeyRef.current?.returnToDemo();
  };
  return { profile, setProfile, resetProfile: () => setProfile(DEFAULT_DEMO_PROFILE), settings, setSettings, feedback, setFeedback,
    resetSettings: () => setSettings({ ...defaults }), clearFeedback: () => setFeedback({}),
    resetDemo, saveSettings: save, storageMessage, storageReady: ready };
}

const PreviewSession = createContext<ReturnType<typeof useDraftState> | null>(null);
function ActivePreviewSession({ children }: { children: ReactNode }) {
  const drafts = useDraftState();
  return <PreviewSession.Provider value={drafts}>{children}</PreviewSession.Provider>;
}
/** Only the Learner demo can hydrate local sample choices. Other roles and live mode unmount it. */
export function PreviewSessionBoundary({ enabled, children }: { enabled: boolean; children: ReactNode }) {
  return enabled ? <ActivePreviewSession>{children}</ActivePreviewSession> : <>{children}</>;
}
export function usePreviewSession() {
  const session = useContext(PreviewSession);
  if (!session) throw new Error("Temporary choices require an active Learner demo session.");
  return session;
}

export function useOptionalPreviewSession() { return useContext(PreviewSession); }
