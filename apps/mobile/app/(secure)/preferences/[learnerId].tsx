import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocalSearchParams } from "expo-router";
import { useApp } from "../../../src/providers";
import { WorkflowForm } from "../../../src/workflow-form";
import { preferenceForm } from "../../../src/learning-forms";
import {
  Button,
  Card,
  ErrorNotice,
  Loading,
  Message,
  Screen,
  Title,
} from "../../../src/ui";
export default function Preferences() {
  const { learnerId } = useLocalSearchParams<{ learnerId: string }>();
  const { api } = useApp();
  const cache = useQueryClient();
  const key = ["preferences", learnerId];
  const q = useQuery({
    queryKey: key,
    queryFn: () => api.preferences(learnerId),
    refetchOnWindowFocus: false,
  });
  const p = q.data;
  return (
    <Screen>
      <Title>Reading preferences</Title>
      <Message>
        Blank or inherited values use application/device defaults. Only the
        learner or a guardian manager may save changes.
      </Message>
      {q.isPending && <Loading />}
      <ErrorNotice error={q.error} context="preferences" />
      {p && !q.isError && (
        <Card>
          <WorkflowForm
            key={p.row_version}
            schema={preferenceForm}
            context="preferences"
            initial={{
              preferred_language_tag: p.preferred_language_tag ?? "",
              text_scale: String(p.text_scale ?? ""),
              line_spacing: String(p.line_spacing ?? ""),
              theme: p.theme ?? "",
              reduce_motion:
                p.reduce_motion === null ? "" : String(p.reduce_motion),
            }}
            fields={[
              {
                name: "preferred_language_tag",
                label: "Preferred language tag (optional)",
              },
              {
                name: "text_scale",
                label: "Text scale (0.75–3, optional)",
                numeric: true,
              },
              {
                name: "line_spacing",
                label: "Line spacing (1–3, optional)",
                numeric: true,
              },
              {
                name: "theme",
                label: "Theme",
                options: [
                  { label: "Inherit", value: "" },
                  { label: "System", value: "system" },
                  { label: "Light", value: "light" },
                  { label: "Dark", value: "dark" },
                  { label: "High contrast", value: "high_contrast" },
                ],
              },
              {
                name: "reduce_motion",
                label: "Reduce motion",
                options: [
                  { label: "Inherit", value: "" },
                  { label: "Yes", value: "true" },
                  { label: "No", value: "false" },
                ],
              },
            ]}
            submitLabel="Save preferences"
            onSubmit={async (body) => {
              cache.setQueryData(
                key,
                await api.updatePreferences(learnerId, {
                  ...body,
                  row_version: p.row_version,
                }),
              );
            }}
          />
        </Card>
      )}
      <Button
        title="Reload preferences"
        secondary
        disabled={q.isFetching}
        onPress={() => void q.refetch()}
      />
    </Screen>
  );
}
