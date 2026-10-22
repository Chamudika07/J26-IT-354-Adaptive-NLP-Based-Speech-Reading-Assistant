import type { PreviewRole, ChangeDirection } from "../types";
import type { ContractName } from "./validateContract";
import { isAwareDate, isUuid, validateContract } from "./validateContract";

export type ApiFailure = "authentication_required" | "consent_required" | "forbidden" |
  "learner_unavailable" | "invalid_request" | "session_conflict" | "temporarily_unavailable" |
  "invalid_response" | "cancelled";
export class Component4ApiError extends Error {
  constructor(readonly failure: ApiFailure) { super("Reading information is unavailable."); }
}
export interface AuthenticatedSession {
  /** Changes on account/session replacement; never a token or learner display name. */
  readonly scopeKey: string;
  getAccessToken(): Promise<string | null>;
  /** Host-owned refresh; no credentials are persisted by Component 4. */
  refreshAccessToken?(): Promise<string | null>;
}
export interface LiveConnection {
  readonly baseUrl: string; // Trusted HTTPS API root, including /api/v1.
  readonly learnerId: string; // Supplied by the authorized Learners selection, never a demo UUID.
  readonly role: PreviewRole;
  readonly session: AuthenticatedSession;
}
export interface ReportingWindow { start_at_utc: string; end_at_utc: string }
type DecimalWire = string | number;
export interface MetricWire {
  metric_name: "reading_accuracy" | "reading_fluency_wpm" | "hesitation_rate_per_word";
  unit: "proportion" | "words_per_minute" | "hesitations_per_attempted_word";
  first_value: DecimalWire | null; latest_value: DecimalWire | null;
  change_direction: ChangeDirection;
  explanation?: string; educational_interpretation?: string;
  valid_observation_count?: number; missing_observation_count?: number;
}
interface ContextWire {
  task_label?: string; difficulty_label?: string; support_label?: string;
  task_type?: string; difficulty_tier?: string; support_mode?: string;
  metrics: MetricWire[];
}
interface ProjectionBase { reporting_period: ReportingWindow; included_session_count: number; disclaimer: string }
export interface LearnerProjection extends ProjectionBase {
  contexts: ContextWire[]; support_observations: { description: string; session_count: number }[];
  difficulty_observations: { description: string; observed_at: string }[]; evidence_message: string;
}
export interface GuardianProjection extends ProjectionBase {
  contexts: ContextWire[]; support_exposures: { description: string; session_count: number }[];
  difficulty_history: { description: string; observed_at: string }[]; evidence_limitations: string[];
}
export interface EducatorProjection extends ProjectionBase {
  partitions: ContextWire[];
  support_mode_exposures: { support_mode: string; session_count: number; total_duration_ms: number; active_duration_ms: number }[];
  difficulty_timeline: { difficulty_tier: string; observed_at: string }[]; limitations: string[];
}
export interface ReadingSessionInput {
  learner_id: string; client_session_id: string; document_id?: string | null;
  session_start_time: string; session_end_time: string;
  task_type: "independent_reading" | "assisted_read_aloud" | "guided_echo_reading";
  difficulty_tier: "early" | "intermediate" | "advanced";
  support_mode: "baseline_fixed" | "adaptive" | "manual_override";
  completion_status: "completed" | "abandoned" | "interrupted";
  words_attempted: number; words_correct: number; target_word_count: number;
  active_duration_ms: number; total_duration_ms: number;
  hesitation_count?: number | null; total_pause_duration_ms?: number | null;
  pause_count?: number | null; replay_count?: number | null;
}
export interface IngestReceipt { id: string; client_session_id: string; created: boolean }

const suffixes = { learner: "progress", guardian: "guardian-summary", educator: "educator-analytics" } as const;
const contracts: Record<PreviewRole, ContractName> = { learner: "LearnerProgressProjection", guardian: "GuardianSummaryProjection", educator: "EducatorAnalyticsProjection" };
export function createComponent4Client(connection: LiveConnection, transport: typeof fetch = fetch) {
  let base: URL;
  try { base = new URL(connection.baseUrl); } catch { throw new Component4ApiError("invalid_request"); }
  if (base.protocol !== "https:" || base.username || base.password || base.search || base.hash ||
      base.pathname.replace(/\/$/, "") !== "/api/v1" || !isUuid(connection.learnerId) || !connection.session.scopeKey) {
    throw new Component4ApiError("invalid_request");
  }
  const root = base.toString().replace(/\/$/, "");
  async function request(path: string, contract: ContractName, signal?: AbortSignal, body?: ReadingSessionInput): Promise<unknown> {
    const controller = new AbortController();
    const abort = () => controller.abort();
    if (signal?.aborted) throw new Component4ApiError("cancelled");
    signal?.addEventListener("abort", abort);
    const timer = setTimeout(abort, 15000);
    function bounded<T>(promise: Promise<T>): Promise<T> {
      return new Promise((resolve, reject) => {
        const stop = () => reject(new Component4ApiError(signal?.aborted ? "cancelled" : "temporarily_unavailable"));
        if (controller.signal.aborted) { stop(); return; }
        controller.signal.addEventListener("abort", stop);
        promise.then(resolve, reject).finally(() => controller.signal.removeEventListener("abort", stop));
      });
    }
    try {
      let token = await bounded(connection.session.getAccessToken());
      for (let attempt = 0; attempt < 2; attempt++) {
        if (controller.signal.aborted) throw new Component4ApiError(signal?.aborted ? "cancelled" : "temporarily_unavailable");
        if (!token || /\s/.test(token)) throw new Component4ApiError("authentication_required");
        const response = await bounded(transport(root + "/learner-modelling" + path, {
          method: body ? "POST" : "GET", signal: controller.signal, redirect: "error",
          headers: { Authorization: `Bearer ${token}`, Accept: "application/json", ...(body ? { "Content-Type": "application/json" } : {}) },
          ...(body ? { body: JSON.stringify(body) } : {}),
        }));
        if (response.status === 401 && attempt === 0 && connection.session.refreshAccessToken) {
          token = await bounded(connection.session.refreshAccessToken());
          continue;
        }
        if (Number(response.headers.get("content-length")) > 2000000) throw new Component4ApiError("invalid_response");
        const raw = await bounded(response.text());
        if (raw.length > 2000000) throw new Component4ApiError("invalid_response");
        let value: unknown;
        try { value = JSON.parse(raw); } catch {
          if (response.ok) throw new Component4ApiError("invalid_response");
          value = null;
        }
        if (!response.ok) {
          const code = (value as { error?: { code?: unknown } } | null)?.error?.code;
          const failure: ApiFailure = response.status === 401 ? "authentication_required" :
            response.status === 403 ? code === "consent_required" ? "consent_required" : "forbidden" :
            response.status === 404 ? "learner_unavailable" : response.status === 409 ? "session_conflict" :
            response.status === 422 ? "invalid_request" : "temporarily_unavailable";
          throw new Component4ApiError(failure);
        }
        if ((!body && response.status !== 200) || (body && response.status !== 200 && response.status !== 201) ||
            !validateContract(contract, value)) throw new Component4ApiError("invalid_response");
        return value;
      }
      throw new Component4ApiError("authentication_required");
    } catch (error) {
      if (signal?.aborted) throw new Component4ApiError("cancelled");
      if (error instanceof Component4ApiError) throw error;
      throw new Component4ApiError("temporarily_unavailable");
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener("abort", abort);
    }
  }
  async function load(role: PreviewRole, window: ReportingWindow, signal?: AbortSignal) {
    const start = Date.parse(window.start_at_utc), end = Date.parse(window.end_at_utc);
    if (role !== connection.role) throw new Component4ApiError("forbidden");
    if (!isAwareDate(window.start_at_utc) || !isAwareDate(window.end_at_utc) || end <= start || end - start > 90 * 86400000) throw new Component4ApiError("invalid_request");
    const query = `start_at_utc=${encodeURIComponent(window.start_at_utc)}&end_at_utc=${encodeURIComponent(window.end_at_utc)}`;
    const result = await request(`/learners/${connection.learnerId}/${suffixes[role]}?${query}`, contracts[role], signal) as ProjectionBase;
    if (Date.parse(result.reporting_period.start_at_utc) !== start || Date.parse(result.reporting_period.end_at_utc) !== end) throw new Component4ApiError("invalid_response");
    return result;
  }
  return {
    loadLearnerProgress: (w: ReportingWindow, s?: AbortSignal) => load("learner", w, s) as Promise<LearnerProjection>,
    loadGuardianSummary: (w: ReportingWindow, s?: AbortSignal) => load("guardian", w, s) as Promise<GuardianProjection>,
    loadEducatorAnalytics: (w: ReportingWindow, s?: AbortSignal) => load("educator", w, s) as Promise<EducatorProjection>,
    async submitReadingSession(input: ReadingSessionInput, signal?: AbortSignal): Promise<IngestReceipt> {
      if (connection.role !== "learner") throw new Component4ApiError("forbidden");
      if (!validateContract("ReadingSessionIngest", input) || input.learner_id !== connection.learnerId ||
          input.words_correct > input.words_attempted || input.active_duration_ms > input.total_duration_ms ||
          (input.total_pause_duration_ms ?? 0) > input.total_duration_ms || Date.parse(input.session_end_time) < Date.parse(input.session_start_time)) throw new Component4ApiError("invalid_request");
      const snapshot = JSON.parse(JSON.stringify(input)) as ReadingSessionInput;
      const result = await request("/reading-sessions", "SessionIngestReceipt", signal, snapshot) as IngestReceipt;
      if (result.client_session_id !== snapshot.client_session_id) throw new Component4ApiError("invalid_response");
      return result;
    },
  };
}
