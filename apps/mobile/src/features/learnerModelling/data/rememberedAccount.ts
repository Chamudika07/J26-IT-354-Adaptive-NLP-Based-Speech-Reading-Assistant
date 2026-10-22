import { Platform } from "react-native";
import type { RefreshPersistence } from "./accountSession";

export interface LoginSettings { version: 1; baseUrl: string; handle: string; remember: boolean; autoSignIn: boolean }
export interface LoginStorage {
  loadSettings(): Promise<LoginSettings | null>;
  saveSettings(value: LoginSettings): Promise<void>;
  readSecret(): Promise<string | null>;
  writeSecret(value: string): Promise<void>;
  deleteSecret(): Promise<void>;
}
export function validateLoginSettings(value: unknown): LoginSettings {
  const v = value as LoginSettings;
  if (!v || typeof v !== "object" || Object.keys(v).sort().join() !== ["version","baseUrl","handle","remember","autoSignIn"].sort().join() ||
      v.version !== 1 || typeof v.baseUrl !== "string" || v.baseUrl.length > 2048 || typeof v.handle !== "string" || !v.handle.trim() || v.handle.length > 128 || /[\u0000-\u001f\u007f]/.test(v.handle) || typeof v.remember !== "boolean" || typeof v.autoSignIn !== "boolean") throw new Error("Invalid login settings");
  const url = new URL(v.baseUrl);
  if (url.protocol !== "https:" || url.username || url.password || url.search || url.hash || url.pathname.replace(/\/$/, "") !== "/api/v1") throw new Error("Invalid server address");
  return { ...v, baseUrl: url.toString().replace(/\/$/, "") };
}
/** All writes are serialized so logout cannot be overtaken by a refresh write. */
export function createRememberStore(storage: LoginStorage) {
  let queue = Promise.resolve();
  function ordered<T>(operation: () => Promise<T>): Promise<T> {
    const result = queue.then(operation); queue = result.then(() => undefined, () => undefined); return result;
  }
  return {
    load: () => ordered(async () => { const settings = await storage.loadSettings(); return settings ? validateLoginSettings(settings) : null; }),
    saveSettings: (settings: LoginSettings) => ordered(() => storage.saveSettings(validateLoginSettings(settings))),
    signOut: (settings: LoginSettings) => ordered(async () => {
      const outcomes = await Promise.allSettled([storage.saveSettings({ ...validateLoginSettings(settings), autoSignIn: false }), storage.deleteSecret()]);
      if (outcomes.some(result => result.status === "rejected")) throw new Error("Stored sign-out could not be confirmed");
    }),
    persistence(settings: LoginSettings): RefreshPersistence {
      const fixed = validateLoginSettings(settings);
      return {
        consume: () => ordered(async () => {
          const raw = await storage.readSecret();
          await storage.deleteSecret(); // Never replay a rotating credential after an uncertain request.
          if (!raw) return null;
          if (raw.length > 2048) throw new Error("Invalid saved session");
          const v = JSON.parse(raw);
          if (!v || Object.keys(v).sort().join() !== ["version","baseUrl","handle","refreshToken"].sort().join() || v.version !== 1 || v.baseUrl !== fixed.baseUrl || v.handle !== fixed.handle || typeof v.refreshToken !== "string" || !v.refreshToken || v.refreshToken.length > 256 || /\s/.test(v.refreshToken)) throw new Error("Invalid saved session");
          return v.refreshToken as string;
        }),
        save: token => ordered(async () => {
          if (!token || token.length > 256 || /\s/.test(token)) throw new Error("Invalid refresh credential");
          await storage.writeSecret(JSON.stringify({ version: 1, baseUrl: fixed.baseUrl, handle: fixed.handle, refreshToken: token }));
        }),
        clear: () => ordered(() => storage.deleteSecret()),
      };
    },
  };
}
export type RememberStore = ReturnType<typeof createRememberStore>;

/** Native adapters are lazy: Demo Mode does not access secure credentials or make auth calls. */
export function nativeRememberStore(): RememberStore {
  const file = () => {
    if (!["ios", "android"].includes(Platform.OS)) throw new Error("Storage unavailable");
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const fs = require("expo-file-system/legacy") as typeof import("expo-file-system/legacy");
    if (!fs.documentDirectory?.startsWith("file://")) throw new Error("Storage unavailable");
    return { fs, uri: fs.documentDirectory + "readbuddy-c4-login-settings-v1.json" };
  };
  const secure = () => {
    // Lazy loading keeps native credential access out of offline Demo Mode.
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    return require("expo-secure-store") as typeof import("expo-secure-store");
  };
  const key = "readbuddy.c4.refresh.v1";
  return createRememberStore({
    async loadSettings() { const { fs, uri } = file(); const info = await fs.getInfoAsync(uri); if (!info.exists) return null; if (info.isDirectory || info.size > 4096) throw new Error("Invalid login settings"); const raw = await fs.readAsStringAsync(uri); if (raw.length > 4096) throw new Error("Invalid login settings"); return validateLoginSettings(JSON.parse(raw)); },
    async saveSettings(settings) { const { fs, uri } = file(); await fs.writeAsStringAsync(uri, JSON.stringify(validateLoginSettings(settings))); },
    readSecret: () => secure().getItemAsync(key),
    writeSecret: value => { const store = secure(); return store.setItemAsync(key, value, { keychainAccessible: store.WHEN_UNLOCKED_THIS_DEVICE_ONLY }); },
    deleteSecret: () => secure().deleteItemAsync(key),
  });
}
