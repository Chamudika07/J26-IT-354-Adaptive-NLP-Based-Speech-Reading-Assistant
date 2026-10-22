import { Platform } from "react-native";
import { testFile } from "./developerSessions";
import { nativeTestStorage } from "./developerSessionStorage";

/** Explicit local JSON export only. No upload or real learner data. */
export async function exportDeveloperSessions(allowed: () => boolean) {
  if (!__DEV__ || !allowed() || !["ios", "android"].includes(Platform.OS)) throw Error("Export requires a native developer Learner demo.");
  try {
    const saved = await nativeTestStorage(allowed).load();
    if (!allowed()) throw Error();
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const fs = require("expo-file-system/legacy") as typeof import("expo-file-system/legacy");
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const sharing = require("expo-sharing") as typeof import("expo-sharing");
    if (!fs.cacheDirectory?.startsWith("file://") || !await sharing.isAvailableAsync() || !allowed()) throw Error();
    const uri = fs.cacheDirectory + "readbuddy-component4-sample-sessions.json";
    await fs.writeAsStringAsync(uri, JSON.stringify(testFile(saved.records), null, 2));
    if (!allowed()) throw Error();
    await sharing.shareAsync(uri, { mimeType: "application/json", UTI: "public.json", dialogTitle: "Export synthetic sample sessions" });
    return "Export share sheet closed. Saving or cancelling is handled by your device; no exported copy is confirmed.";
  } catch { throw Error("Synthetic export unavailable. Check saved records and native file sharing."); }
}
