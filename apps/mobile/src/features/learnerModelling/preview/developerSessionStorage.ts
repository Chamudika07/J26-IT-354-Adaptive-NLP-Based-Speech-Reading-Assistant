import { Platform } from "react-native";

import { testFile, validateTestFile, validateTestSession, type TestFile, type TestSession } from "./developerSessions";

export class SyntheticSessionInputError extends Error {}

export interface TestStorageIO { read(): Promise<string | null>; write(text: string): Promise<void>; clear(): Promise<void> }
export function developerTestStorage(io: TestStorageIO, allowed: () => boolean) {
  const guard = () => { if (!allowed()) throw Error("Developer Learner demo only."); };
  const load = async (): Promise<TestFile> => {
    guard();
    try {
      const text = await io.read(); guard();
      if (text !== null && text.length > 100_000) throw Error();
      return text === null ? testFile([]) : validateTestFile(JSON.parse(text));
    } catch { throw Error("Cannot load synthetic records: storage unavailable or invalid. Clear to recover."); }
  };
  return { load, async save(record: TestSession) {
    guard();
    let valid: TestSession;
    try { valid = validateTestSession(record); } catch { throw new SyntheticSessionInputError("Invalid synthetic input. Previous saved data is unchanged."); }
    const file = await load(); guard();
    const existing = file.records.find((r) => r.id === valid.id);
    if (existing) {
      if (Object.keys(valid).every((key) => existing[key as keyof TestSession] === valid[key as keyof TestSession])) return file;
      throw new SyntheticSessionInputError("Duplicate synthetic session ID with conflicting measurements. Previous saved data is unchanged.");
    }
    const next = testFile([...file.records, valid]);
    try {
      await io.write(JSON.stringify(next)); guard();
      const confirmed = await load();
      if (JSON.stringify(confirmed) !== JSON.stringify(next)) throw Error();
      return confirmed;
    } catch { throw Error("Save could not be confirmed. Load to check device storage."); }
  }, async clear() {
    guard();
    try { await io.clear(); guard(); if ((await load()).records.length) throw Error(); }
    catch { throw Error("Clear could not be confirmed. Device storage may be unavailable."); }
    return testFile([]);
  } };
}
export function nativeTestStorage(allowed: () => boolean) {
  const file = async () => {
    if (!__DEV__ || !allowed() || (Platform.OS !== "ios" && Platform.OS !== "android")) throw Error("Native developer storage unavailable.");
    // Load native storage only after development/context/platform gates (literal Metro path).
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const fs = require("expo-file-system/legacy") as typeof import("expo-file-system/legacy");
    if (!fs.documentDirectory?.startsWith("file://")) throw Error("Native developer storage unavailable.");
    return { fs, uri: fs.documentDirectory + "readbuddy-component4-developer-synthetic-v1.json" };
  };
  return developerTestStorage({
    async read() { const { fs, uri } = await file(); const info = await fs.getInfoAsync(uri);
      if (!info.exists) return null;
      if (info.isDirectory || info.size > 100_000) throw Error("Invalid storage.");
      return fs.readAsStringAsync(uri);
    },
    async write(text) { const { fs, uri } = await file();
      await fs.writeAsStringAsync(uri, text);
    },
    async clear() { const { fs, uri } = await file(); await fs.deleteAsync(uri, { idempotent: true }); },
  }, () => __DEV__ && allowed());
}
