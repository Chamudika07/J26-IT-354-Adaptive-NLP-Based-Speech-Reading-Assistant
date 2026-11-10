import { useState } from "react";
import { Alert, Text } from "react-native";
import { useQuery } from "@tanstack/react-query";
import type { Schema } from "@j26/api-client";
import { useApp } from "../../src/providers";
import { adminApi } from "../../src/api/admin";
import {
  educatorForm,
  learnerForm,
  grantForm,
  revokeForm,
} from "../../src/admin-forms";
import { WorkflowForm } from "../../src/workflow-form";
import {
  Button,
  Card,
  ErrorNotice,
  Loading,
  Message,
  Screen,
  Title,
} from "../../src/ui";

export default function Administrator() {
  const { api, session } = useApp();
  const admin = adminApi(session);
  const me = useQuery({ queryKey: ["me"], queryFn: api.me });
  const [section, choose] = useState<
    "educator" | "learner" | "assign" | "revoke"
  >("educator");
  const [educator, setEducator] = useState<Schema<"AccountCreated">>();
  const [learner, setLearner] = useState<Schema<"LearnerCreated">>();
  const [grant, setGrant] = useState<Schema<"EducatorGrantRead">>();
  const [notice, setNotice] = useState("");
  if (me.isPending)
    return (
      <Screen>
        <Loading />
      </Screen>
    );
  if (me.isError)
    return (
      <Screen>
        <ErrorNotice error={me.error} />
        <Button title="Retry" onPress={() => void me.refetch()} />
      </Screen>
    );
  if (!me.data.roles.includes("administrator"))
    return (
      <Screen>
        <Message>Administrator access is required.</Message>
      </Screen>
    );
  return (
    <Screen>
      <Title>Administrator dashboard</Title>
      <Message>
        Create accounts and assign explicit access. These actions do not grant
        you learner reading access.
      </Message>
      {(
        [
          ["educator", "Create educator account"],
          ["learner", "Create synthetic learner"],
          ["assign", "Assign educator to learner"],
          ["revoke", "Revoke educator access"],
        ] as const
      ).map(([key, title]) => (
        <Button
          key={key}
          title={title}
          secondary={section !== key}
          onPress={() => {
            choose(key);
            setNotice("");
          }}
        />
      ))}
      <Card>
        {section === "educator" && (
          <WorkflowForm
            schema={educatorForm}
            context="admin"
            resetOnSuccess
            fields={[
              { name: "login_handle", label: "Educator login handle" },
              {
                name: "password",
                label: "New password (15–128 characters)",
                secret: true,
              },
              { name: "confirm", label: "Confirm password", secret: true },
            ]}
            submitLabel="Create educator"
            onSubmit={async (body) => {
              setEducator(await admin.createEducator(body));
              setNotice(
                "Educator created. Save the ID and share credentials privately.",
              );
            }}
          />
        )}
        {section === "learner" && (
          <WorkflowForm
            schema={learnerForm}
            context="admin"
            resetOnSuccess
            fields={[
              { name: "display_name", label: "Synthetic learner display name" },
            ]}
            submitLabel="Create learner"
            onSubmit={async (body) => {
              setLearner(await admin.createLearner(body));
              setNotice("Synthetic learner created. Assign an educator next.");
            }}
          />
        )}
        {section === "assign" && (
          <WorkflowForm
            key={`assign-${educator?.user_id}-${learner?.id}`}
            schema={grantForm}
            context="admin"
            initial={{
              learner_id: learner?.id ?? "",
              educator_user_id: educator?.user_id ?? "",
              access_level: "instructor",
              expires_at: new Date(Date.now() + 7 * 86400000).toISOString(),
            }}
            fields={[
              { name: "learner_id", label: "Learner ID" },
              { name: "educator_user_id", label: "Educator user ID" },
              {
                name: "access_level",
                label: "Access level",
                options: [
                  { label: "Instructor — read and write", value: "instructor" },
                  { label: "Viewer — read only", value: "viewer" },
                ],
              },
              {
                name: "expires_at",
                label: "Expires at (ISO date and time with timezone)",
              },
            ]}
            submitLabel="Assign access"
            onSubmit={async ({ learner_id, ...body }) => {
              setGrant(await admin.assign(learner_id, body));
              setNotice(
                "Access assigned. Sign out, then sign in as the educator to open the learner.",
              );
            }}
          />
        )}
        {section === "revoke" && (
          <WorkflowForm
            key={`revoke-${grant?.id}`}
            schema={revokeForm}
            context="admin"
            initial={{
              learner_id: grant?.learner_id ?? learner?.id ?? "",
              grant_id: grant?.id ?? "",
            }}
            fields={[
              { name: "learner_id", label: "Learner ID" },
              { name: "grant_id", label: "Grant ID" },
            ]}
            submitLabel="Review revocation"
            onSubmit={async ({ learner_id, grant_id }) => {
              const confirm = await new Promise<boolean>((resolve) =>
                Alert.alert(
                  "Revoke educator access?",
                  "This assignment will stop granting access. Its history remains.",
                  [
                    {
                      text: "Cancel",
                      style: "cancel",
                      onPress: () => resolve(false),
                    },
                    {
                      text: "Revoke",
                      style: "destructive",
                      onPress: () => resolve(true),
                    },
                  ],
                  { cancelable: false },
                ),
              );
              if (confirm) {
                setGrant(await admin.revoke(learner_id, grant_id));
                setNotice("Assignment revoked.");
              }
            }}
          />
        )}
        {!!notice && <Message>{notice}</Message>}
      </Card>
      <Card>
        <Title>Latest receipts</Title>
        <Message>
          These receipts stay only while this dashboard is open. Save the IDs to
          manage an assignment later; the API has no account or grant directory.
        </Message>
        {educator && (
          <Text selectable>
            Educator: {educator.login_handle}
            {"\n"}User ID: {educator.user_id}
          </Text>
        )}
        {learner && (
          <Text selectable>
            Learner: {learner.display_name}
            {"\n"}Learner ID: {learner.id}
          </Text>
        )}
        {grant && (
          <Text selectable>
            Grant ID: {grant.id}
            {"\n"}Learner ID: {grant.learner_id}
            {"\n"}Access: {grant.access_level}
            {"\n"}Expires: {new Date(grant.expires_at).toLocaleString()}
            {"\n"}
            {grant.revoked_at ? "Revoked" : "Assigned"}
          </Text>
        )}
      </Card>
    </Screen>
  );
}
