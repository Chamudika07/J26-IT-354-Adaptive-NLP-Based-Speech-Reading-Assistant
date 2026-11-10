import { useState } from "react";
import { router, useLocalSearchParams } from "expo-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { Schema } from "@j26/api-client";
import { useApp } from "../../../../src/providers";
import { PagedList } from "../../../../src/paged-list";
import {
  Button,
  Card,
  ErrorNotice,
  Message,
  Screen,
  Title,
} from "../../../../src/ui";
export default function Assessments() {
  const { learnerId } = useLocalSearchParams<{ learnerId: string }>();
  const { api } = useApp();
  const cache = useQueryClient();
  const [tab, setTab] = useState<"history" | "catalog">("history");
  const me = useQuery({ queryKey: ["me"], queryFn: api.me });
  const open = (id: string) =>
    router.push({
      pathname: "/assessments/[learnerId]/[assessmentId]",
      params: { learnerId, assessmentId: id },
    });
  const start = useMutation({
    mutationFn: (material_id: string) =>
      api.startAssessment(learnerId, { material_id }),
    onSuccess: async (a) => {
      await cache.invalidateQueries({ queryKey: ["assessments", learnerId] });
      open(a.id);
    },
  });
  return (
    <Screen>
      <Title>Reading assessments</Title>
      <Message>
        Instructor-observed educational measurements, not diagnoses.
      </Message>
      <Button
        title="Assessment history"
        secondary={tab !== "history"}
        onPress={() => setTab("history")}
      />
      {me.data?.roles.includes("educator") && (
        <Button
          title="Assessment material catalog"
          secondary={tab !== "catalog"}
          onPress={() => setTab("catalog")}
        />
      )}
      <ErrorNotice error={start.error} context="assessment" />
      {tab === "history" ? (
        <PagedList<Schema<"AssessmentHistoryItem">>
          queryKey={["assessments", learnerId]}
          load={(c) => api.assessments(learnerId, c)}
          context="assessment"
          render={(a) => (
            <Card key={a.id}>
              <Message>
                {a.material.title} · {a.status}
              </Message>
              <Message>{new Date(a.started_at).toLocaleString()}</Message>
              <Button title="View assessment" onPress={() => open(a.id)} />
            </Card>
          )}
        />
      ) : (
        <>
          <Message>
            Only an assigned instructor can start. If a request fails, refresh
            history before starting again.
          </Message>
          <PagedList<Schema<"AssessmentMaterialSummary">>
            queryKey={["assessment-materials"]}
            load={api.assessmentMaterials}
            context="assessment"
            empty="No published assessment materials are available. Ask your administrator about approved material provisioning."
            render={(m) => (
              <Card key={m.id}>
                <Title>{m.title}</Title>
                <Message>
                  Version {m.version} · {m.word_count} words ·{" "}
                  {m.comprehension_question_count} questions
                </Message>
                <Button
                  title="Start observed assessment"
                  disabled={start.isPending}
                  onPress={() => start.mutate(m.id)}
                />
              </Card>
            )}
          />
        </>
      )}
    </Screen>
  );
}
