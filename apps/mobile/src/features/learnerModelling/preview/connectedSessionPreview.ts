import replayContract from "./connectedSessionReplayContract.json";
import contract from "./connectedSessionContract.json";
import type { PreviewRole } from "../types";

import type recommendationFixture from "./backendRecommendationSnapshot.json";

type Recommendation = typeof recommendationFixture.presentation;
export interface ConnectedArtifact {
  schemaVersion: "connected-synthetic-v2"; synthetic: true; verifiedTelemetry: false;
  role: "learner"; source: "component4-offline-backend"; sourceDigest: string;
  generatedAt: string; reportingStartUtc: string; reportingEndUtc: string;
  context: { task: string; tier: string; mode: string };
  settingsSource: "approved-synthetic-settings-scenario";
  includedSessionCount: number; excludedSessionCount: number;
  metrics: { metric_name: string; display_label: string; unit: string;
    first_value: string | null; latest_value: string | null;
    change_direction: string; evidence_state: string; explanation: string }[];
  history: { sequence: number; recordedAt: string; accuracy: string | null; wpm: string | null; hesitation: string | null; experimentalEngagement: string | null }[];
  reportStatements: string[];
  recommendation: Recommendation | null;
  recommendationExplanation: string[]; disclaimer: string;
}
function canonical(value: unknown): string {
  if (Array.isArray(value)) return "[" + value.map(canonical).join(",") + "]";
  if (value && typeof value === "object") {
    const data = value as Record<string, unknown>;
    return "{" + Object.keys(data).sort().map((key) => JSON.stringify(key)+":"+canonical(data[key])).join(",") + "}";
  }
  return JSON.stringify(value) ?? "invalid";
}
// A build-time synthetic fixture pin, not authentication or a live API validator.
// The opt-in backend importer emits both files; backend tests verify source agreement.
const expected = canonical(contract);
export function selectConnectedPreview({ enabled, development, demoMode, role, read }: {
  enabled: boolean; development: boolean; demoMode: boolean; role: PreviewRole; read?: () => unknown;
}): ConnectedArtifact | null {
  if (!__DEV__ || !enabled || !development || !demoMode || role !== "learner") return null;
  try {
    const value = read ? read() : require("./connectedSessionPreview.json") as unknown;
    if (contract.schemaVersion !== "connected-synthetic-v2" || contract.synthetic !== true
      || contract.verifiedTelemetry !== false || contract.role !== "learner"
      || contract.source !== "component4-offline-backend" || canonical(value) !== expected) return null;
    return JSON.parse(expected) as ConnectedArtifact;
  } catch { return null; }
}

export function selectConnectedReplay({ index, development, demoMode, role, read }: {
  index: number; development: boolean; demoMode: boolean; role: PreviewRole; read?: () => unknown;
}): ConnectedArtifact | null {
  if (!__DEV__ || !development || !demoMode || role !== "learner" || !Number.isInteger(index) || index < 0 || index >= replayContract.length) return null;
  try {
    const value = read ? read() : require("./connectedSessionReplay.json") as unknown;
    if (canonical(value) !== canonical(replayContract)) return null;
    return JSON.parse(canonical(replayContract[index])) as ConnectedArtifact;
  } catch { return null; }
}
export const connectedReplayLength = replayContract.length;
