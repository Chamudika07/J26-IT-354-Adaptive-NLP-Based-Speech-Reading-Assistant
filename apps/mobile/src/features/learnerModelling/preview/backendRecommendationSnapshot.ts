import trustedFixture from "./backendRecommendationSnapshot.json";
import type { PreviewRole } from "../types";

// A pinned, backend-regenerated synthetic fixture, not authentication or a live DTO.
// Backend tests verify that this artifact exactly matches the validated engine output.
export type BackendRecommendationSnapshot = typeof trustedFixture;
const canonical = (value: unknown): string => {
  if (Array.isArray(value)) return "[" + value.map(canonical).join(",") + "]";
  if (typeof value === "object" && value !== null) {
    const data = value as Record<string, unknown>;
    return "{" + Object.keys(data).sort().map((key) => JSON.stringify(key) + ":" + canonical(data[key])).join(",") + "}";
  }
  return JSON.stringify(value) ?? "invalid";
};
const pinned = canonical(trustedFixture);
export function validateBackendRecommendation(value: unknown, role: PreviewRole): BackendRecommendationSnapshot | null {
  try {
    if (role !== "learner" || canonical(value) !== pinned) return null;
    // Detached output: consumers cannot mutate the pinned validation reference.
    return JSON.parse(pinned) as BackendRecommendationSnapshot;
  } catch { return null; }
}
export function selectBackendRecommendation({ enabled, development, demoMode, role, read }: {
  enabled: boolean; development: boolean; demoMode: boolean; role: PreviewRole; read?: () => unknown;
}): BackendRecommendationSnapshot | null {
  if (!enabled || !development || !demoMode || role !== "learner") return null;
  try { return validateBackendRecommendation(read ? read() : trustedFixture, role); } catch { return null; }
}
