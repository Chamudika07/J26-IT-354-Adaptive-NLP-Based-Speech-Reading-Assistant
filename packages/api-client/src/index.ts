import createClient from "openapi-fetch";
import type { paths, components } from "./schema";

export type Schema<K extends keyof components["schemas"]> =
  components["schemas"][K];
export const createApi = (baseUrl: string, transport: typeof fetch = fetch) =>
  createClient<paths>({
    baseUrl: baseUrl.replace(/\/api\/v1\/?$/, ""),
    fetch: transport,
  });

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
  ) {
    super(code);
  }
}

export function unwrap<T>(result: {
  data?: T;
  error?: unknown;
  response: Response;
}): T {
  if (!result.response.ok || result.data === undefined) {
    const body = result.error as { error?: { code?: string } } | undefined;
    throw new ApiError(
      result.response.status,
      body?.error?.code ?? "request_failed",
    );
  }
  return result.data;
}
