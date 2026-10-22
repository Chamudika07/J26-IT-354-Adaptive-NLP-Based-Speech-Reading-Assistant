import type { AuthenticatedSession } from "./component4Client";
import { selectConnectedReplay, type ConnectedArtifact } from "../preview/connectedSessionPreview";

export interface Pp1Connection { baseUrl: string; session: AuthenticatedSession }
export interface Pp1Result {
  source: "postgresql-backed-python";
  selectedSessionCount: number;
  result: ConnectedArtifact;
}
function normalized(value: unknown): string {
  if (Array.isArray(value)) return JSON.stringify(value.map((item) => JSON.parse(normalized(item))));
  if (value && typeof value === "object") {
    return JSON.stringify(Object.fromEntries(Object.entries(value).filter(([key]) => key !== "generatedAt")
      .sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => [key, JSON.parse(normalized(item))])));
  }
  return JSON.stringify(value);
}
/** Explicit learner-only sample source. Errors never select offline evidence automatically. */
export function createPp1Client(connection: Pp1Connection, transport: typeof fetch = fetch) {
  const base = new URL(connection.baseUrl);
  if (base.protocol !== "https:" || base.username || base.password || base.search || base.hash ||
      base.pathname.replace(/\/$/, "") !== "/api/v1" || !connection.session.scopeKey) throw new Error("Invalid server address");
  const load = async (count: number, signal?: AbortSignal, saved = false): Promise<Pp1Result> => {
    if (!__DEV__ || !Number.isInteger(count) || count < (saved ? -1 : 0) || count > 6) throw new Error("Sample unavailable");
    let expected = selectConnectedReplay({ index: count, development: true, demoMode: true, role: "learner" });
    if (!expected && !saved) throw new Error("Sample unavailable");
    const controller = new AbortController();
    const abort = () => controller.abort();
    if (signal?.aborted) throw new Error("Cancelled");
    signal?.addEventListener("abort", abort);
    const timer = setTimeout(abort, 15000);
    try {
      const token = await connection.session.getAccessToken();
      if (!token || /\s/.test(token) || controller.signal.aborted) throw new Error("Sign in required");
      const response = await transport(`${base.toString().replace(/\/$/, "")}/learner-modelling/pp1-demo/${saved ? "saved-progress" : `scenarios/${count}`}`, {
        headers: { Authorization: `Bearer ${token}` }, redirect: "error", signal: controller.signal,
      });
      if (response.status !== 200) throw new Error("Sample server unavailable");
      if (Number(response.headers.get("content-length")) > 1000000) throw new Error("Invalid sample response");
      const raw = await response.text();
      if (raw.length > 1000000 || controller.signal.aborted) throw new Error("Invalid sample response");
      const data = JSON.parse(raw);
      if (saved) {
        count = data.selectedSessionCount;
        if (!Number.isInteger(count) || count < 0 || count > 6) throw new Error("Invalid saved count");
        expected = selectConnectedReplay({ index: count, development: true, demoMode: true, role: "learner" });
      }
      const keys = ["schemaVersion", "synthetic", "verifiedTelemetry", "source", "datasetKey", "fixtureVersion", "sourceDigest", "selectedSessionCount", "role", "generatedAt", "result"];
      if (Object.keys(data).length !== keys.length || keys.some((key) => !(key in data)) ||
          data.schemaVersion !== "pp1-demo-result-v1" || data.synthetic !== true || data.verifiedTelemetry !== false ||
          data.source !== "postgresql-backed-python" || data.datasetKey !== "pp1-six-session-journey" ||
          data.fixtureVersion !== 1 || data.role !== "learner" || data.selectedSessionCount !== count ||
          data.sourceDigest !== "33659d1c6947d7687a7d74e00f4540da065a2450b357805c90566ec71fda0ad7" || !Number.isFinite(Date.parse(data.generatedAt)) ||
          data.generatedAt !== data.result.generatedAt || normalized(data.result) !== normalized(expected)) {
        throw new Error("Invalid sample response");
      }
      return { source: data.source, selectedSessionCount: count, result: data.result };
    } catch { throw new Error("Sample results unavailable. Choose offline examples explicitly."); }
    finally { clearTimeout(timer); signal?.removeEventListener("abort", abort); }
  };
  const save = async (count: number, signal?: AbortSignal): Promise<Pp1Result> => {
    if (!__DEV__ || !Number.isInteger(count) || count < 0 || count > 6 || signal?.aborted) throw new Error("Invalid sample");
    const controller = new AbortController();
    const abort = () => controller.abort(); signal?.addEventListener("abort", abort);
    const timer = setTimeout(abort, 15000);
    try {
      const token = await connection.session.getAccessToken();
      if (!token || /\s/.test(token) || controller.signal.aborted) throw new Error("Sign in required");
      const response = await transport(`${base.toString().replace(/\/$/, "")}/learner-modelling/pp1-demo/saved-progress/${count}`, {
        method: "POST", headers: { Authorization: `Bearer ${token}` }, redirect: "error", signal: controller.signal,
      });
      if (response.status !== 200 || Number(response.headers.get("content-length")) > 10000) throw new Error("Save unavailable");
      const raw = await response.text(); if (raw.length > 10000 || controller.signal.aborted) throw new Error("Save not confirmed");
      const receipt = JSON.parse(raw);
      if (Object.keys(receipt).sort().join() !== ["synthetic", "sourceDigest", "savedSessionCount", "createdSessionCount"].sort().join() ||
          receipt.synthetic !== true || receipt.sourceDigest !== "33659d1c6947d7687a7d74e00f4540da065a2450b357805c90566ec71fda0ad7" ||
          !Number.isInteger(receipt.savedSessionCount) || receipt.savedSessionCount < count || receipt.savedSessionCount > 6 ||
          !Number.isInteger(receipt.createdSessionCount) || receipt.createdSessionCount < 0 || receipt.createdSessionCount > count) throw new Error("Invalid save receipt");
      const fresh = await load(-1, controller.signal, true);
      if (fresh.selectedSessionCount < receipt.savedSessionCount) throw new Error("Saved read-back mismatch");
      return fresh;
    } catch { throw new Error("Save or refresh not confirmed. Retry the same sample safely, or choose offline examples."); }
    finally { clearTimeout(timer); signal?.removeEventListener("abort", abort); }
  };
  return Object.assign(load, { save, readSaved: (signal?: AbortSignal) => load(-1, signal, true) });
}
