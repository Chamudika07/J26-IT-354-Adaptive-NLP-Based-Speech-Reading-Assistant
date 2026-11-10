import { useRef, useState } from "react";
import { router, useLocalSearchParams } from "expo-router";
import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import type { z } from "zod";
import type { Schema } from "@j26/api-client";
import { useApp } from "../../../src/providers";
import { textForm } from "../../../src/forms";
import {
  Button,
  Card,
  ErrorNotice,
  Field,
  Loading,
  Message,
  Screen,
  Title,
} from "../../../src/ui";

export default function LearnerMaterials() {
  const { learnerId } = useLocalSearchParams<{ learnerId: string }>();
  const { api } = useApp();
  const cache = useQueryClient();
  const me = useQuery({ queryKey: ["me"], queryFn: api.me });
  const list = useInfiniteQuery({
    queryKey: ["materials", learnerId],
    queryFn: ({ pageParam }) => api.materials(learnerId, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
  });
  const saved = useRef<Schema<"MaterialSummary"> | null>(null);
  const [hasSaved, setHasSaved] = useState(false);
  const { control, handleSubmit, reset } = useForm<z.infer<typeof textForm>>({
    resolver: zodResolver(textForm),
    defaultValues: { title: "", text: "" },
  });
  const open = (material: Schema<"MaterialSummary">, runId?: string) =>
    router.push({
      pathname: "/materials/[learnerId]/[materialId]",
      params: {
        learnerId,
        materialId: material.id,
        revisionId: material.latest_revision.id,
        ...(runId ? { runId } : {}),
      },
    });
  const create = useMutation({
    mutationFn: async (values: z.infer<typeof textForm>) => {
      // A processing failure must never create a second material on retry.
      if (!saved.current) {
        saved.current = await api.create(learnerId, {
          ...values,
          language_tag: "en",
        });
        setHasSaved(true);
        void cache.invalidateQueries({ queryKey: ["materials", learnerId] });
      }
      const material = saved.current;
      const run = await api.process({
        learner_id: learnerId,
        material_id: material.id,
        revision_id: material.latest_revision.id,
      });
      return { material, run };
    },
    onSuccess: ({ material, run }) => {
      saved.current = null;
      setHasSaved(false);
      reset();
      open(material, run.id);
    },
  });
  return (
    <Screen>
      <Title>Reading materials</Title>
      <Message>English passages and their text measurements.</Message>
      <Button
        title="Learner profile & preferences"
        secondary
        onPress={() =>
          router.push({
            pathname: "/profiles/[learnerId]",
            params: { learnerId },
          })
        }
      />
      <Button
        title="Reading assessments & history"
        secondary
        onPress={() =>
          router.push({
            pathname: "/assessments/[learnerId]",
            params: { learnerId },
          })
        }
      />
      <Button
        title="PDF sources & extraction"
        secondary
        onPress={() =>
          router.push({ pathname: "/pdf/[learnerId]", params: { learnerId } })
        }
      />
      {list.isPending && <Loading />}
      <ErrorNotice error={list.error} />
      {me.data?.roles.includes("educator") && !list.isError && (
        <Card>
          <Title>Add a passage</Title>
          <Message>
            Creating and processing requires a current instructor grant. The
            server verifies access for this learner.
          </Message>
          <Controller
            control={control}
            name="title"
            render={({ field, fieldState }) => (
              <Field
                label="Title"
                value={field.value}
                onChangeText={field.onChange}
                onBlur={field.onBlur}
                maxLength={200}
                error={fieldState.error?.message}
                editable={!create.isPending && !hasSaved}
              />
            )}
          />
          <Controller
            control={control}
            name="text"
            render={({ field, fieldState }) => (
              <Field
                label="English passage"
                multiline
                value={field.value}
                onChangeText={field.onChange}
                onBlur={field.onBlur}
                maxLength={50000}
                error={fieldState.error?.message}
                editable={!create.isPending && !hasSaved}
              />
            )}
          />
          <ErrorNotice error={create.error} />
          {hasSaved && (
            <Message>
              Your text is saved. Retry processing or open the saved material
              below.
            </Message>
          )}
          <Button
            title={
              create.isPending
                ? "Saving / processing…"
                : hasSaved
                  ? "Retry processing saved text"
                  : "Create & process text"
            }
            disabled={create.isPending}
            onPress={handleSubmit((values) => create.mutate(values))}
          />
          {hasSaved && (
            <Button
              title="Open saved material"
              secondary
              disabled={create.isPending}
              onPress={() => {
                if (saved.current) open(saved.current);
              }}
            />
          )}
        </Card>
      )}
      {!list.isError &&
        list.data?.pages
          .flatMap((page) => page.items)
          .map((material) => (
            <Card key={material.id}>
              <Message>{material.latest_revision.title}</Message>
              <Message>
                Revision {material.latest_revision.revision_number} ·{" "}
                {material.latest_revision.language_tag.toUpperCase()}
              </Message>
              <Button
                title="Open material & results"
                onPress={() => open(material)}
              />
            </Card>
          ))}
      {list.data?.pages[0]?.items.length === 0 && (
        <Message>No reading materials yet.</Message>
      )}
      {list.hasNextPage && (
        <Button
          title="More materials"
          disabled={list.isFetchingNextPage}
          onPress={() => void list.fetchNextPage()}
        />
      )}
      <Button
        title="Refresh materials"
        secondary
        disabled={list.isFetching}
        onPress={() => void list.refetch()}
      />
    </Screen>
  );
}
