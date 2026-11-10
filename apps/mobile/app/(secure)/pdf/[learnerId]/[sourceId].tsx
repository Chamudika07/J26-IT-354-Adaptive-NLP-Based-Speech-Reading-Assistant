import { useState } from "react";
import { Alert } from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { Schema } from "@j26/api-client";
import { useApp } from "../../../../src/providers";
import { PagedList } from "../../../../src/paged-list";
import {
  Button,
  Card,
  ErrorNotice,
  Loading,
  Message,
  Screen,
  Title,
} from "../../../../src/ui";
export default function PdfDetail() {
  const { learnerId, sourceId, runId } = useLocalSearchParams<{
    learnerId: string;
    sourceId: string;
    runId?: string;
  }>();
  const { api } = useApp();
  const cache = useQueryClient();
  const [selected, select] = useState(runId);
  const me = useQuery({ queryKey: ["me"], queryFn: api.me });
  const key = ["pdf-source", learnerId, sourceId];
  const source = useQuery({
    queryKey: key,
    queryFn: () => api.pdfSource(learnerId, sourceId),
    refetchOnWindowFocus: false,
  });
  const s = source.data;
  const material = useQuery({
    queryKey: ["material", learnerId, s?.material_id],
    queryFn: () => api.material(learnerId, s!.material_id!),
    enabled: !!s?.material_id && source.isSuccess,
    refetchOnWindowFocus: false,
  });
  const activeRun = selected ?? s?.latest_extraction?.id;
  const result = useQuery({
    queryKey: ["pdf-result", learnerId, sourceId, activeRun],
    queryFn: () => api.pdfResult(learnerId, sourceId, activeRun!),
    enabled: !!activeRun && source.isSuccess,
    refetchInterval: (q) => (q.state.data?.status === "running" ? 3000 : false),
  });
  const r = result.data;
  const extract = useMutation({
    mutationFn: () =>
      api.extractPdf(
        learnerId,
        sourceId,
        s?.material_id ? { row_version: material.data!.row_version } : {},
      ),
    onSuccess: async (value) => {
      select(value.id);
      await cache.invalidateQueries({ queryKey: key });
      await cache.invalidateQueries({
        queryKey: ["pdf-runs", learnerId, sourceId],
      });
      await cache.invalidateQueries({
        queryKey: ["pdf-result", learnerId, sourceId],
      });
      await cache.invalidateQueries({ queryKey: ["materials", learnerId] });
    },
  });
  const archive = useMutation({
    mutationFn: (version: number) =>
      api.archivePdf(learnerId, sourceId, version),
    onSuccess: async () => {
      await cache.invalidateQueries({ queryKey: ["pdf-sources", learnerId] });
      router.replace({ pathname: "/pdf/[learnerId]", params: { learnerId } });
    },
  });
  return (
    <Screen>
      <Title>PDF extraction</Title>
      {source.isPending && <Loading />}
      <ErrorNotice
        error={
          source.error ||
          result.error ||
          extract.error ||
          archive.error ||
          material.error
        }
        context="pdf"
      />
      {s && !source.isError && (
        <>
          <Card>
            <Title>{s.title}</Title>
            <Message>
              {s.byte_count} bytes · {s.language_tag.toUpperCase()}
            </Message>
            <Message>
              Created: {new Date(s.created_at).toLocaleString()}
            </Message>
          </Card>
          {me.data?.roles.includes("educator") && !s.archived_at && (
            <>
              <Button
                title={
                  extract.isPending ? "Extracting…" : "Run / retry extraction"
                }
                disabled={
                  extract.isPending ||
                  archive.isPending ||
                  (!!s.material_id && !material.isSuccess)
                }
                onPress={() => extract.mutate()}
              />
              <Button
                title="Archive PDF source"
                secondary
                disabled={archive.isPending || extract.isPending}
                onPress={() =>
                  Alert.alert(
                    "Archive this PDF source?",
                    "It will leave the active source list. Previously created reading materials are retained.",
                    [
                      { text: "Cancel", style: "cancel" },
                      {
                        text: "Archive",
                        style: "destructive",
                        onPress: () => archive.mutate(s.row_version),
                      },
                    ],
                  )
                }
              />
            </>
          )}
          {result.isFetching && <Loading />}
          {r && !result.isError && (
            <Card>
              <Title>Status: {r.status}</Title>
              {r.outcome_code && <Message>Outcome: {r.outcome_code}</Message>}
              {r.status === "ocr_required" && (
                <Message>
                  This PDF needs OCR. No public OCR engine or review action is
                  available; extraction has not produced approved reading text.
                </Message>
              )}
              {r.status === "needs_review" && (
                <Message>
                  This extraction needs review. The backend does not expose a
                  public review/acceptance API.
                </Message>
              )}
              {r.status === "failed" && (
                <Message>
                  Extraction failed. Review the outcome and retry if
                  appropriate.
                </Message>
              )}
              <Message>
                Attempt {r.attempt_number} · Extractor {r.extractor_name}{" "}
                {r.extractor_package_version}
              </Message>
              <Message>Extraction version: {r.extraction_version}</Message>
              <Message>
                Pages: {r.total_page_count ?? "Not available"} · Words:{" "}
                {r.lexical_word_count ?? "Not available"} · Characters:{" "}
                {r.assembled_character_count ?? "Not available"}
              </Message>
              <Message>
                Pages with lexical text:{" "}
                {r.pages_with_lexical_text ?? "Not available"} · Coverage:{" "}
                {r.lexical_page_coverage ?? "Not available"}
              </Message>
              {r.assembled_text && (
                <>
                  <Title>Extracted text</Title>
                  <Message>{r.assembled_text}</Message>
                </>
              )}
              {r.material_id && r.revision_id && (
                <Button
                  title="Open extracted reading material"
                  onPress={() =>
                    router.push({
                      pathname: "/materials/[learnerId]/[materialId]",
                      params: {
                        learnerId,
                        materialId: r.material_id!,
                        revisionId: r.revision_id!,
                      },
                    })
                  }
                />
              )}
              {r.pages?.map((page) => (
                <Card key={page.page_number}>
                  <Message>
                    Page {page.page_number}: {page.text_status},{" "}
                    {page.lexical_word_count} words
                  </Message>
                  <Message>
                    Characters: {page.raw_character_count} · Source span{" "}
                    {page.text_start}–{page.text_end}
                  </Message>
                  <Message>
                    Warnings: {page.warning_codes.join(", ") || "None"}
                  </Message>
                </Card>
              ))}
            </Card>
          )}
          <Title>Extraction history</Title>
          <PagedList<
            Schema<"app__modules__reading_materials__pdf__schemas__RunSummary">
          >
            queryKey={["pdf-runs", learnerId, sourceId]}
            load={(c) => api.pdfRuns(learnerId, sourceId, c)}
            context="pdf"
            render={(run) => (
              <Button
                key={run.id}
                title={`Attempt ${run.attempt_number} · ${run.status}`}
                secondary
                onPress={() => select(run.id)}
              />
            )}
          />
        </>
      )}
      <Button
        title="Reload source & result"
        secondary
        disabled={source.isFetching}
        onPress={() => {
          void source.refetch();
          if (activeRun) void result.refetch();
          if (s?.material_id) void material.refetch();
        }}
      />
    </Screen>
  );
}
