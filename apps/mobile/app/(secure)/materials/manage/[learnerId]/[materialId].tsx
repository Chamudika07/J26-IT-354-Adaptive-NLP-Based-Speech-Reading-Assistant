import { useState } from "react";
import { Alert } from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { Schema } from "@j26/api-client";
import { useApp } from "../../../../../src/providers";
import { PagedList } from "../../../../../src/paged-list";
import { WorkflowForm } from "../../../../../src/workflow-form";
import { textForm } from "../../../../../src/forms";
import {
  Button,
  Card,
  ErrorNotice,
  Loading,
  Message,
  Screen,
  Title,
} from "../../../../../src/ui";
export default function ManageMaterial() {
  const { learnerId, materialId } = useLocalSearchParams<{
    learnerId: string;
    materialId: string;
  }>();
  const { api } = useApp();
  const cache = useQueryClient();
  const [selected, select] = useState<string>();
  const [draft, setDraft] = useState<{
    version: number;
    title: string;
    text: string;
  }>();
  const me = useQuery({ queryKey: ["me"], queryFn: api.me });
  const key = ["material", learnerId, materialId];
  const material = useQuery({
    queryKey: key,
    queryFn: () => api.material(learnerId, materialId),
    refetchOnWindowFocus: false,
  });
  const m = material.data;
  const revisionId = selected ?? m?.latest_revision.id;
  const revision = useQuery({
    queryKey: ["revision", learnerId, materialId, revisionId],
    queryFn: () => api.revision(learnerId, materialId, revisionId!),
    enabled: !!revisionId && material.isSuccess,
  });
  const archive = useMutation({
    mutationFn: (version: number) =>
      api.archiveMaterial(learnerId, materialId, version),
    onSuccess: async (value) => {
      cache.setQueryData(key, value);
      setDraft(undefined);
      await cache.invalidateQueries({ queryKey: ["materials", learnerId] });
    },
  });
  return (
    <Screen>
      <Title>Material & revisions</Title>
      {material.isPending && <Loading />}
      <ErrorNotice error={material.error || revision.error || archive.error} />
      {m && !material.isError && (
        <>
          <Card>
            <Title>{m.latest_revision.title}</Title>
            <Message>
              {m.archived_at ? "Archived" : "Active"} · Current version{" "}
              {m.row_version}
            </Message>
            <Message>
              Created: {new Date(m.created_at).toLocaleString()}
            </Message>
          </Card>
          <PagedList<Schema<"RevisionSummary">>
            queryKey={["revisions", learnerId, materialId]}
            load={(c) => api.revisions(learnerId, materialId, c)}
            render={(r) => (
              <Card key={r.id}>
                <Message>
                  Revision {r.revision_number}: {r.title}
                </Message>
                <Message>
                  {r.source_kind} · {new Date(r.created_at).toLocaleString()}
                </Message>
                <Button
                  title="View original revision"
                  secondary
                  onPress={() => select(r.id)}
                />
                <Button
                  title="Processing results"
                  onPress={() =>
                    router.push({
                      pathname: "/materials/[learnerId]/[materialId]",
                      params: { learnerId, materialId, revisionId: r.id },
                    })
                  }
                />
              </Card>
            )}
          />
          {revision.isPending && <Loading />}
          {revision.data && !revision.isError && (
            <Card>
              <Title>
                Original text · revision {revision.data.revision_number}
              </Title>
              <Message>{revision.data.original_text}</Message>
              {me.data?.roles.includes("educator") && !m.archived_at && (
                <Button
                  title="Create a new revision from this text"
                  onPress={() =>
                    setDraft({
                      version: m.row_version,
                      title: revision.data.title,
                      text: revision.data.original_text,
                    })
                  }
                />
              )}
            </Card>
          )}
          {draft && !m.archived_at && (
            <Card>
              <Title>New immutable revision</Title>
              <WorkflowForm
                schema={textForm}
                context="reading"
                initial={{ title: draft.title, text: draft.text }}
                fields={[
                  { name: "title", label: "Title" },
                  { name: "text", label: "English passage", multiline: true },
                ]}
                submitLabel="Save new revision"
                onSubmit={async (body) => {
                  const updated = await api.revise(learnerId, materialId, {
                    ...body,
                    language_tag: "en",
                    row_version: draft.version,
                  });
                  cache.setQueryData(key, updated);
                  select(updated.latest_revision.id);
                  setDraft(undefined);
                  await cache.invalidateQueries({
                    queryKey: ["revisions", learnerId, materialId],
                  });
                  await cache.invalidateQueries({
                    queryKey: ["materials", learnerId],
                  });
                }}
              />
              <Button
                title="Cancel revision"
                secondary
                onPress={() => setDraft(undefined)}
              />
            </Card>
          )}
          {me.data?.roles.includes("educator") && !m.archived_at && (
            <Button
              title="Archive reading material"
              disabled={archive.isPending}
              onPress={() =>
                Alert.alert(
                  "Archive this material?",
                  "It will leave the active list. Revisions and results are retained.",
                  [
                    { text: "Cancel", style: "cancel" },
                    {
                      text: "Archive",
                      style: "destructive",
                      onPress: () => archive.mutate(m.row_version),
                    },
                  ],
                )
              }
            />
          )}
        </>
      )}
      <Button
        title="Reload material"
        secondary
        disabled={material.isFetching}
        onPress={() => {
          setDraft(undefined);
          void material.refetch();
        }}
      />
    </Screen>
  );
}
