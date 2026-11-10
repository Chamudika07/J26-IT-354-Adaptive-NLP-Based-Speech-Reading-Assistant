import { useQuery } from "@tanstack/react-query";
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
export default function SystemStatus() {
  const { api } = useApp();
  const health = useQuery({ queryKey: ["health"], queryFn: api.health });
  const ready = useQuery({ queryKey: ["readiness"], queryFn: api.readiness });
  return (
    <Screen>
      <Title>Connection status</Title>
      {(health.isFetching || ready.isFetching) && <Loading />}
      <Card>
        <Message>API: {health.data?.status ?? "Not verified"}</Message>
        <ErrorNotice error={health.error} />
        <Message>
          Database readiness: {ready.data?.status ?? "Not verified"}
        </Message>
        <ErrorNotice error={ready.error} />
      </Card>
      <Message>
        Readiness confirms connectivity. Feature availability also depends on
        permissions and server configuration.
      </Message>
      <Button
        title="Check connection"
        disabled={health.isFetching || ready.isFetching}
        onPress={() => {
          void health.refetch();
          void ready.refetch();
        }}
      />
    </Screen>
  );
}
