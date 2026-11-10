import { unwrap, type Schema } from "@j26/api-client";
import type { Session } from "./session";
const L = "/api/v1/learners/{learner_id}" as const;
const A = `${L}/reading-assessments` as const;
const M = `${L}/reading-materials/{material_id}` as const;
export function learningApi(session: Session) {
  const api = session.api;
  return {
    profile: async (learner_id: string) =>
      unwrap(await api.GET(L, { params: { path: { learner_id } } })),
    preferences: async (learner_id: string) =>
      unwrap(
        await api.GET(`${L}/preferences`, { params: { path: { learner_id } } }),
      ),
    updatePreferences: async (
      learner_id: string,
      body: Schema<"LearnerPreferenceUpdate">,
    ) =>
      unwrap(
        await api.PATCH(`${L}/preferences`, {
          params: { path: { learner_id } },
          body,
        }),
      ),
    assessmentMaterials: async (cursor?: string) =>
      unwrap(
        await api.GET("/api/v1/assessment-materials", {
          params: { query: { cursor, limit: 25 } },
        }),
      ),
    assessments: async (learner_id: string, cursor?: string) =>
      unwrap(
        await api.GET(A, {
          params: { path: { learner_id }, query: { cursor, limit: 25 } },
        }),
      ),
    startAssessment: async (
      learner_id: string,
      body: Schema<"AssessmentStartRequest">,
    ) => unwrap(await api.POST(A, { params: { path: { learner_id } }, body })),
    assessment: async (learner_id: string, assessment_id: string) =>
      unwrap(
        await api.GET(`${A}/{assessment_id}`, {
          params: { path: { learner_id, assessment_id } },
        }),
      ),
    completeAssessment: async (
      learner_id: string,
      assessment_id: string,
      body: Schema<"AssessmentCompletionRequest">,
    ) =>
      unwrap(
        await api.POST(`${A}/{assessment_id}/complete`, {
          params: { path: { learner_id, assessment_id } },
          body,
        }),
      ),
    abandonAssessment: async (
      learner_id: string,
      assessment_id: string,
      row_version: number,
    ) =>
      unwrap(
        await api.POST(`${A}/{assessment_id}/abandon`, {
          params: { path: { learner_id, assessment_id } },
          body: { row_version },
        }),
      ),
    revisions: async (
      learner_id: string,
      material_id: string,
      cursor?: string,
    ) =>
      unwrap(
        await api.GET(`${M}/revisions`, {
          params: {
            path: { learner_id, material_id },
            query: { cursor, limit: 25 },
          },
        }),
      ),
    revision: async (
      learner_id: string,
      material_id: string,
      revision_id: string,
    ) =>
      unwrap(
        await api.GET(`${M}/revisions/{revision_id}`, {
          params: { path: { learner_id, material_id, revision_id } },
        }),
      ),
    revise: async (
      learner_id: string,
      material_id: string,
      body: Schema<"RevisionCreate">,
    ) =>
      unwrap(
        await api.POST(`${M}/revisions`, {
          params: { path: { learner_id, material_id } },
          body,
        }),
      ),
    archiveMaterial: async (
      learner_id: string,
      material_id: string,
      row_version: number,
    ) =>
      unwrap(
        await api.POST(`${M}/archive`, {
          params: { path: { learner_id, material_id } },
          body: { row_version },
        }),
      ),
  };
}
