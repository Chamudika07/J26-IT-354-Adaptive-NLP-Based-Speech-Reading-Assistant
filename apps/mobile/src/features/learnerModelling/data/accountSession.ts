import type { AuthenticatedSession } from "./component4Client";
import { isUuid } from "./validateContract";

export class AccountError extends Error {
  constructor(readonly code: "sign_in_required" | "invalid_response" | "unavailable" | "invalid_address" | "rate_limited" | "storage_unavailable") { super("Account request could not be completed."); }
}
export interface AccountIdentity { user_id: string; login_handle: string; status: "active"; roles: string[] }
export interface AuthorizedLearner { id: string; display_name: string }
interface Tokens { access_token: string; refresh_token: string; token_type: "bearer"; expires_in: number }
function object(value: unknown): value is Record<string, unknown> { return !!value && typeof value === "object" && !Array.isArray(value); }
function tokens(value: unknown): value is Tokens {
  return object(value) && typeof value.access_token === "string" && value.access_token.length > 0 && !/\s/.test(value.access_token) &&
    typeof value.refresh_token === "string" && value.refresh_token.length > 0 && value.refresh_token.length <= 256 &&
    value.token_type === "bearer" && typeof value.expires_in === "number" && Number.isInteger(value.expires_in) && value.expires_in > 0;
}
export interface RefreshPersistence { consume(): Promise<string | null>; save(token: string): Promise<void>; clear(): Promise<void> }
let scopeSequence = 0;
/** Password/access tokens remain in memory; optional refresh persistence uses secure host storage. */
export function createAccountSession(address: string, onExpired: () => void, transport: typeof fetch = fetch, persistence?: RefreshPersistence) {
  let base: URL;
  try { base = new URL(address); } catch { throw new AccountError("invalid_address"); }
  if (base.protocol !== "https:" || base.username || base.password || base.search || base.hash || base.pathname.replace(/\/$/, "") !== "/api/v1") throw new AccountError("invalid_address");
  const baseUrl = base.toString().replace(/\/$/, "");
  let current: Tokens | undefined;
  let expiresAt = 0;
  let generation = 0;
  let refreshing: Promise<string | null> | undefined;
  const controllers = new Set<AbortController>();
  function clear() {
    generation++;
    current = undefined;
    expiresAt = 0;
    for (const c of controllers) c.abort();
    controllers.clear();
  }
  function expire() { clear(); void persistence?.clear().catch(() => undefined); onExpired(); }
  async function request(path: string, body?: unknown, token?: string): Promise<unknown> {
    const controller = new AbortController(); controllers.add(controller);
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      const operation = (async () => {
        const response = await transport(baseUrl + path, { method: body ? "POST" : "GET", redirect: "error", signal: controller.signal,
          headers: { Accept: "application/json", ...(body ? { "Content-Type": "application/json" } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) },
          ...(body ? { body: JSON.stringify(body) } : {}) });
        if (response.status === 401) throw new AccountError("sign_in_required");
        if (response.status === 429) throw new AccountError("rate_limited");
        if (!response.ok) throw new AccountError("unavailable");
        if (response.status === 204) return null;
        if (Number(response.headers.get("content-length")) > 1000000) throw new AccountError("invalid_response");
        const text = await response.text();
        if (text.length > 1000000) throw new AccountError("invalid_response");
        try { return JSON.parse(text) as unknown; } catch { throw new AccountError("invalid_response"); }
      })();
      return await Promise.race([operation, new Promise<never>((_resolve, reject) => {
        timer = setTimeout(() => { controller.abort(); reject(new AccountError("unavailable")); }, 15000);
      })]);
    } catch (error) {
      if (error instanceof AccountError) throw error;
      throw new AccountError("unavailable");
    } finally { if (timer) clearTimeout(timer); controllers.delete(controller); }
  }
  function store(value: unknown) {
    if (!tokens(value)) throw new AccountError("invalid_response");
    current = { access_token: value.access_token, refresh_token: value.refresh_token, token_type: "bearer", expires_in: value.expires_in };
    expiresAt = Date.now() + value.expires_in * 1000;
  }
  async function refresh(): Promise<string | null> {
    if (!current) return null;
    if (refreshing) return refreshing;
    const before = generation;
    const refreshToken = current.refresh_token;
    refreshing = (async () => {
      try {
        const value = await request("/auth/refresh", { refresh_token: refreshToken });
        if (before !== generation) return null;
        store(value);
        if (persistence && current) await persistence.save(current.refresh_token);
        if (before !== generation) return null;
        return current?.access_token ?? null;
      } catch {
        // A refresh can rotate before a network failure. Never replay an uncertain token.
        if (before === generation) expire();
        return null;
      } finally { refreshing = undefined; }
    })();
    return refreshing;
  }
  const session: AuthenticatedSession = {
    scopeKey: `account-session-${++scopeSequence}`,
    async getAccessToken() {
      if (!current) return null;
      if (Date.now() >= expiresAt - 10000) return refresh();
      return current.access_token;
    },
    refreshAccessToken: refresh,
  };
  async function authorized(path: string) {
    const before = generation;
    let token = await session.getAccessToken();
    if (!token || before !== generation) throw new AccountError("sign_in_required");
    try { return await request(path, undefined, token); }
    catch (error) {
      if (!(error instanceof AccountError) || error.code !== "sign_in_required") throw error;
      token = await refresh();
      if (!token || before !== generation) throw new AccountError("sign_in_required");
      try { return await request(path, undefined, token); }
      catch (retryError) { if (retryError instanceof AccountError && retryError.code === "sign_in_required") expire(); throw retryError; }
    }
  }
  async function readIdentity(): Promise<AccountIdentity> {
    const identity = await authorized("/auth/me");
    if (!object(identity) || !isUuid(identity.user_id) || identity.status !== "active" ||
        typeof identity.login_handle !== "string" || !Array.isArray(identity.roles) || !identity.roles.every(r => typeof r === "string")) throw new AccountError("invalid_response");
    return { user_id: identity.user_id, login_handle: identity.login_handle, status: "active", roles: [...identity.roles] as string[] };
  }
  return {
    baseUrl, session,
    async restore(): Promise<AccountIdentity | null> {
      if (!persistence) return null;
      clear(); const before = generation;
      try {
        const credential = await persistence.consume();
        if (!credential || before !== generation) return null;
        current = { access_token: "restore-pending", refresh_token: credential, token_type: "bearer", expires_in: 1 };
        const token = await refresh();
        if (!token || before !== generation) throw new AccountError("sign_in_required");
        const identity = await readIdentity();
        if (before !== generation) throw new AccountError("sign_in_required");
        return identity;
      } catch { if (before === generation) { clear(); await persistence.clear().catch(() => undefined); } throw new AccountError("sign_in_required"); }
    },
    async login(handle: string, password: string): Promise<AccountIdentity> {
      clear(); const before = generation;
      try {
        if (persistence) { try { await persistence.clear(); } catch { throw new AccountError("storage_unavailable"); } }
        if (!handle.trim() || handle.length > 128 || !password || password.length > 128) throw new AccountError("sign_in_required");
        const value = await request("/auth/login", { login_handle: handle.trim(), password });
        if (before !== generation) throw new AccountError("sign_in_required");
        store(value);
        if (persistence && current) { try { await persistence.save(current.refresh_token); } catch { throw new AccountError("storage_unavailable"); } }
        const identity = await readIdentity();
        if (before !== generation) throw new AccountError("sign_in_required");
        return identity;
      } catch (error) { if (before === generation) { clear(); await persistence?.clear().catch(() => undefined); } throw error; }
    },
    async learners(cursor?: string): Promise<{ items: AuthorizedLearner[]; next_cursor: string | null }> {
      if (cursor && !isUuid(cursor)) throw new AccountError("invalid_response");
      const before = generation;
      const value = await authorized("/learners?limit=25" + (cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""));
      if (before !== generation) throw new AccountError("sign_in_required");
      if (!object(value) || !Array.isArray(value.items) || value.items.length > 25 || !value.items.every(v => object(v) && isUuid(v.id) && typeof v.display_name === "string" && v.display_name.length > 0 && v.display_name.length <= 80) ||
          (value.next_cursor !== null && !isUuid(value.next_cursor)) || new Set(value.items.map(v => v.id)).size !== value.items.length) throw new AccountError("invalid_response");
      return { items: value.items.map(v => ({ id: v.id as string, display_name: v.display_name as string })), next_cursor: value.next_cursor as string | null };
    },
    async logout(): Promise<boolean> {
      const token = current?.refresh_token;
      clear();
      let removed = true;
      try { await persistence?.clear(); } catch { removed = false; }
      if (!token) return removed;
      try { await request("/auth/logout", { refresh_token: token }); return removed; } catch { return false; }

    },
    dispose: clear,
  };
}
export type AccountSession = ReturnType<typeof createAccountSession>;
