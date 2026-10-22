import contract from "./syntheticReportDisplayContract.json";
import type { PreviewRole } from "../types";

export interface LocalReportSnapshot {
  schemaVersion: "synthetic-local-report-v1";
  synthetic: true;
  source: "local-ollama";
  validated: true;
  role: "learner";
  model: string;
  generatedAt: string;
  reportingStartUtc: string;
  reportingEndUtc: string;
  statements: string[];
}

const keys = ["schemaVersion", "synthetic", "source", "validated", "role", "model",
  "generatedAt", "reportingStartUtc", "reportingEndUtc", "statements"].sort();
const models = ["qwen3:4b", "qwen3:4b-q4_K_M", "qwen3:4b-q8_0", "qwen3:4b-fp16"];

/** A bundled synthetic fixture check, not authentication or a production trust boundary. */
export function validateLocalReportSnapshot(value: unknown, role: PreviewRole): LocalReportSnapshot | null {
  if (role !== "learner" || typeof value !== "object" || value === null || Array.isArray(value)) return null;
  const data = value as Record<string, unknown>;
  if (JSON.stringify(Object.keys(data).sort()) !== JSON.stringify(keys)
    || data.schemaVersion !== "synthetic-local-report-v1"
    || data.synthetic !== true || data.validated !== true || data.source !== "local-ollama"
    || data.role !== role || typeof data.model !== "string" || !models.includes(data.model)
    || typeof data.generatedAt !== "string"
    || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00$/.test(data.generatedAt)
    || !Number.isFinite(Date.parse(data.generatedAt))
    || new Date(data.generatedAt).toISOString().replace(".000Z", "+00:00") !== data.generatedAt
    || Date.parse(data.generatedAt) > Date.now() + 300_000
    || data.reportingStartUtc !== contract.reportingStartUtc
    || data.reportingEndUtc !== contract.reportingEndUtc
    || !Array.isArray(data.statements)
    || !data.statements.every((text: unknown) => typeof text === "string")
    || JSON.stringify([...data.statements].sort()) !== JSON.stringify([...contract.statements].sort())) return null;
  return data as unknown as LocalReportSnapshot;
}

export function selectLocalReportSnapshot({ enabled, development, demoMode, role, read }: {
  enabled: boolean; development: boolean; demoMode: boolean; role: PreviewRole; read: () => unknown;
}): LocalReportSnapshot | null {
  // Check all gates before reading the local artifact. Never use the live provider.
  if (!enabled || !development || !demoMode || role !== "learner") return null;
  try { return validateLocalReportSnapshot(read(), role); } catch { return null; }
}

export function readBundledLocalSnapshot(): unknown {
  // Metro requires a literal path. This function is called only after the opt-in gates.
  return require("./localReportSnapshot.json") as unknown;
}
