import guardians from "./guardianScenarioContract.json";
import educators from "./educatorScenarioContract.json";

export type GuardianArtifact = typeof guardians[number];
export type EducatorArtifact = typeof educators[number];
function canonical(v: unknown): string {
  if (Array.isArray(v)) return `[${v.map(canonical).join(",")}]`;
  if (v && typeof v === "object") return `{${Object.keys(v).sort().map(k => `${JSON.stringify(k)}:${canonical((v as Record<string, unknown>)[k])}`).join(",")}}`;
  return JSON.stringify(v) ?? "invalid";
}
export function selectRoleScenario(role: "guardian", id: string, read?: () => unknown): GuardianArtifact | null;
export function selectRoleScenario(role: "educator", id: string, read?: () => unknown): EducatorArtifact | null;
export function selectRoleScenario(role: "guardian" | "educator", id: string, read?: () => unknown): GuardianArtifact | EducatorArtifact | null;
export function selectRoleScenario(role: "guardian" | "educator", id: string, read?: () => unknown) {
  if (!__DEV__) return null;
  try {
    const pin = role === "guardian" ? guardians : educators;
    const value: unknown = read ? read() : role === "guardian" ? require("./guardianScenarioResults.json") : require("./educatorScenarioResults.json");
    if (canonical(value) !== canonical(pin)) return null;
    const entry = pin.find(a => a.scenarioId === id && a.role === role && a.synthetic === true && a.schemaVersion === "role-scenario-v1");
    return entry ? JSON.parse(JSON.stringify(entry)) as GuardianArtifact | EducatorArtifact : null;
  } catch { return null; }
}
