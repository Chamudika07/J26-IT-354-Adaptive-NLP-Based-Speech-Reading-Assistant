/**
 * TypeScript contract definitions for Component 2:
 * Generative AI-Based Adaptive Text Simplification & Vocabulary Support.
 *
 * These contracts mirror the FastAPI backend Pydantic schemas in
 * `apps/backend/app/modules/simplification/schemas.py`.
 *
 * Strict validation note: The backend uses Pydantic with `extra="forbid"`.
 * Never add extra properties to request payloads beyond those declared here.
 * In particular, `learner_id` belongs in the URL path, NOT in request bodies.
 */

// ── Enumerations (String Union Types) ────────────────────────────────────────

/**
 * Proposed qualitative reading levels for Component 2 text adaptation.
 * Mirrors `app.modules.simplification.schemas.ReadingLevel`.
 */
export type ReadingLevel = "beginner" | "elementary" | "intermediate" | "advanced";

/**
 * Adaptation strategy applied or requested for text simplification.
 * Mirrors `app.modules.simplification.schemas.SimplificationStrategy`.
 */
export type SimplificationStrategy =
  | "vocabulary_swap"
  | "sentence_split"
  | "concept_reduction"
  | "full_rewrite"
  | "combined";

/**
 * Origin of the vocabulary item.
 * Mirrors `app.modules.simplification.schemas.VocabularySource`.
 */
export type VocabularySource = "automatic" | "user";

/**
 * Coarse learner feedback signal on reading difficulty.
 * Mirrors `app.modules.simplification.schemas.FeedbackSignal`.
 */
export type FeedbackSignal = "too_hard" | "too_easy" | "just_right" | "skipped";

// ── Shared Vocabulary Schemas ────────────────────────────────────────────────

/**
 * A single vocabulary term and plain-language explanation for children aged 9-12.
 * Mirrors `app.modules.simplification.schemas.VocabularyItemResponse`.
 */
export interface VocabularyItemResponse {
  /** The challenging academic or domain-specific word (1 to 200 characters). */
  term: string;
  /** Plain-language explanation accessible to children (1 to 500 characters). */
  simplified_definition: string;
  /** Contextual or illustrative example sentence (max 300 characters), if available. */
  example_sentence?: string | null;
  /** Up to 5 child-friendly synonyms (each max 100 characters). */
  synonyms: string[];
  /** Origin of the vocabulary item: automatically extracted or user-requested. */
  source: VocabularySource;
}

// ── API 1: Text Simplification (/api/v1/simplification/{learner_id}/simplify) ─

/**
 * Request payload for adaptive text simplification.
 * Learner identity is resolved from the URL path and JWT authentication.
 * Client-supplied reading levels and strategies are advisory hints only.
 * Mirrors `app.modules.simplification.schemas.SimplificationRequest`.
 */
export interface SimplificationRequest {
  /** Raw educational text to simplify (1 to 50,000 characters). */
  source_text: string;
  /** Optional source difficulty score normalized between 0.00 and 1.00. */
  source_difficulty?: number | null;
  /** Optional correlation identifier of the source document. */
  document_id?: string | null;
  /** Key concepts to preserve during adaptation (max 20 items, each max 120 characters). */
  key_concepts?: string[];
  /** Advisory hint: current estimated reading level of the learner. */
  current_reading_level?: ReadingLevel | null;
  /** Advisory hint: target reading level for adaptation. */
  target_reading_level?: ReadingLevel | null;
  /** Advisory hint: preferred adaptation strategy. */
  preferred_strategy?: SimplificationStrategy | null;
}

/**
 * Response payload containing simplified text, extracted vocabulary, and metadata.
 * Mirrors `app.modules.simplification.schemas.SimplificationResponse`.
 */
export interface SimplificationResponse {
  /** Unique session identifier generated for this simplification request. */
  session_id: string;
  /** Identifier of the learner profile this session belongs to. */
  learner_id: string;
  /** The adapted, simplified passage accessible to children aged 9-12 (1 to 60,000 characters). */
  simplified_text: string;
  /** The adaptation strategy applied by the simplification engine. */
  strategy_applied: SimplificationStrategy;
  /** Target reading level applied to the output text. */
  target_reading_level: ReadingLevel;
  /** Decimal score (0.00 to 1.00), serialized as a JSON string by Pydantic. */
  estimated_output_difficulty?: string | null;
  /** Adaptation iteration attempt count (between 1 and 10). */
  adaptation_attempt: number;
  /** Key vocabulary items identified and explained automatically. */
  vocabulary_items: VocabularyItemResponse[];
  /** Validation warnings or pedagogical guidance generated during adaptation. */
  warnings: string[];
  /** Timestamp when the session was created and persisted (ISO 8601 UTC). */
  created_at: string;
}

// ── API 2: On-Demand Vocabulary (/api/v1/simplification/{learner_id}/vocabulary/explain)

/**
 * Request payload for on-demand explanation of a selected word.
 * Mirrors `app.modules.simplification.schemas.WordExplanationRequest`.
 */
export interface WordExplanationRequest {
  /** The word or term selected by the learner for explanation (1 to 200 characters). */
  term: string;
  /** Context sentence in which the word appeared (max 500 characters). */
  context_sentence?: string | null;
  /** Optional simplification session identifier to associate with this lookup. */
  session_id?: string | null;
}

/**
 * Response payload containing plain-language explanation for a selected word.
 * Mirrors `app.modules.simplification.schemas.WordExplanationResponse`.
 */
export interface WordExplanationResponse {
  /** Identifier of the learner profile. */
  learner_id: string;
  /** The explained vocabulary item with definitions and synonyms. */
  item: VocabularyItemResponse;
  /** BCP 47 language tag of the explanation (e.g. "en"). */
  language_tag: string;
  /** Associated simplification session identifier, if provided in request. */
  session_id?: string | null;
  /** Timestamp when the explanation was recorded (ISO 8601 UTC). */
  created_at: string;
}

// ── API 3: Post-Reading Feedback (/api/v1/simplification/{learner_id}/sessions/{session_id}/feedback)

/**
 * Request payload for submitting post-reading learner feedback.
 * Feedback is append-only; update and delete operations do not exist.
 * Mirrors `app.modules.simplification.schemas.ReadingFeedbackRequest`.
 */
export interface ReadingFeedbackRequest {
  /** Learner's perceived difficulty feedback signal. */
  feedback_signal: FeedbackSignal;
  /** Active time spent reading in seconds (0 to 7200 seconds / 2 hours). */
  time_spent_seconds?: number | null;
  /** Count of vocabulary lookups or taps during the session (0 to 100). */
  vocabulary_lookups_count?: number | null;
  /** Whether the learner completed reading the passage. */
  completed_reading?: boolean | null;
  /** Timestamp when the reading event occurred (ISO 8601 UTC). Defaults to server time if omitted. */
  occurred_at?: string | null;
}

/**
 * Receipt acknowledging recorded post-reading feedback.
 * Mirrors `app.modules.simplification.schemas.ReadingFeedbackResponse`.
 */
export interface ReadingFeedbackResponse {
  /** Unique identifier for the recorded feedback record. */
  feedback_id: string;
  /** Identifier of the simplification session this feedback evaluates. */
  session_id: string;
  /** Confirmation flag indicating feedback was successfully recorded. */
  feedback_recorded: true;
  /** Timestamp when the feedback was recorded in the database (ISO 8601 UTC). */
  created_at: string;
}

// ── Standard Public API Error Envelopes ───────────────────────────────────────

/**
 * Error detail envelope returned by the FastAPI backend on failure.
 * Mirrors `app.core.exceptions.SecurityError` and standard exception handlers.
 */
export interface ApiErrorDetail {
  /** Error classification code (e.g. "authentication_required", "not_found", "rate_limited", "service_unavailable"). */
  code: string;
  /** Sanitized, fixed public error message. */
  message: string;
}

/**
 * Top-level error response envelope returned by the backend for all non-2xx responses.
 */
export interface ApiErrorResponse {
  /** The error payload. */
  error: ApiErrorDetail;
}
