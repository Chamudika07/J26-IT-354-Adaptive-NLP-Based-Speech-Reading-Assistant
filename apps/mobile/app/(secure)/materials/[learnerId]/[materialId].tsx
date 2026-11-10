import { useState } from "react";
import { router, useLocalSearchParams } from "expo-router";
import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useApp } from "../../../../src/providers";
import {
  Button,
  Card,
  ErrorNotice,
  Loading,
  Message,
  Screen,
  Title,
} from "../../../../src/ui";

export default function Results() {
  const { learnerId, materialId, revisionId, runId } = useLocalSearchParams<{
    learnerId: string;
    materialId: string;
    revisionId?: string;
    runId?: string;
  }>();
  const { api } = useApp();
  const cache = useQueryClient();
  const [selected, select] = useState(runId);
  const me = useQuery({ queryKey: ["me"], queryFn: api.me });
  const material = useQuery({
    queryKey: ["material", learnerId, materialId],
    queryFn: () => api.material(learnerId, materialId),
  });
  const revision = revisionId ?? material.data?.latest_revision.id;
  const sourceRevision = useQuery({
    queryKey: ["revision", learnerId, materialId, revision],
    queryFn: () => api.revision(learnerId, materialId, revision!),
    enabled: !!revision && material.isSuccess,
  });
  const path = {
    learner_id: learnerId,
    material_id: materialId,
    revision_id: revision ?? "",
  };
  const key = ["runs", learnerId, materialId, revision];
  const runs = useInfiniteQuery({
    queryKey: key,
    queryFn: ({ pageParam }) => api.runs(path, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    enabled: !!revision && material.isSuccess,
  });
  const activeRun = selected ?? runs.data?.pages[0]?.items[0]?.id;
  const result = useQuery({
    queryKey: ["result", learnerId, materialId, revision, activeRun],
    queryFn: () => api.result(path, activeRun!),
    enabled: !!activeRun && !!revision && material.isSuccess,
    refetchInterval: (query) =>
      query.state.data?.status === "running" ? 3000 : false,
  });
  const process = useMutation({
    mutationFn: () => api.process(path),
    onSuccess: (run) => {
      select(run.id);
      void cache.invalidateQueries({ queryKey: key });
      void cache.invalidateQueries({
        queryKey: ["result", learnerId, materialId, revision, run.id],
      });
    },
  });
  const profile = result.data?.profile;
  return (
    <Screen>
      <Title>Text results</Title>
      <Button
        title="View material, revisions & archive"
        secondary
        onPress={() =>
          router.push({
            pathname: "/materials/manage/[learnerId]/[materialId]",
            params: { learnerId, materialId },
          })
        }
      />
      {material.isPending && <Loading />}
      <ErrorNotice error={material.error} />
      {material.data && !material.isError && (
        <Card>
          <Message>
            {sourceRevision.data?.title ?? material.data.latest_revision.title}
          </Message>
          {sourceRevision.data && (
            <Message>Revision {sourceRevision.data.revision_number}</Message>
          )}
          <Message>
            These measurements describe the text. They are not a diagnosis or a
            measure of learner ability.
          </Message>
        </Card>
      )}
      {(runs.isFetching || result.isFetching) && <Loading />}
      <ErrorNotice error={runs.error || result.error || process.error} />
      {!result.isError && !material.isError && result.data && (
        <Card>
          <Message>Status: {result.data.status}</Message>
          <Message>Pipeline: {result.data.pipeline_version}</Message>
          {result.data.status === "failed" && (
            <Message>
              Processing did not complete ({result.data.failure_code}). An
              instructor can retry.
            </Message>
          )}
          {profile && (
            <>
              <Title>{profile.length_load.word_count} words</Title>
              <Message>
                {profile.length_load.sentence_count} sentences ·{" "}
                {profile.length_load.character_count} characters
              </Message>
              <Message>
                Unique words:{" "}
                {profile.word_form_characteristics.unique_word_count}
              </Message>
              <Message>
                Average word length:{" "}
                {profile.word_form_characteristics.average_word_length}
              </Message>
              <Message>
                Longest word:{" "}
                {profile.word_form_characteristics.maximum_word_length} letters
              </Message>
              <Message>
                Lexical diversity:{" "}
                {profile.word_form_characteristics.lexical_diversity}
              </Message>
              <Message>
                Average sentence:{" "}
                {profile.sentence_structure.average_sentence_length} words
              </Message>
              <Message>
                Longest sentence:{" "}
                {profile.sentence_structure.maximum_sentence_length} words
              </Message>
              <Message>Vocabulary difficulty: not evaluated</Message>
              <Message>
                Completed: {new Date(profile.completed_at).toLocaleString()}
              </Message>
            </>
          )}
        </Card>
      )}
      {me.data?.roles.includes("educator") &&
        material.isSuccess &&
        !material.data.archived_at && (
          <Button
            title={process.isPending ? "Processing…" : "Process this revision"}
            disabled={process.isPending || !revision}
            onPress={() => process.mutate()}
          />
        )}
      {runs.data?.pages[0]?.items.length === 0 && (
        <Message>This revision has no processing results yet.</Message>
      )}
      {runs.data?.pages
        .flatMap((page) => page.items)
        .map((run) => (
          <Button
            key={run.id}
            title={`Attempt ${run.attempt_number} · ${run.status}`}
            secondary
            onPress={() => select(run.id)}
          />
        ))}
      {runs.hasNextPage && (
        <Button
          title="More attempts"
          disabled={runs.isFetchingNextPage}
          onPress={() => void runs.fetchNextPage()}
        />
      )}
      {!result.isError &&
        !material.isError &&
        result.data?.sentences?.map((sentence) => (
          <Card key={sentence.ordinal}>
            <Message>
              Sentence {sentence.ordinal} · {sentence.word_count} words
            </Message>
            <Message>{sentence.normalized_text}</Message>
          </Card>
        ))}
      <Button
        title="Refresh results"
        secondary
        onPress={() => {
          void material.refetch();
          if (revision) void runs.refetch();
          if (activeRun && revision) void result.refetch();
        }}
      />
    </Screen>
  );
}
