import { unwrap, type Schema } from "@j26/api-client";
import type { Session } from "./session";
const M = "/api/v1/learners/{learner_id}/reading-materials" as const;
const P = `${M}/pdf-sources` as const;
export type PdfFile = Blob | { uri: string; name: string; type: string };
export function pdfApi(session: Session) {
  const api = session.api;
  return {
    uploadPdf: async (
      learner_id: string,
      title: string,
      upload_request_id: string,
      file: PdfFile,
    ) => {
      const data = new FormData();
      data.append("title", title);
      data.append("language_tag", "en");
      data.append("upload_request_id", upload_request_id);
      // React Native's FormData accepts a private cache URI; browsers/Node use Blob.
      if ("uri" in file) data.append("file", file as unknown as Blob);
      else data.append("file", file, "synthetic.pdf");
      return unwrap(
        await api.POST(`${M}/pdf`, {
          params: { path: { learner_id } },
          body: { title, language_tag: "en", upload_request_id, file: "file" },
          bodySerializer: () => data,
        }),
      );
    },
    pdfSources: async (learner_id: string, cursor?: string) =>
      unwrap(
        await api.GET(P, {
          params: { path: { learner_id }, query: { cursor, limit: 25 } },
        }),
      ),
    pdfSource: async (learner_id: string, source_id: string) =>
      unwrap(
        await api.GET(`${P}/{source_id}`, {
          params: { path: { learner_id, source_id } },
        }),
      ),
    extractPdf: async (
      learner_id: string,
      source_id: string,
      body: Schema<"ExtractRequest">,
    ) =>
      unwrap(
        await api.POST(`${P}/{source_id}/extraction-runs`, {
          params: { path: { learner_id, source_id } },
          body,
        }),
      ),
    pdfRuns: async (learner_id: string, source_id: string, cursor?: string) =>
      unwrap(
        await api.GET(`${P}/{source_id}/extraction-runs`, {
          params: {
            path: { learner_id, source_id },
            query: { cursor, limit: 25 },
          },
        }),
      ),
    pdfResult: async (learner_id: string, source_id: string, run_id: string) =>
      unwrap(
        await api.GET(`${P}/{source_id}/extraction-runs/{run_id}`, {
          params: {
            path: { learner_id, source_id, run_id },
            query: { include_evidence: true },
          },
        }),
      ),
    archivePdf: async (
      learner_id: string,
      source_id: string,
      row_version: number,
    ) =>
      unwrap(
        await api.POST(`${P}/{source_id}/archive`, {
          params: { path: { learner_id, source_id } },
          body: { row_version },
        }),
      ),
  };
}
