import { useSyncExternalStore } from "react";
import type { ConnectedArtifact } from "./connectedSessionPreview";

// An example selection identifier only. Never identity, preferences, evidence or auth.
let selected: string | null = null;
const listeners = new Set<() => void>();
export function selectedScenarioId() { return __DEV__ ? selected : null; }
export function scenarioId(index: number, artifact: ConnectedArtifact) {
  return JSON.stringify([index, artifact.sourceDigest, artifact.reportingStartUtc, artifact.reportingEndUtc, artifact.context.task, artifact.context.tier, artifact.context.mode, artifact.generatedAt]);
}
export function publishScenario(index: number | null, artifact?: ConnectedArtifact | null) {
  if (!__DEV__) return;
  selected = index === null ? null : artifact ? scenarioId(index, artifact) : `unavailable:${index}`;
  listeners.forEach(listener => listener());
}
export function useSelectedScenario() {
  return useSyncExternalStore(listener => { listeners.add(listener); return () => { listeners.delete(listener); }; }, () => selected, () => null);
}
