import { unwrap, type Schema } from "@j26/api-client";
import type { Session } from "./session";
import { learningApi } from "./learning";
import { pdfApi } from "./pdf";

export const materialPath =
  "/api/v1/learners/{learner_id}/reading-materials" as const;
export const runPath =
  "/api/v1/learners/{learner_id}/reading-materials/{material_id}/revisions/{revision_id}/processing-runs" as const;
export type Run = Schema<"app__modules__reading_materials__schemas__RunDetail">;
export type RunParams = {
  learner_id: string;
  material_id: string;
  revision_id: string;
};

export function workflows(session: Session) {
  const api = session.api;
  return {
    ...learningApi(session),
    ...pdfApi(session),
    health: async () => unwrap(await api.GET("/api/v1/health")),
    readiness: async () => unwrap(await api.GET("/api/v1/health/ready")),
    me: async () => unwrap(await api.GET("/api/v1/auth/me")),
    learners: async (cursor?: string) =>
      unwrap(
        await api.GET("/api/v1/learners", {
          params: { query: { cursor, limit: 25 } },
        }),
      ),
    materials: async (learner_id: string, cursor?: string) =>
      unwrap(
        await api.GET(materialPath, {
          params: { path: { learner_id }, query: { cursor, limit: 25 } },
        }),
      ),
    create: async (learner_id: string, body: Schema<"MaterialCreate">) =>
      unwrap(
        await api.POST(materialPath, {
          params: { path: { learner_id } },
          body,
        }),
      ),
    material: async (learner_id: string, material_id: string) =>
      unwrap(
        await api.GET(`${materialPath}/{material_id}`, {
          params: { path: { learner_id, material_id } },
        }),
      ),
    process: async (path: RunParams) =>
      unwrap(await api.POST(runPath, { params: { path }, body: {} })),
    runs: async (path: RunParams, cursor?: string) =>
      unwrap(
        await api.GET(runPath, {
          params: { path, query: { cursor, limit: 25 } },
        }),
      ),
    result: async (path: RunParams, run_id: string) =>
      unwrap(
        await api.GET(`${runPath}/{run_id}`, {
          params: {
            path: { ...path, run_id },
            query: { include_sentences: true },
          },
        }),
      ),
  };
}
