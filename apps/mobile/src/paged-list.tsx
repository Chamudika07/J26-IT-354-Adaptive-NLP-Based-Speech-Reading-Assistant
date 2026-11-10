import type { ReactNode } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { Button, ErrorNotice, Loading, Message } from "./ui";
import type { ErrorContext } from "./api/errors";
export function PagedList<T extends { id: string }>({
  queryKey,
  load,
  render,
  empty = "No records yet.",
  enabled = true,
  context = "reading",
}: {
  queryKey: readonly unknown[];
  load(cursor?: string): Promise<{ items: T[]; next_cursor?: string | null }>;
  render(item: T): ReactNode;
  empty?: string;
  enabled?: boolean;
  context?: ErrorContext;
}) {
  const q = useInfiniteQuery({
    queryKey,
    queryFn: ({ pageParam }) => load(pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    enabled,
  });
  if (!enabled) return null;
  return (
    <>
      {q.isPending && <Loading />}
      <ErrorNotice error={q.error} context={context} />
      {!q.isError && q.data?.pages.flatMap((p) => p.items).map(render)}
      {q.data?.pages[0]?.items.length === 0 && <Message>{empty}</Message>}
      {q.hasNextPage && (
        <Button
          title="Load more"
          disabled={q.isFetching}
          onPress={() => void q.fetchNextPage()}
        />
      )}
      <Button
        title="Refresh list"
        secondary
        disabled={q.isFetching}
        onPress={() => void q.refetch()}
      />
    </>
  );
}
