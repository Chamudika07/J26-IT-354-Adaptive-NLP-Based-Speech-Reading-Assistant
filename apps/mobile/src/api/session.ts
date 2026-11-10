import { ApiError, createApi, unwrap, type Schema } from "@j26/api-client";

export interface CredentialStore {
  read(): Promise<string | null>;
  write(value: string): Promise<void>;
  clear(): Promise<void>;
}

export function apiUrl(
  value: string | undefined,
  development: boolean,
): string {
  if (!value)
    throw new Error("Set EXPO_PUBLIC_API_URL in apps/mobile/.env.local.");
  const url = new URL(value);
  if (
    !["https:", "http:"].includes(url.protocol) ||
    url.username ||
    url.password ||
    url.search ||
    url.hash ||
    url.pathname.replace(/\/$/, "") !== "/api/v1"
  ) {
    throw new Error(
      "API URL must be an HTTP(S) address ending in /api/v1, without credentials.",
    );
  }
  if (!development && url.protocol !== "https:")
    throw new Error("Production requires HTTPS.");
  return value.replace(/\/$/, "");
}

export class Session {
  private tokens: Schema<"TokenResponse"> | null = null;
  private refreshToken: string | null = null;
  private rotating: Promise<void> | null = null;
  private generation = 0;
  private storageQueue: Promise<void> = Promise.resolve();
  private readonly publicApi;
  readonly api;

  constructor(
    base: string,
    private store: CredentialStore,
    private changed: (active: boolean) => void,
    private transport: typeof fetch = fetch,
  ) {
    this.publicApi = createApi(base, this.send);
    this.api = createApi(base, this.authorized);
  }

  private send: typeof fetch = async (input, init) => {
    const request = new Request(input, init);
    const controller = new AbortController();
    const abort = () => controller.abort();
    request.signal.addEventListener("abort", abort, { once: true });
    if (request.signal.aborted) controller.abort();
    // PDF extraction can itself take 30 seconds; leave room for upload and DB work.
    const pdfWrite =
      request.method === "POST" &&
      /\/(pdf|extraction-runs)$/.test(new URL(request.url).pathname);
    const timer = setTimeout(abort, pdfWrite ? 60_000 : 30_000);
    try {
      return await this.transport(request, { signal: controller.signal });
    } finally {
      clearTimeout(timer);
      request.signal.removeEventListener("abort", abort);
    }
  };

  private persist(action: () => Promise<void>) {
    const next = this.storageQueue.catch(() => undefined).then(action);
    this.storageQueue = next;
    return next;
  }

  private async accept(tokens: Schema<"TokenResponse">, generation: number) {
    if (generation !== this.generation) {
      await this.publicApi.POST("/api/v1/auth/logout", {
        body: { refresh_token: tokens.refresh_token },
      });
      throw new ApiError(401, "session_changed");
    }
    try {
      await this.persist(() => this.store.write(tokens.refresh_token));
    } catch {
      await this.forget();
      await this.publicApi.POST("/api/v1/auth/logout", {
        body: { refresh_token: tokens.refresh_token },
      });
      throw new Error("Secure session storage failed. Sign in again.");
    }
    if (generation !== this.generation) {
      await this.publicApi.POST("/api/v1/auth/logout", {
        body: { refresh_token: tokens.refresh_token },
      });
      throw new ApiError(401, "session_changed");
    }
    this.tokens = tokens;
    this.refreshToken = tokens.refresh_token;
    this.changed(true);
  }

  async login(body: Schema<"LoginRequest">) {
    const generation = ++this.generation;
    const tokens = unwrap(
      await this.publicApi.POST("/api/v1/auth/login", { body }),
    );
    await this.accept(tokens, generation);
  }

  async restore() {
    const generation = this.generation;
    const saved = await this.store.read();
    if (generation !== this.generation) return;
    this.refreshToken = saved;
    if (saved) await this.refresh();
  }

  private refresh(): Promise<void> {
    if (this.rotating) return this.rotating;
    const token = this.refreshToken;
    const generation = this.generation;
    if (!token)
      return Promise.reject(new ApiError(401, "authentication_required"));
    this.rotating = (async () => {
      try {
        const tokens = unwrap(
          await this.publicApi.POST("/api/v1/auth/refresh", {
            body: { refresh_token: token },
          }),
        );
        await this.accept(tokens, generation);
      } catch (error) {
        if (
          error instanceof ApiError &&
          error.status === 401 &&
          generation === this.generation
        )
          await this.forget();
        throw error;
      } finally {
        this.rotating = null;
      }
    })();
    return this.rotating;
  }

  private authorized: typeof fetch = async (input, init) => {
    const generation = this.generation;
    const request = new Request(input, init);
    const execute = () => {
      if (generation !== this.generation)
        throw new ApiError(401, "session_changed");
      const headers = new Headers(request.headers);
      if (this.tokens)
        headers.set("Authorization", `Bearer ${this.tokens.access_token}`);
      return this.send(request.clone(), { headers });
    };
    if (!this.tokens) await this.refresh();
    const used = this.tokens?.access_token;
    let response = await execute();
    if (response.status === 401) {
      // Concurrent 401s share one rotation; late responses reuse the new access token.
      if (used === this.tokens?.access_token) await this.refresh();
      response = await execute();
      if (response.status === 401 && generation === this.generation)
        await this.forget();
    }
    if (generation !== this.generation)
      throw new ApiError(401, "session_changed");
    return response;
  };

  async forget() {
    ++this.generation;
    this.tokens = null;
    this.refreshToken = null;
    this.changed(false);
    await this.persist(() => this.store.clear());
  }

  async logout() {
    const token = this.refreshToken;
    await this.forget();
    if (token) {
      const result = await this.publicApi.POST("/api/v1/auth/logout", {
        body: { refresh_token: token },
      });
      if (!result.response.ok)
        throw new ApiError(result.response.status, "logout_failed");
    }
  }
}
