import fixtures from "./liveProjectionFixtures.json";
import { Component4ApiError, createComponent4Client, type LiveConnection, type ReadingSessionInput } from "../data/component4Client";
import { createLiveDashboardProvider } from "../data/liveDashboardProvider";
import { validateContract } from "../data/validateContract";

export const window = { start_at_utc: "2026-01-01T00:00:00Z", end_at_utc: "2026-02-01T00:00:00Z" };
export const connection = (role: LiveConnection["role"] = "learner"): LiveConnection => ({
  baseUrl: "https://readbuddy.example/api/v1", learnerId: "00000000-0000-4000-8000-000000000001", role,
  session: { scopeKey: "test-session", getAccessToken: async () => "test-access-token" },
});
export function response(value: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, text: async () => JSON.stringify(value), headers: { get: () => null } } as unknown as Response;
}
function transport(value: unknown, status = 200) { return jest.fn(async () => response(value, status)); }
const input = (): ReadingSessionInput => ({ learner_id: connection().learnerId,
  client_session_id: "00000000-0000-4000-8000-000000000002", task_type: "independent_reading", difficulty_tier: "intermediate",
  support_mode: "adaptive", completion_status: "completed", session_start_time: "2026-01-05T00:00:00Z", session_end_time: "2026-01-05T00:02:00Z",
  words_attempted: 100, words_correct: 90, target_word_count: 100, active_duration_ms: 60000, total_duration_ms: 70000 });

it.each(["learner", "guardian", "educator"] as const)("maps actual backend %s projector output without new decisions", async role => {
  const mock = transport(fixtures[role]);
  const result = await createLiveDashboardProvider(connection(role), mock).load(role, window);
  expect(result.role).toBe(role);
  expect(result.sessionCount).toBe(6);
  expect(result.contexts[0]?.metrics[0]?.latestValue).toBe(90);
  expect(result.contexts[0]?.metrics[1]?.latestValue).toBe(100);
  expect(result.contexts[0]?.metrics[2]?.latestValue).toBeNull();
  expect(result.contexts[0]?.metrics[2]?.unit).toBe("per 100 attempted words");
  expect(result).not.toHaveProperty("recommendation");
  expect(result).not.toHaveProperty("engagement");
  expect(mock).toHaveBeenCalledWith(expect.stringContaining(role === "learner" ? "/progress?" : role === "guardian" ? "/guardian-summary?" : "/educator-analytics?"), expect.objectContaining({ headers: expect.objectContaining({ Authorization: "Bearer test-access-token" }) }));
});
it("rejects a different role before any request", async () => {
  const mock = transport(fixtures.learner);
  await expect(createLiveDashboardProvider(connection(), mock).load("guardian", window)).rejects.toMatchObject({ failure: "forbidden" });
  expect(mock).not.toHaveBeenCalled();
});
it.each(["http://readbuddy.example/api/v1", "https://user:pass@readbuddy.example/api/v1", "https://readbuddy.example/wrong", "https://readbuddy.example/api/v1?token=bad"])("rejects insecure or ambiguous URL %s", baseUrl => {
  expect(() => createComponent4Client({ ...connection(), baseUrl }, transport({}))).toThrow(Component4ApiError);
});
it("refreshes through the host exactly once after 401", async () => {
  const config = connection();
  config.session.refreshAccessToken = jest.fn(async () => "refreshed-test-token");
  const mock = jest.fn().mockResolvedValueOnce(response({}, 401)).mockResolvedValueOnce(response(fixtures.learner));
  await createComponent4Client(config, mock).loadLearnerProgress(window);
  expect(config.session.refreshAccessToken).toHaveBeenCalledTimes(1);
  expect(mock).toHaveBeenCalledTimes(2);
  expect(mock.mock.calls[1]?.[1].headers.Authorization).toBe("Bearer refreshed-test-token");
});
it("does not loop on repeated 401 or invent an anonymous session", async () => {
  const config = connection();
  config.session.refreshAccessToken = jest.fn(async () => "second-test-token");
  const mock = transport({}, 401);
  await expect(createComponent4Client(config, mock).loadLearnerProgress(window)).rejects.toMatchObject({ failure: "authentication_required" });
  expect(mock).toHaveBeenCalledTimes(2);
  const missing = { ...config, session: { scopeKey: "missing", getAccessToken: async () => null } };
  await expect(createComponent4Client(missing, mock).loadLearnerProgress(window)).rejects.toMatchObject({ failure: "authentication_required" });
  expect(mock).toHaveBeenCalledTimes(2);
});
it.each([[403, "consent_required", "consent_required"], [403, "forbidden", "forbidden"], [404, "not_found", "learner_unavailable"], [409, "digest_conflict", "session_conflict"], [422, "validation_error", "invalid_request"], [503, "service_unavailable", "temporarily_unavailable"]])("sanitizes HTTP %s %s", async (status, code, failure) => {
  const mock = transport({ error: { code, message: "private raw error" } }, Number(status));
  await expect(createComponent4Client(connection(), mock).loadLearnerProgress(window)).rejects.toMatchObject({ failure, message: "Reading information is unavailable." });
  expect(mock).toHaveBeenCalledTimes(1);
});
it("rejects extra cross-role fields, malformed responses and mismatched periods", async () => {
  for (const value of [fixtures.guardian, { ...fixtures.learner, engagement: 1 }, { ...fixtures.learner, reporting_period: { ...window, end_at_utc: "2026-01-30T00:00:00Z" } }, { ...fixtures.learner, included_session_count: -1 }]) {
    await expect(createComponent4Client(connection(), transport(value)).loadLearnerProgress(window)).rejects.toMatchObject({ failure: "invalid_response" });
  }
});
it("validates unit identity and does not flatten incompatible contexts", async () => {
  const bad = JSON.parse(JSON.stringify(fixtures.learner));
  bad.contexts[0].metrics[0].unit = "words_per_minute";
  await expect(createLiveDashboardProvider(connection(), transport(bad)).load("learner", window)).rejects.toMatchObject({ failure: "invalid_response" });
  const multiple = { ...fixtures.learner, contexts: [...fixtures.learner.contexts, ...fixtures.learner.contexts] };
  const result = await createLiveDashboardProvider(connection(), transport(multiple)).load("learner", window);
  expect(result.contexts).toHaveLength(2);
});
it("rejects malformed JSON and oversized responses", async () => {
  const mock = jest.fn(async () => ({ ...response({}), text: async () => "not json" }));
  await expect(createComponent4Client(connection(), mock as typeof fetch).loadLearnerProgress(window)).rejects.toMatchObject({ failure: "invalid_response" });
  const large = jest.fn(async () => ({ ...response({}), headers: { get: () => "2000001" } }));
  await expect(createComponent4Client(connection(), large as unknown as typeof fetch).loadLearnerProgress(window)).rejects.toMatchObject({ failure: "invalid_response" });
});
it("cancels before transport and bounds stalled token lookup", async () => {
  const controller = new AbortController(); controller.abort();
  const mock = transport(fixtures.learner);
  await expect(createComponent4Client(connection(), mock).loadLearnerProgress(window, controller.signal)).rejects.toMatchObject({ failure: "cancelled" });
  expect(mock).not.toHaveBeenCalled();
  jest.useFakeTimers();
  try {
    const config = { ...connection(), session: { scopeKey: "stall", getAccessToken: () => new Promise<string>(() => {}) } };
    const pending = createComponent4Client(config, mock).loadLearnerProgress(window);
    const assertion = expect(pending).rejects.toMatchObject({ failure: "temporarily_unavailable" });
    await jest.advanceTimersByTimeAsync(15001);
    await assertion;
    expect(mock).not.toHaveBeenCalled();
  } finally { jest.useRealTimers(); }
});
it("submits the existing raw contract and verifies the minimal receipt", async () => {
  const data = input();
  const receipt = { id: "00000000-0000-4000-8000-000000000003", client_session_id: data.client_session_id, created: true };
  const mock = transport(receipt, 201);
  expect(await createComponent4Client(connection(), mock).submitReadingSession(data)).toEqual(receipt);
  expect(mock).toHaveBeenCalledWith(expect.stringContaining("/reading-sessions"), expect.objectContaining({ method: "POST", body: JSON.stringify(data) }));
  expect(JSON.parse(JSON.stringify(data))).not.toHaveProperty("calculated_accuracy");
  await expect(createComponent4Client(connection("guardian"), mock).submitReadingSession(data)).rejects.toMatchObject({ failure: "forbidden" });
});
it("rejects invalid telemetry, wrong learner and forged fields before submission", async () => {
  const mock = transport({});
  for (const data of [{ ...input(), words_correct: 101 }, { ...input(), learner_id: "00000000-0000-4000-8000-000000000099" }, { ...input(), active_duration_ms: 80000 }, { ...input(), calculated_accuracy: 1 }]) {
    await expect(createComponent4Client(connection(), mock).submitReadingSession(data)).rejects.toMatchObject({ failure: "invalid_request" });
  }
  expect(mock).not.toHaveBeenCalled();
});
it("rejects unsupported schema values without adding defaults", () => {
  expect(validateContract("LearnerProgressProjection", { ...fixtures.learner, contexts: null })).toBe(false);
  expect(validateContract("ReadingSessionIngest", { ...input(), completion_status: "fake" })).toBe(false);
});
