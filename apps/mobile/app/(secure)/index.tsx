import { Alert } from "react-native";
import { router } from "expo-router";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { useApp } from "../../src/providers";
import {
  Button,
  Card,
  ErrorNotice,
  Loading,
  Message,
  Screen,
  Title,
} from "../../src/ui";

export default function Home() {
  const { api, session } = useApp();
  const me = useQuery({ queryKey: ["me"], queryFn: api.me });
  const canRead =
    me.data?.roles.some((role) =>
      ["educator", "guardian", "learner"].includes(role),
    ) ?? false;
  const learners = useInfiniteQuery({
    queryKey: ["learners"],
    queryFn: ({ pageParam }) => api.learners(pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    enabled: canRead,
  });
  return (
    <Screen>
      <Title>Your reading space</Title>
      <Button
        title="Connection status"
        secondary
        onPress={() => router.push("/system")}
      />
      {me.isPending && <Loading />}
      <ErrorNotice error={me.error} />
      {me.data && (
        <Card>
          <Message>Signed in as {me.data.login_handle}</Message>
          <Message>
            Roles: {me.data.roles.join(", ") || "No assigned roles"}
          </Message>
        </Card>
      )}
      {me.data?.roles.includes("administrator") && (
        <Card>
          <Title>Administration</Title>
          <Button
            title="Open administrator dashboard"
            onPress={() => router.push("/admin")}
          />
        </Card>
      )}
      <Button
        title="Sign out"
        secondary
        onPress={() => {
          void session
            .logout()
            .catch(() =>
              Alert.alert(
                "Signed out locally",
                "The server could not confirm revocation or secure storage could not be cleared. Reconnect and retry sign-out before sharing this device.",
              ),
            );
        }}
      />
      {me.data && !canRead && (
        <Message>
          This account has no learner-reading role. Use the administrator
          dashboard to assign educator access; administrator status alone does
          not grant reading access.
        </Message>
      )}
      {canRead && (
        <>
          <Title>Learners</Title>
          {learners.isPending && <Loading />}
          <ErrorNotice error={learners.error} />
          {!learners.isError &&
            learners.data?.pages
              .flatMap((page) => page.items)
              .map((learner) => (
                <Card key={learner.id}>
                  <Message>{learner.display_name}</Message>
                  <Button
                    title={`Open ${learner.display_name}`}
                    onPress={() =>
                      router.push({
                        pathname: "/learners/[learnerId]",
                        params: { learnerId: learner.id },
                      })
                    }
                  />
                </Card>
              ))}
          {learners.data?.pages[0]?.items.length === 0 && (
            <Message>
              No learners are assigned to this account. An administrator must
              assign a current educator grant.
            </Message>
          )}
          {learners.hasNextPage && (
            <Button
              title="More learners"
              disabled={learners.isFetchingNextPage}
              onPress={() => void learners.fetchNextPage()}
            />
          )}
        </>
      )}
      <Button
        title="Refresh"
        secondary
        disabled={me.isFetching || learners.isFetching}
        onPress={() => {
          void me.refetch();
          if (canRead) void learners.refetch();
        }}
      />
    </Screen>
  );
}
