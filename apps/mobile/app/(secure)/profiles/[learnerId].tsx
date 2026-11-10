import { useQuery } from "@tanstack/react-query";
import { router, useLocalSearchParams } from "expo-router";
import { useApp } from "../../../src/providers";
import {
  Button,
  Card,
  ErrorNotice,
  Loading,
  Message,
  Screen,
  Title,
} from "../../../src/ui";
export default function Profile() {
  const { learnerId } = useLocalSearchParams<{ learnerId: string }>();
  const { api } = useApp();
  const q = useQuery({
    queryKey: ["profile", learnerId],
    queryFn: () => api.profile(learnerId),
  });
  return (
    <Screen>
      <Title>Learner profile</Title>
      {q.isPending && <Loading />}
      <ErrorNotice error={q.error} />
      {q.data && !q.isError && (
        <Card>
          <Title>{q.data.display_name}</Title>
          {"age_band" in q.data && (
            <>
              <Message>Age band: {q.data.age_band ?? "Not recorded"}</Message>
              <Message>
                Grade level: {q.data.grade_level ?? "Not recorded"}
              </Message>
            </>
          )}
          <Button
            title="Preferences"
            onPress={() =>
              router.push({
                pathname: "/preferences/[learnerId]",
                params: { learnerId },
              })
            }
          />
          <Message>
            Preferences require learner or guardian permission. Educator access
            does not include preferences.
          </Message>
        </Card>
      )}
      <Button
        title="Refresh profile"
        secondary
        disabled={q.isFetching}
        onPress={() => void q.refetch()}
      />
    </Screen>
  );
}
