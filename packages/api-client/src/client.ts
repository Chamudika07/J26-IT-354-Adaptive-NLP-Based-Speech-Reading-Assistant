/**
 * API client service functions for Component 2:
 * Generative AI-Based Adaptive Text Simplification & Vocabulary Support.
 *
 * Implements client transport for the three currently supported FastAPI endpoints:
 * 1. POST /api/v1/simplification/{learner_id}/simplify
 * 2. POST /api/v1/simplification/{learner_id}/vocabulary/explain
 * 3. POST /api/v1/simplification/{learner_id}/sessions/{session_id}/feedback
 *
 * Designed for mobile and web frontends with zero external dependencies,
 * using globalThis.fetch, strictly adhering to repository privacy rules
 * and the shared FastAPI authentication conventions.
 */

import type {
  ApiErrorDetail,
  ReadingFeedbackRequest,
  ReadingFeedbackResponse,
  SimplificationRequest,
  SimplificationResponse,
  WordExplanationRequest,
  WordExplanationResponse,
} from "./simplification";

/**
 * Token provider: can be a static string token or an async/sync callback that
 * returns the current access token.
 * Tokens must NOT be stored statically inside this package.
 */
export type TokenProvider =
  | string
  | (() => string | null | undefined | Promise<string | null | undefined>);

/** Obtain and retain a replacement access token using the application's refresh session. */
export type TokenRefreshProvider = () => Promise<string | null | undefined>;

/** Clear an unusable authentication session after refresh or retry failure. */
export type AuthenticationFailureHandler = () => void | Promise<void>;

/**
 * Configuration options for the Component 2 Simplification API client.
 */
export interface SimplificationClientConfig {
  /**
   * Base URL of the API server, e.g.:
   * - "http://10.0.2.2:8000" (Android emulator pointing to local host)
   * - "http://localhost:8000" (iOS simulator pointing to local host)
   * - "http://192.168.1.100:8000" (Physical mobile device on local Wi-Fi)
   * - "https://api.readbuddy.org" (Staging or production domain)
   *
   * Note: Do NOT assume "localhost" works on physical mobile devices.
   * Both "http://host:port" and "http://host:port/api/v1" formats are accepted.
   */
  baseUrl: string;

  /**
   * Optional access token or token retrieval callback.
   * The token is attached via the HTTP `Authorization: Bearer <token>` header.
   */
  getAccessToken?: TokenProvider;

  /**
   * Optional refresh callback. It is invoked only for a backend
   * `401 authentication_required` response and never for explicit per-request tokens.
   */
  refreshAccessToken?: TokenRefreshProvider;

  /** Called when refresh cannot recover the session or the one allowed retry fails. */
  onAuthenticationFailure?: AuthenticationFailureHandler;

  /**
   * Optional custom fetch implementation (defaults to globalThis.fetch).
   * Allows plugging in custom fetch for testing or specialized environments.
   */
  fetch?: typeof fetch;

  /**
   * Optional additional default headers to attach to every outgoing request.
   */
  defaultHeaders?: Record<string, string>;
}

/**
 * Per-request execution options.
 */
export interface RequestOptions {
  /** Optional AbortSignal to cancel the in-flight request. */
  signal?: AbortSignal;
  /** Optional per-request access token override. */
  accessToken?: string;
  /** Optional extra headers for this specific request. */
  headers?: Record<string, string>;
}

/**
 * Specific error thrown when an API request returns a non-2xx status code.
 * Preserves the backend's standard error envelope when valid, but ensures
 * no secrets, raw provider details, or learner texts are leaked.
 */
export class SimplificationApiError extends Error {
  /** HTTP response status code (e.g. 401, 404, 422, 429, 503). */
  readonly status: number;
  /** Error classification code from backend (e.g. "authentication_required", "rate_limited"). */
  readonly code: string;
  /** Recommended retry-after backoff in seconds (populated if 429 response contains Retry-After). */
  readonly retryAfter?: number;
  /** Sanitized error detail from backend, if available. */
  readonly errorDetail?: ApiErrorDetail;

  constructor(
    status: number,
    code: string,
    message: string,
    retryAfter?: number,
    errorDetail?: ApiErrorDetail
  ) {
    super(message);
    this.name = "SimplificationApiError";
    this.status = status;
    this.code = code;
    this.retryAfter = retryAfter;
    this.errorDetail = errorDetail;
    Object.setPrototypeOf(this, SimplificationApiError.prototype);
  }
}

/**
 * Construct the complete URL for an endpoint path, correctly handling
 * whether baseUrl includes the `/api/v1` prefix or not.
 */
export function buildApiUrl(baseUrl: string, endpointPath: string): string {
  const trimmedBase = baseUrl.replace(/\/+$/, "");
  const normalizedBase = trimmedBase.endsWith("/api/v1")
    ? trimmedBase
    : `${trimmedBase}/api/v1`;
  const cleanPath = endpointPath.startsWith("/") ? endpointPath : `/${endpointPath}`;
  return `${normalizedBase}${cleanPath}`;
}

/**
 * Map HTTP status code to a default sanitized error classification code.
 */
function defaultErrorCode(status: number): string {
  switch (status) {
    case 400:
      return "bad_request";
    case 401:
      return "authentication_required";
    case 403:
      return "forbidden";
    case 404:
      return "not_found";
    case 422:
      return "validation_error";
    case 429:
      return "rate_limited";
    case 500:
      return "server_error";
    case 503:
      return "service_unavailable";
    default:
      return "http_error";
  }
}

/**
 * Map HTTP status code to a default sanitized user-facing error message.
 * Never leaks database details, AI provider details, or learner inputs.
 */
function defaultErrorMessage(status: number): string {
  switch (status) {
    case 400:
      return "Bad request";
    case 401:
      return "Authentication required";
    case 403:
      return "Access denied";
    case 404:
      return "Resource not found";
    case 422:
      return "Invalid request";
    case 429:
      return "Try again later";
    case 500:
      return "An internal server error occurred";
    case 503:
      return "Service unavailable";
    default:
      return `Request failed with status ${status}`;
  }
}

/**
 * Safely parse error response from the backend without exposing raw internals.
 */
async function parseErrorResponse(response: Response): Promise<SimplificationApiError> {
  const status = response.status;
  let code = defaultErrorCode(status);
  let message = defaultErrorMessage(status);
  let detail: ApiErrorDetail | undefined = undefined;

  let retryAfter: number | undefined = undefined;
  const retryHeader = response.headers.get("Retry-After");
  if (retryHeader) {
    const parsed = parseInt(retryHeader, 10);
    if (!isNaN(parsed) && parsed > 0) {
      retryAfter = parsed;
    }
  }

  try {
    const contentType = response.headers.get("content-type");
    if (contentType && contentType.includes("application/json")) {
      const data = await response.json();
      if (
        data &&
        typeof data === "object" &&
        data.error &&
        typeof data.error === "object"
      ) {
        const errObj = data.error as Record<string, unknown>;
        if (typeof errObj.code === "string" && errObj.code.trim()) {
          code = errObj.code.trim();
        }
        if (typeof errObj.message === "string" && errObj.message.trim()) {
          message = errObj.message.trim();
        }
        detail = { code, message };
      }
    }
  } catch {
    // If response body parsing fails, preserve safe fallback message and code
  }

  return new SimplificationApiError(status, code, message, retryAfter, detail);
}

/**
 * Resolve access token from static string or dynamic provider.
 */
async function resolveAccessToken(
  provider?: TokenProvider,
  overrideToken?: string
): Promise<string | null> {
  if (overrideToken && overrideToken.trim()) {
    return overrideToken.trim();
  }
  if (!provider) {
    return null;
  }
  if (typeof provider === "function") {
    const token = await provider();
    return token && token.trim() ? token.trim() : null;
  }
  return provider.trim() ? provider.trim() : null;
}

/**
 * Execute an authenticated POST request and validate the JSON response.
 */
async function postJson<TReq, TRes>(
  url: string,
  body: TReq,
  config: SimplificationClientConfig,
  options?: RequestOptions,
  recoverAuthentication?: (rejectedToken: string | null) => Promise<string | null>
): Promise<TRes> {
  const fetchFn = config.fetch ?? globalThis.fetch;
  if (typeof fetchFn !== "function") {
    throw new Error(
      "No fetch implementation found. Ensure globalThis.fetch is available or supply config.fetch."
    );
  }

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "application/json",
    ...config.defaultHeaders,
    ...options?.headers,
  };

  const token = await resolveAccessToken(config.getAccessToken, options?.accessToken);
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const execute = async (): Promise<Response> => {
    try {
      return await fetchFn(url, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
        signal: options?.signal,
      });
    } catch (err: unknown) {
      if (err instanceof Error && err.name === "AbortError") {
        throw err;
      }
      const message = err instanceof Error ? err.message : "Network request failed";
      throw new SimplificationApiError(0, "network_error", message);
    }
  };

  let response = await execute();
  if (!response.ok) {
    const initialError = await parseErrorResponse(response);
    const canRefresh =
      initialError.status === 401 &&
      initialError.code === "authentication_required" &&
      !options?.accessToken &&
      recoverAuthentication;
    if (!canRefresh) {
      throw initialError;
    }

    const replacement = await recoverAuthentication(token);
    if (!replacement) {
      throw initialError;
    }
    headers.Authorization = `Bearer ${replacement}`;
    response = await execute();
    if (!response.ok) {
      const retryError = await parseErrorResponse(response);
      if (
        retryError.status === 401 &&
        retryError.code === "authentication_required" &&
        config.onAuthenticationFailure
      ) {
        await config.onAuthenticationFailure();
      }
      throw retryError;
    }
  }

  return (await response.json()) as TRes;
}

/**
 * Public client interface for Component 2 Simplification API operations.
 */
export interface SimplificationClient {
  /**
   * Request adaptive text simplification for a learner.
   *
   * @param learnerId Unique UUID of the learner.
   * @param request Simplification parameters including source_text.
   * @param options Optional request-level controls (e.g. AbortSignal).
   * @returns Simplified text, vocabulary list, and session metadata.
   */
  simplifyText(
    learnerId: string,
    request: SimplificationRequest,
    options?: RequestOptions
  ): Promise<SimplificationResponse>;

  /**
   * Request plain-language explanation for a difficult word selected by the learner.
   *
   * @param learnerId Unique UUID of the learner.
   * @param request Target word term and optional context sentence / session ID.
   * @param options Optional request-level controls.
   * @returns Explained vocabulary item with definitions and child-friendly synonyms.
   */
  explainWord(
    learnerId: string,
    request: WordExplanationRequest,
    options?: RequestOptions
  ): Promise<WordExplanationResponse>;

  /**
   * Submit post-reading learner difficulty feedback for an active simplification session.
   *
   * @param learnerId Unique UUID of the learner.
   * @param sessionId Unique UUID of the simplification session being reviewed.
   * @param request Feedback signal, reading duration, and completion status.
   * @param options Optional request-level controls.
   * @returns Confirmation receipt with persisted feedback_id.
   */
  submitReadingFeedback(
    learnerId: string,
    sessionId: string,
    request: ReadingFeedbackRequest,
    options?: RequestOptions
  ): Promise<ReadingFeedbackResponse>;
}

/**
 * Reusable implementation of the SimplificationClient interface.
 */
export class SimplificationApiClient implements SimplificationClient {
  private refreshInFlight: Promise<string | null> | null = null;

  constructor(private readonly config: SimplificationClientConfig) {
    if (!config || !config.baseUrl || !config.baseUrl.trim()) {
      throw new Error("SimplificationApiClient requires a valid non-empty baseUrl.");
    }
    this.simplifyText = this.simplifyText.bind(this);
    this.explainWord = this.explainWord.bind(this);
    this.submitReadingFeedback = this.submitReadingFeedback.bind(this);
  }

  private async clearFailedAuthentication(): Promise<void> {
    if (this.config.onAuthenticationFailure) {
      await this.config.onAuthenticationFailure();
    }
  }

  private async recoverAuthentication(rejectedToken: string | null): Promise<string | null> {
    if (!this.config.refreshAccessToken) {
      await this.clearFailedAuthentication();
      return null;
    }

    const currentToken = await resolveAccessToken(this.config.getAccessToken);
    if (currentToken && currentToken !== rejectedToken) {
      return currentToken;
    }

    if (!this.refreshInFlight) {
      this.refreshInFlight = (async () => {
        try {
          const token = await this.config.refreshAccessToken?.();
          const normalized = token?.trim() || null;
          if (!normalized) {
            await this.clearFailedAuthentication();
          }
          return normalized;
        } catch {
          await this.clearFailedAuthentication();
          return null;
        }
      })().finally(() => {
        this.refreshInFlight = null;
      });
    }
    return this.refreshInFlight;
  }

  async simplifyText(
    learnerId: string,
    request: SimplificationRequest,
    options?: RequestOptions
  ): Promise<SimplificationResponse> {
    const url = buildApiUrl(
      this.config.baseUrl,
      `/simplification/${encodeURIComponent(learnerId)}/simplify`
    );
    return postJson<SimplificationRequest, SimplificationResponse>(
      url,
      request,
      this.config,
      options,
      (rejectedToken) => this.recoverAuthentication(rejectedToken)
    );
  }

  async explainWord(
    learnerId: string,
    request: WordExplanationRequest,
    options?: RequestOptions
  ): Promise<WordExplanationResponse> {
    const url = buildApiUrl(
      this.config.baseUrl,
      `/simplification/${encodeURIComponent(learnerId)}/vocabulary/explain`
    );
    return postJson<WordExplanationRequest, WordExplanationResponse>(
      url,
      request,
      this.config,
      options,
      (rejectedToken) => this.recoverAuthentication(rejectedToken)
    );
  }

  async submitReadingFeedback(
    learnerId: string,
    sessionId: string,
    request: ReadingFeedbackRequest,
    options?: RequestOptions
  ): Promise<ReadingFeedbackResponse> {
    const url = buildApiUrl(
      this.config.baseUrl,
      `/simplification/${encodeURIComponent(learnerId)}/sessions/${encodeURIComponent(sessionId)}/feedback`
    );
    return postJson<ReadingFeedbackRequest, ReadingFeedbackResponse>(
      url,
      request,
      this.config,
      options,
      (rejectedToken) => this.recoverAuthentication(rejectedToken)
    );
  }
}

/**
 * Factory function to create a new SimplificationApiClient instance.
 */
export function createSimplificationClient(
  config: SimplificationClientConfig
): SimplificationApiClient {
  return new SimplificationApiClient(config);
}

/**
 * Standalone helper to simplify text using an explicit client configuration.
 */
export async function simplifyText(
  learnerId: string,
  request: SimplificationRequest,
  config: SimplificationClientConfig,
  options?: RequestOptions
): Promise<SimplificationResponse> {
  return createSimplificationClient(config).simplifyText(learnerId, request, options);
}

/**
 * Standalone helper to explain a word using an explicit client configuration.
 */
export async function explainWord(
  learnerId: string,
  request: WordExplanationRequest,
  config: SimplificationClientConfig,
  options?: RequestOptions
): Promise<WordExplanationResponse> {
  return createSimplificationClient(config).explainWord(learnerId, request, options);
}

/**
 * Standalone helper to submit reading feedback using an explicit client configuration.
 */
export async function submitReadingFeedback(
  learnerId: string,
  sessionId: string,
  request: ReadingFeedbackRequest,
  config: SimplificationClientConfig,
  options?: RequestOptions
): Promise<ReadingFeedbackResponse> {
  return createSimplificationClient(config).submitReadingFeedback(
    learnerId,
    sessionId,
    request,
    options
  );
}
