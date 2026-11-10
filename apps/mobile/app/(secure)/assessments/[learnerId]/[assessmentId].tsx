import { Alert } from "react-native";
import { useLocalSearchParams } from "expo-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useApp } from "../../../../src/providers";
import { WorkflowForm } from "../../../../src/workflow-form";
import {
  completionForm,
  observationFields,
} from "../../../../src/learning-forms";
import {
  Button,
  Card,
  ErrorNotice,
  Loading,
  Message,
  Screen,
  Title,
} from "../../../../src/ui";
export default function Assessment() {
  const { learnerId, assessmentId } = useLocalSearchParams<{
    learnerId: string;
    assessmentId: string;
  }>();
  const { api } = useApp();
  const cache = useQueryClient();
  const key = ["assessment", learnerId, assessmentId];
  const q = useQuery({
    queryKey: key,
    queryFn: () => api.assessment(learnerId, assessmentId),
    refetchOnWindowFocus: false,
  });
  const a = q.data;
  const abandon = useMutation({
    mutationFn: (version: number) =>
      api.abandonAssessment(learnerId, assessmentId, version),
    onSuccess: async (value) => {
      cache.setQueryData(key, value);
      await cache.invalidateQueries({ queryKey: ["assessments", learnerId] });
    },
  });
  return (
    <Screen>
      <Title>Assessment details</Title>
      {q.isPending && <Loading />}
      <ErrorNotice error={q.error || abandon.error} context="assessment" />
      {a && !q.isError && (
        <>
          <Card>
            <Title>{a.material.title}</Title>
            <Message>
              Status: {a.status} · Material version {a.material.version}
            </Message>
            <Message>
              Started: {new Date(a.started_at).toLocaleString()}
            </Message>
            <Message>
              Mode: instructor observed · Protocol: {a.protocol_version}
            </Message>
          </Card>
          {"passage_text" in a.material && (
            <Card>
              <Title>Administration</Title>
              <Message>{a.material.administration_instructions}</Message>
              <Message>{a.material.passage_text}</Message>
              {a.material.comprehension_prompt_text && (
                <>
                  <Message>
                    Questions: {a.material.comprehension_prompt_text}
                  </Message>
                  <Message>
                    Rubric: {a.material.comprehension_rubric_text}
                  </Message>
                </>
              )}
            </Card>
          )}
          {a.status === "started" && "passage_text" in a.material && (
            <Card>
              <Title>Record observations</Title>
              <Message>
                Enter observed counts, including zero when observed. Leave
                unfamiliar words blank if unmeasured. Submission is permanent.
              </Message>
              <WorkflowForm
                key={a.row_version}
                context="assessment"
                schema={completionForm(
                  a.material.comprehension_question_count,
                  a.material.word_count,
                )}
                fields={[
                  ...observationFields.map(([name, label]) => ({
                    name,
                    label,
                    numeric: true,
                  })),
                  ...(a.material.comprehension_question_count
                    ? [
                        {
                          name: "comprehension_correct",
                          label: `Correct answers (of ${a.material.comprehension_question_count})`,
                          numeric: true,
                        },
                      ]
                    : []),
                ]}
                submitLabel="Complete assessment"
                onSubmit={async (body) => {
                  const confirmed = await new Promise<boolean>((resolve) =>
                    Alert.alert(
                      "Submit observations?",
                      "Completed observations cannot be edited.",
                      [
                        {
                          text: "Cancel",
                          style: "cancel",
                          onPress: () => resolve(false),
                        },
                        { text: "Complete", onPress: () => resolve(true) },
                      ],
                      { cancelable: false },
                    ),
                  );
                  if (confirmed) {
                    cache.setQueryData(
                      key,
                      await api.completeAssessment(learnerId, assessmentId, {
                        ...body,
                        row_version: a.row_version,
                      }),
                    );
                    await cache.invalidateQueries({
                      queryKey: ["assessments", learnerId],
                    });
                  }
                }}
              />
              <Button
                title="Abandon assessment"
                secondary
                disabled={abandon.isPending}
                onPress={() =>
                  Alert.alert(
                    "Abandon assessment?",
                    "This session cannot be resumed.",
                    [
                      { text: "Cancel", style: "cancel" },
                      {
                        text: "Abandon",
                        style: "destructive",
                        onPress: () => abandon.mutate(a.row_version),
                      },
                    ],
                  )
                }
              />
            </Card>
          )}
          {a.status === "started" && !("passage_text" in a.material) && (
            <Message>
              Only the administering instructor with current access may complete
              or abandon this session.
            </Message>
          )}
          {a.result && (
            <Card>
              <Title>Educational results</Title>
              <Message>
                Duration: {a.result.reading_duration_seconds} seconds
              </Message>
              <Message>
                Words attempted: {a.result.attempted_word_count} · Correct:{" "}
                {a.result.correct_word_count}
              </Message>
              <Message>
                Attempted words/minute: {a.result.attempted_words_per_minute}
              </Message>
              <Message>
                Correct words/minute: {a.result.words_correct_per_minute}
              </Message>
              <Message>
                Accuracy:{" "}
                {a.result.attempted_word_accuracy_percentage ??
                  "Not measurable"}
                {a.result.attempted_word_accuracy_percentage !== null
                  ? "%"
                  : ""}
              </Message>
              <Message>
                Incorrect attempts:{" "}
                {a.result.incorrect_attempt_percentage ?? "Not measurable"}
              </Message>
              <Message>
                Comprehension:{" "}
                {a.result.comprehension_percentage ?? "Not measured"}
              </Message>
              {observationFields
                .filter(
                  ([n]) =>
                    ![
                      "reading_duration_ms",
                      "attempted_word_count",
                      "correct_word_count",
                    ].includes(n),
                )
                .map(([n, label]) => (
                  <Message key={n}>
                    {label}: {a.result?.[n] ?? "Not measured"}
                  </Message>
                ))}
              <Message>Scoring: {a.result.scoring_version}</Message>
              <Message>These observations are not a diagnosis.</Message>
            </Card>
          )}
        </>
      )}
      <Button
        title="Reload assessment"
        secondary
        disabled={q.isFetching}
        onPress={() => void q.refetch()}
      />
    </Screen>
  );
}
