import { Platform } from "react-native";
import { selectConnectedReplay, selectConnectedPreview } from "./connectedSessionPreview";
import type { PreviewSettings, PreviewFeedback } from "./PreviewSession";

export type DemoData = {
  version: 1; scope: "component4-learner-demo";
  profile: { name: string; avatar: "book" | "fox" | "owl" };
  settings: PreviewSettings; feedback: PreviewFeedback;
  journey: { index: number; digest: string } | null;
};
let pending: Promise<void> = Promise.resolve();
const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);
const keys = (v: Record<string, unknown>, allowed: string[]) => Object.keys(v).every(k => allowed.includes(k));
export function validateDemoData(value: unknown): DemoData {
  if (!object(value) || !keys(value, ["version", "scope", "profile", "settings", "feedback", "journey"]) || value.version !== 1 || value.scope !== "component4-learner-demo") throw Error("Invalid demo data");
  const { profile: p, settings: s, feedback: f, journey: j } = value;
  if (!object(p) || !keys(p, ["name", "avatar"]) || typeof p.name !== "string" || p.name !== p.name.trim() || !p.name.length || p.name.length > 32 || /[\u0000-\u001f\u007f]/.test(p.name) || typeof p.avatar !== "string" || !["book", "fox", "owl"].includes(p.avatar)) throw Error("Invalid demo profile");
  if (!object(s) || !keys(s, ["font", "spacing", "highlight", "audio"]) || typeof s.font !== "string" || !["comfortable", "large", "extraLarge"].includes(s.font) || typeof s.spacing !== "string" || !["comfortable", "wide"].includes(s.spacing) || typeof s.highlight !== "boolean" || typeof s.audio !== "boolean") throw Error("Invalid demo settings");
  if (!object(f) || !keys(f, ["feeling", "difficulty", "continueReading"])) throw Error("Invalid demo feedback");
  for (const [key, choices] of Object.entries({ feeling: ["Happy", "Unsure", "Tired"], difficulty: ["Easy", "Okay", "Difficult"], continueReading: ["Yes", "Maybe later", "No"] })) {
    if (key in f && (typeof f[key] !== "string" || !choices.includes(f[key]))) throw Error("Invalid demo feedback");
  }
  if (j !== null) {
    if (!object(j) || !keys(j, ["index", "digest"]) || !Number.isInteger(j.index)) throw Error("Invalid demo journey");
    const sample = j.index === -1
      ? selectConnectedPreview({ enabled: true, development: true, demoMode: true, role: "learner" })
      : selectConnectedReplay({ index: j.index as number, development: true, demoMode: true, role: "learner" });
    if (!sample || sample.sourceDigest !== j.digest) throw Error("Outdated demo journey");
  }
  return JSON.parse(JSON.stringify(value)) as DemoData;
}

// Separate from custom session files, AI snapshots and all production providers.
// All access is explicitly guarded by the mounted Learner demo boundary.
export function demoStorage(allowed: () => boolean) {
  const guard = () => { if (!__DEV__ || !allowed() || !["ios", "android"].includes(Platform.OS)) throw Error("Demo storage unavailable"); };
  const file = () => {
    guard();
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const fs = require("expo-file-system/legacy") as typeof import("expo-file-system/legacy");
    if (!fs.documentDirectory?.startsWith("file://")) throw Error("Demo storage unavailable");
    return { fs, uri: fs.documentDirectory + "readbuddy-component4-learner-demo-v1.json" };
  };
  return {
    async load(): Promise<DemoData | null> {
      guard(); await pending.catch(() => undefined);
      const { fs, uri } = file(); const info = await fs.getInfoAsync(uri); guard();
      if (!info.exists) return null;
      if (info.isDirectory || info.size > 16_384) throw Error("Invalid demo file");
      const text = await fs.readAsStringAsync(uri); guard();
      if (text.length > 16_384) throw Error("Invalid demo file");
      return validateDemoData(JSON.parse(text));
    },
    async save(value: DemoData) {
      const text = JSON.stringify(validateDemoData(value));
      pending = pending.catch(() => undefined).then(async () => {
        const { fs, uri } = file(); await fs.writeAsStringAsync(uri, text); guard();
        if (await fs.readAsStringAsync(uri) !== text) throw Error("Save unconfirmed"); guard();
      });
      await pending;
    },
  };
}
