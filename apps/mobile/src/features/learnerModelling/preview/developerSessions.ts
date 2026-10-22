/** Local simulator subset of ReadingSessionIngest. No learner/document identities or verified provenance. */
export const tasks = ["independent_reading", "assisted_read_aloud", "guided_echo_reading"] as const;
export const tiers = ["early", "intermediate", "advanced"] as const;
export const modes = ["baseline_fixed", "adaptive", "manual_override"] as const;
export const completions = ["completed", "abandoned", "interrupted"] as const;
export interface TestSession {
  id: string; start: string; end: string;
  task: typeof tasks[number]; tier: typeof tiers[number]; mode: typeof modes[number];
  attempted: number; correct: number; target: number; activeMs: number; totalMs: number;
  hesitations: number | null;
  pauseCount: number | null; pauseMs: number | null; replayCount: number | null;
  completion: typeof completions[number];
}
export interface TestFile { version: 2; synthetic: true; verifiedTelemetry: false; records: TestSession[] }
const legacyFields = ["id", "start", "end", "task", "tier", "mode", "attempted", "correct", "target", "activeMs", "totalMs", "hesitations"].sort();
const fields = ["id", "start", "end", "task", "tier", "mode", "attempted", "correct", "target", "activeMs", "totalMs", "hesitations", "pauseCount", "pauseMs", "replayCount", "completion"].sort();
export function validateTestSession(value: unknown): TestSession {
  const error = () => { throw new Error("Invalid synthetic session. Check UUID, UTC dates, context, counts and durations."); };
  if (!value || typeof value !== "object" || Array.isArray(value)) return error();
  const data = value as TestSession;
  if (JSON.stringify(Object.keys(data).sort()) !== JSON.stringify(fields)
    || typeof data.id !== "string" || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(data.id)
    || !tasks.includes(data.task) || !tiers.includes(data.tier) || !modes.includes(data.mode) || !completions.includes(data.completion)) return error();
  for (const date of [data.start, data.end]) {
    if (typeof date !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(date)
      || !Number.isFinite(Date.parse(date)) || new Date(date).toISOString() !== date) return error();
  }
  for (const n of [data.attempted, data.correct, data.target, data.activeMs, data.totalMs]) {
    if (!Number.isSafeInteger(n) || n < 0 || n > 1_000_000_000) return error();
  }
  for (const n of [data.hesitations, data.pauseCount, data.pauseMs, data.replayCount]) {
    if (n !== null && (!Number.isSafeInteger(n) || n < 0 || n > 1_000_000_000)) return error();
  }
  if (data.correct > data.attempted || data.activeMs > data.totalMs || data.end < data.start
    || (data.pauseMs !== null && data.pauseMs > data.totalMs)) return error();
  return { ...data, id: data.id.toLowerCase() };
}
export function validateTestFile(value: unknown): TestFile {
  if (!value || typeof value !== "object") throw Error("Invalid synthetic test storage.");
  const file = value as Omit<TestFile, "version"> & { version: number };
  if (JSON.stringify(Object.keys(file).sort()) !== JSON.stringify(["records", "synthetic", "verifiedTelemetry", "version"])
    || (file.version !== 1 && file.version !== 2) || file.synthetic !== true || file.verifiedTelemetry !== false
    || !Array.isArray(file.records) || file.records.length > 100) throw Error("Invalid synthetic test storage.");
  const records = file.records.map((record) => {
    if (file.version === 2) return validateTestSession(record);
    // V1 explicitly simulated completed sessions. Uncollected pause/replay fields remain missing.
    if (!record || typeof record !== "object" || JSON.stringify(Object.keys(record).sort()) !== JSON.stringify(legacyFields)) throw Error("Invalid legacy synthetic record.");
    return validateTestSession({ ...record, pauseCount: null, pauseMs: null, replayCount: null, completion: "completed" });
  });
  if (new Set(records.map((r) => r.id)).size !== records.length) throw Error("Duplicate synthetic session IDs.");
  return { version: 2, synthetic: true, verifiedTelemetry: false, records };
}
export function testFile(records: TestSession[]): TestFile {
  return validateTestFile({ version: 2, synthetic: true, verifiedTelemetry: false, records });
}
// Mirrors analytics.py denominator rules. No recommendation thresholds or decisions.
const round = (n: number, digits: number) => {
  // Python round uses half-even; JS toFixed rounds exact ties upward. All inputs
  // here are bounded nonnegative metrics. A decimal midpoint is binary-exact only
  // when its odd numerator cancels the 5^digits denominator.
  const factor = 10 ** digits;
  const scaled = n * factor;
  const lower = Math.floor(scaled);
  if (scaled - lower === 0.5 && (2 * lower + 1) % (5 ** digits) === 0 && lower % 2 === 0) {
    return lower / factor;
  }
  return Number(n.toFixed(digits));
};
export function testMetrics(record: TestSession) {
  const r = validateTestSession(record);
  return {
    accuracy: r.attempted === 0 ? null : round(r.correct / r.attempted, 4),
    wpm: r.activeMs < 1000 ? null : round(r.attempted / (r.activeMs / 60000), 2),
    hesitation: r.hesitations === null || r.attempted === 0 ? null : round(r.hesitations / r.attempted, 4),
  };
}
export function eligibleTestSessions(records: TestSession[], days: number, end: number) {
  return records.filter((r) => Date.parse(r.start) >= end - days * 86400000 && Date.parse(r.start) < end)
    .sort((a, b) => a.start.localeCompare(b.start) || a.id.localeCompare(b.id));
}


/** Developer diagnostic only: existing analytics.py v0.1-research-heuristic defaults.
 * This is not approved for learner/guardian/educator dashboard disclosure.
 */
export function experimentalTestEngagement(record: TestSession) {
  const r = validateTestSession(record);
  const missing = [r.target <= 0 ? "target word count" : null, r.totalMs <= 0 ? "total duration" : null, r.pauseMs === null ? "total pause duration" : null].filter((s): s is string => s !== null);
  if (missing.length || r.pauseMs === null) return { score: null, missing, completion: null, active: null, pauseEfficiency: null };
  const fraction = Math.min(1, r.attempted / r.target);
  const completion = r.completion === "completed" ? 1 : round(fraction * (r.completion === "interrupted" ? 0.5 : 1), 4);
  const active = round(Math.min(1, r.activeMs / r.totalMs), 4);
  const pauseEfficiency = r.activeMs === 0 ? 0 : round(Math.max(0, 1 - Math.min(1, r.pauseMs / (r.activeMs * 0.5))), 4);
  const score = Math.max(0, Math.min(1, round(0.5 * completion + 0.3 * active + 0.2 * pauseEfficiency, 4)));
  return { score, missing, completion, active, pauseEfficiency };
}
