/** Shared authenticated API client and mobile session storage. */
import {
  buildApiUrl,
  createSimplificationClient,
  type SimplificationClient,
  SimplificationApiError,
} from "@readbuddy/api-client";
import * as SecureStore from "expo-secure-store";
import { API_BASE_URL } from "../config/env";

export { SimplificationApiError };

const SESSION_STORAGE_KEY = "readbuddy.auth.refresh-session.v1";
const SECURE_STORE_OPTIONS: SecureStore.SecureStoreOptions = {
  keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
};

export interface AuthSession {
  /** Short-lived bearer token. Kept in memory only. */
  accessToken: string | null;
  /** Rotating refresh token. Persisted only in the platform credential store. */
  refreshToken: string | null;
  /** UUID of the active learner profile. */
  learnerId: string | null;
  /** Optional development backend override associated with this session. */
  apiBaseUrl?: string | null;
}

interface StoredRefreshSession {
  version: 1;
  refreshToken: string;
  learnerId: string;
  apiBaseUrl: string | null;
}

interface RefreshResponse {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_in: number;
}

type AuthSessionListener = (session: AuthSession) => void;

let activeSession: AuthSession = {
  accessToken: null,
  refreshToken: null,
  learnerId: null,
  apiBaseUrl: null,
};
const listeners = new Set<AuthSessionListener>();
let cachedClient: { baseUrl: string; client: SimplificationClient } | null = null;

function normalized(value: string | null | undefined): string | null {
  const result = value?.trim();
  return result ? result : null;
}

function notifySessionListeners(): void {
  const snapshot = getAuthSession();
  listeners.forEach((listener) => listener(snapshot));
}

async function secureStorageAvailable(): Promise<boolean> {
  try {
    return await SecureStore.isAvailableAsync();
  } catch {
    return false;
  }
}

async function persistRefreshSession(): Promise<void> {
  if (!(await secureStorageAvailable())) return;

  const refreshToken = normalized(activeSession.refreshToken);
  const learnerId = normalized(activeSession.learnerId);
  if (!refreshToken || !learnerId) {
    await SecureStore.deleteItemAsync(SESSION_STORAGE_KEY, SECURE_STORE_OPTIONS);
    return;
  }

  const stored: StoredRefreshSession = {
    version: 1,
    refreshToken,
    learnerId,
    apiBaseUrl: normalized(activeSession.apiBaseUrl),
  };
  await SecureStore.setItemAsync(
    SESSION_STORAGE_KEY,
    JSON.stringify(stored),
    SECURE_STORE_OPTIONS
  );
}

export function getAuthSession(): AuthSession {
  return { ...activeSession };
}

export function subscribeAuthSession(listener: AuthSessionListener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Update the active session, persisting only the refresh-session fields. */
export async function setAuthSession(session: Partial<AuthSession>): Promise<void> {
  activeSession = { ...activeSession, ...session };
  await persistRefreshSession();
  notifySessionListeners();
}

/** Remove both the in-memory access token and persisted refresh session. */
export async function clearAuthSession(): Promise<void> {
  activeSession = {
    accessToken: null,
    refreshToken: null,
    learnerId: null,
    apiBaseUrl: null,
  };
  try {
    if (await secureStorageAvailable()) {
      await SecureStore.deleteItemAsync(SESSION_STORAGE_KEY, SECURE_STORE_OPTIONS);
    }
  } finally {
    notifySessionListeners();
  }
}

/** Restore the refresh session after reload. Access is renewed on demand. */
export async function restoreAuthSession(): Promise<AuthSession> {
  if (!(await secureStorageAvailable())) return getAuthSession();

  try {
    const serialized = await SecureStore.getItemAsync(
      SESSION_STORAGE_KEY,
      SECURE_STORE_OPTIONS
    );
    if (!serialized) return getAuthSession();

    const candidate = JSON.parse(serialized) as Partial<StoredRefreshSession>;
    const refreshToken = normalized(candidate.refreshToken);
    const learnerId = normalized(candidate.learnerId);
    if (candidate.version !== 1 || !refreshToken || !learnerId) {
      await SecureStore.deleteItemAsync(SESSION_STORAGE_KEY, SECURE_STORE_OPTIONS);
      return getAuthSession();
    }
    activeSession = {
      accessToken: null,
      refreshToken,
      learnerId,
      apiBaseUrl: normalized(candidate.apiBaseUrl),
    };
    notifySessionListeners();
  } catch {
    await SecureStore.deleteItemAsync(SESSION_STORAGE_KEY, SECURE_STORE_OPTIONS).catch(
      () => undefined
    );
  }
  return getAuthSession();
}

export function getEffectiveApiBaseUrl(): string {
  return normalized(activeSession.apiBaseUrl) ?? API_BASE_URL;
}

function isRefreshResponse(value: unknown): value is RefreshResponse {
  if (!value || typeof value !== "object") return false;
  const response = value as Record<string, unknown>;
  return (
    typeof response.access_token === "string" &&
    response.access_token.trim().length > 0 &&
    typeof response.refresh_token === "string" &&
    response.refresh_token.trim().length > 0 &&
    response.token_type === "bearer" &&
    typeof response.expires_in === "number" &&
    response.expires_in > 0
  );
}

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = normalized(activeSession.refreshToken);
  if (!refreshToken) return null;

  let response: Response;
  try {
    response = await globalThis.fetch(
      buildApiUrl(getEffectiveApiBaseUrl(), "/auth/refresh"),
      {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      }
    );
  } catch {
    return null;
  }
  if (!response.ok) return null;

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return null;
  }
  if (!isRefreshResponse(payload)) return null;

  const accessToken = payload.access_token.trim();
  await setAuthSession({
    accessToken,
    refreshToken: payload.refresh_token.trim(),
  });
  return accessToken;
}

function getClient(): SimplificationClient {
  const baseUrl = getEffectiveApiBaseUrl();
  if (!cachedClient || cachedClient.baseUrl !== baseUrl) {
    cachedClient = {
      baseUrl,
      client: createSimplificationClient({
        baseUrl,
        getAccessToken: () => activeSession.accessToken,
        refreshAccessToken,
        onAuthenticationFailure: clearAuthSession,
      }),
    };
  }
  return cachedClient.client;
}

/** One facade ensures every Component 2 operation uses the same refresh lock. */
export const simplificationClient: SimplificationClient = {
  simplifyText: (learnerId, request, options) =>
    getClient().simplifyText(learnerId, request, options),
  explainWord: (learnerId, request, options) =>
    getClient().explainWord(learnerId, request, options),
  submitReadingFeedback: (learnerId, sessionId, request, options) =>
    getClient().submitReadingFeedback(learnerId, sessionId, request, options),
};
