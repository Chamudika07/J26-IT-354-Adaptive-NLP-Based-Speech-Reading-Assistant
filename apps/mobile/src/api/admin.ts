import { unwrap, type Schema } from "@j26/api-client";
import type { Session } from "./session";

export function adminApi(session: Session) {
  const api = session.api;
  return {
    createEducator: async (body: Schema<"AccountCreate">) =>
      unwrap(await api.POST("/api/v1/auth/users", { body })),
    createLearner: async (body: Schema<"LearnerCreate">) =>
      unwrap(await api.POST("/api/v1/learners", { body })),
    assign: async (learner_id: string, body: Schema<"EducatorGrantCreate">) =>
      unwrap(
        await api.POST("/api/v1/learners/{learner_id}/educator-grants", {
          params: { path: { learner_id } },
          body,
        }),
      ),
    revoke: async (learner_id: string, grant_id: string) =>
      unwrap(
        await api.POST(
          "/api/v1/learners/{learner_id}/educator-grants/{grant_id}/revoke",
          { params: { path: { learner_id, grant_id } } },
        ),
      ),
  };
}
