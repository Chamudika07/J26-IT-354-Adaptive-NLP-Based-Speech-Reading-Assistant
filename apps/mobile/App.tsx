import React, { useState, useRef, useEffect } from "react";
import {
  StyleSheet,
  Text,
  View,
  SafeAreaView,
  ScrollView,
  TextInput,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import type {
  ReadingLevel,
  FeedbackSignal,
  ReadingFeedbackResponse,
  SimplificationRequest,
  SimplificationResponse,
  SimplificationStrategy,
  VocabularyItemResponse,
  WordExplanationResponse,
} from "@readbuddy/api-client";
import {
  simplificationClient,
  SimplificationApiError,
  getAuthSession,
  setAuthSession,
  clearAuthSession,
  restoreAuthSession,
  subscribeAuthSession,
  getEffectiveApiBaseUrl,
  type AuthSession,
} from "./src/services/api";
import { API_BASE_URL } from "./src/config/env";

interface ReadingLevelOption {
  value: ReadingLevel;
  label: string;
  badge: string;
  description: string;
}

interface StrategyOption {
  value: SimplificationStrategy;
  label: string;
  badge: string;
  description: string;
}

interface ApiErrorMessage {
  title: string;
  code: string;
  message: string;
  retryAfter?: number;
}

interface FeedbackOption {
  value: FeedbackSignal;
  emoji: string;
  label: string;
}

const FEEDBACK_OPTIONS: FeedbackOption[] = [
  { value: "too_hard", emoji: "😓", label: "Too Hard" },
  { value: "just_right", emoji: "😊", label: "Just Right" },
  { value: "too_easy", emoji: "🥱", label: "Too Easy" },
  { value: "skipped", emoji: "⏭️", label: "Skipped" },
];

const READING_LEVELS: ReadingLevelOption[] = [
  {
    value: "beginner",
    label: "Beginner",
    badge: "Level 1",
    description: "Shortest sentences and simplest everyday words",
  },
  {
    value: "elementary",
    label: "Elementary",
    badge: "Level 2",
    description: "Gentle reading pace with clear, familiar language",
  },
  {
    value: "intermediate",
    label: "Intermediate",
    badge: "Level 3",
    description: "Standard school-age reading with balanced phrasing",
  },
  {
    value: "advanced",
    label: "Advanced",
    badge: "Level 4",
    description: "Closer to original passage with light adjustments",
  },
];

const STRATEGIES: StrategyOption[] = [
  {
    value: "combined",
    label: "Combined (Recommended)",
    badge: "Best all-around",
    description: "Swaps difficult words and splits complex sentences",
  },
  {
    value: "vocabulary_swap",
    label: "Vocabulary Swap",
    badge: "Word focus",
    description: "Replaces tough academic words with friendly synonyms",
  },
  {
    value: "sentence_split",
    label: "Sentence Split",
    badge: "Structure",
    description: "Breaks long, winding sentences into bite-sized pieces",
  },
  {
    value: "concept_reduction",
    label: "Concept Reduction",
    badge: "Key ideas",
    description: "Focuses on the core message and removes clutter",
  },
  {
    value: "full_rewrite",
    label: "Full Rewrite",
    badge: "Deep adapt",
    description: "Completely rewrites the text in plain, natural English",
  },
];

const MAX_PASSAGE_LENGTH = 50000;

export default function App() {
  const [passage, setPassage] = useState("");
  const [selectedLevel, setSelectedLevel] = useState<ReadingLevel>("elementary");
  const [selectedStrategy, setSelectedStrategy] =
    useState<SimplificationStrategy>("combined");
  const [validationError, setValidationError] = useState<string | null>(null);

  // Stage 2 — simplification states
  const [isLoading, setIsLoading] = useState(false);
  const [apiError, setApiError] = useState<ApiErrorMessage | null>(null);
  const [simplifiedResult, setSimplifiedResult] =
    useState<SimplificationResponse | null>(null);
  const activeSimplifyAbortRef = useRef<AbortController | null>(null);
  const activeFeedbackAbortRef = useRef<AbortController | null>(null);

  // Stage 3 — word explanation states
  const [explainTerm, setExplainTerm] = useState<string | null>(null);
  const [explainResult, setExplainResult] =
    useState<WordExplanationResponse | null>(null);
  const [isExplainLoading, setIsExplainLoading] = useState(false);
  const [explainError, setExplainError] = useState<ApiErrorMessage | null>(null);
  const activeExplainAbortRef = useRef<AbortController | null>(null);

  // Stage 3 — reading feedback states
  const [selectedFeedback, setSelectedFeedback] =
    useState<FeedbackSignal | null>(null);
  const [isFeedbackLoading, setIsFeedbackLoading] = useState(false);
  const [feedbackResult, setFeedbackResult] =
    useState<ReadingFeedbackResponse | null>(null);
  const [feedbackError, setFeedbackError] =
    useState<ApiErrorMessage | null>(null);

  // Authentication & Learner Context Boundary
  const [authSession, setLocalAuthSession] = useState<AuthSession>(() =>
    getAuthSession()
  );
  const [showSessionConfig, setShowSessionConfig] = useState(false);
  const [tempLearnerId, setTempLearnerId] = useState(
    authSession.learnerId ?? ""
  );
  const [tempToken, setTempToken] = useState(authSession.accessToken ?? "");
  const [tempRefreshToken, setTempRefreshToken] = useState(
    authSession.refreshToken ?? ""
  );
  const [tempBaseUrl, setTempBaseUrl] = useState(
    authSession.apiBaseUrl ?? getEffectiveApiBaseUrl()
  );

  const effectiveEndpoint =
    authSession.apiBaseUrl?.trim() || getEffectiveApiBaseUrl();

  useEffect(() => {
    let mounted = true;
    const unsubscribe = subscribeAuthSession((session) => {
      if (mounted) setLocalAuthSession(session);
    });
    void restoreAuthSession();
    return () => {
      mounted = false;
      unsubscribe();
      activeSimplifyAbortRef.current?.abort();
      activeExplainAbortRef.current?.abort();
      activeFeedbackAbortRef.current?.abort();
    };
  }, []);

  const resetReadingState = () => {
    activeSimplifyAbortRef.current?.abort();
    activeSimplifyAbortRef.current = null;
    activeExplainAbortRef.current?.abort();
    activeExplainAbortRef.current = null;
    activeFeedbackAbortRef.current?.abort();
    activeFeedbackAbortRef.current = null;
    setIsLoading(false);
    setSimplifiedResult(null);
    setApiError(null);
    setValidationError(null);
    setExplainTerm(null);
    setExplainResult(null);
    setExplainError(null);
    setIsExplainLoading(false);
    setSelectedFeedback(null);
    setFeedbackResult(null);
    setFeedbackError(null);
    setIsFeedbackLoading(false);
  };

  const handlePassageChange = (text: string) => {
    setPassage(text);
    if (validationError) {
      setValidationError(null);
    }
    if (apiError) {
      setApiError(null);
    }
  };

  const handleClearPassage = () => {
    setPassage("");
    setValidationError(null);
    setApiError(null);
  };

  // ── Word explanation handlers (Task 2) ─────────────────────────────────────

  const handleExplainWord = async (item: VocabularyItemResponse) => {
    // Toggle: tapping the same term again closes the panel immediately
    if (explainTerm === item.term) {
      if (activeExplainAbortRef.current) {
        activeExplainAbortRef.current.abort();
        activeExplainAbortRef.current = null;
      }
      setExplainTerm(null);
      setExplainResult(null);
      setExplainError(null);
      setIsExplainLoading(false);
      return;
    }

    // Cancel any in-flight request from a previously tapped word
    if (activeExplainAbortRef.current) {
      activeExplainAbortRef.current.abort();
      activeExplainAbortRef.current = null;
    }

    setExplainTerm(item.term);
    setExplainResult(null);
    setExplainError(null);

    if (
      !authSession.learnerId ||
      (!authSession.accessToken && !authSession.refreshToken)
    ) {
      setExplainError({
        title: "Authentication Required",
        code: "authentication_required",
        message:
          "A Learner UUID and authentication session are required. Configure the session above.",
      });
      setIsExplainLoading(false);
      return;
    }

    const controller = new AbortController();
    activeExplainAbortRef.current = controller;
    setIsExplainLoading(true);

    try {
      const result = await simplificationClient.explainWord(
        authSession.learnerId,
        {
          term: item.term,
          context_sentence: item.example_sentence?.trim() || null,
          session_id: simplifiedResult?.session_id?.trim() || null,
        },
        { signal: controller.signal }
      );
      if (!controller.signal.aborted) {
        setExplainResult(result);
      }
    } catch (err: unknown) {
      if (
        controller.signal.aborted ||
        (err instanceof Error && err.name === "AbortError")
      ) {
        return;
      }
      if (err instanceof SimplificationApiError) {
        let title = "Explanation Failed";
        let message = err.message;
        switch (err.status) {
          case 401:
            title = "Authentication Required (401)";
            message = "Your session expired. Sign in again and update your session.";
            break;
          case 403:
            title = "Access Denied (403)";
            message =
              "You do not have permission to request explanations for this learner.";
            break;
          case 404:
            title = "Not Found (404)";
            message = "The learner profile was not found.";
            break;
          case 429:
            title = "Rate Limit (429)";
            message = `Provider rate limited. Please wait ${
              err.retryAfter ?? 60
            }s.`;
            break;
          case 503:
            title = "Service Unavailable (503)";
            message = "The AI vocabulary engine is currently unavailable.";
            break;
          case 0:
            title = "Network Error";
            message = `Could not reach ${effectiveEndpoint}.`;
            break;
        }
        setExplainError({
          title,
          code: err.code,
          message,
          retryAfter: err.retryAfter,
        });
      } else {
        setExplainError({
          title: "Unexpected Error",
          code: "unexpected_error",
          message:
            err instanceof Error ? err.message : "An unexpected error occurred.",
        });
      }
    } finally {
      if (activeExplainAbortRef.current === controller) {
        activeExplainAbortRef.current = null;
        setIsExplainLoading(false);
      }
    }
  };

  const handleCloseExplain = () => {
    if (activeExplainAbortRef.current) {
      activeExplainAbortRef.current.abort();
      activeExplainAbortRef.current = null;
    }
    setExplainTerm(null);
    setExplainResult(null);
    setExplainError(null);
    setIsExplainLoading(false);
  };

  // ── Reading feedback handler (Task 3) ──────────────────────────────────────

  const handleSubmitFeedback = async (signal: FeedbackSignal) => {
    if (activeFeedbackAbortRef.current || feedbackResult) return;

    if (
      !authSession.learnerId ||
      (!authSession.accessToken && !authSession.refreshToken)
    ) {
      setFeedbackError({
        title: "Authentication Required",
        code: "authentication_required",
        message:
          "A Learner UUID and authentication session are required. Configure the session above.",
      });
      return;
    }

    if (!simplifiedResult?.session_id) {
      setFeedbackError({
        title: "No Active Session",
        code: "no_session",
        message: "Simplify a passage first before providing feedback.",
      });
      return;
    }

    setSelectedFeedback(signal);
    setFeedbackError(null);
    setIsFeedbackLoading(true);
    const controller = new AbortController();
    activeFeedbackAbortRef.current = controller;

    try {
      const result = await simplificationClient.submitReadingFeedback(
        authSession.learnerId,
        simplifiedResult.session_id,
        {
          feedback_signal: signal,
          completed_reading: signal !== "skipped",
        },
        { signal: controller.signal }
      );
      if (!controller.signal.aborted) {
        setFeedbackResult(result);
      }
    } catch (err: unknown) {
      if (controller.signal.aborted) return;
      if (err instanceof SimplificationApiError) {
        let title = "Feedback Failed";
        let message = err.message;
        switch (err.status) {
          case 401:
            title = "Authentication Required (401)";
            message = "Your session expired. Sign in again and update your session.";
            break;
          case 403:
            title = "Access Denied (403)";
            message = "You do not have permission for this learner profile.";
            break;
          case 404:
            title = "Not Found (404)";
            message =
              "The learner profile or session was not found. It may have expired.";
            break;
          case 422:
            title = "Validation Error (422)";
            message = "The feedback request was rejected by the backend.";
            break;
          case 0:
            title = "Network Error";
            message = `Could not reach ${effectiveEndpoint}.`;
            break;
        }
        setFeedbackError({
          title,
          code: err.code,
          message,
          retryAfter: err.retryAfter,
        });
      } else {
        setFeedbackError({
          title: "Unexpected Error",
          code: "unexpected_error",
          message:
            err instanceof Error ? err.message : "An unexpected error occurred.",
        });
      }
      // Allow retry by clearing the selected signal on error
      setSelectedFeedback(null);
    } finally {
      if (activeFeedbackAbortRef.current === controller) {
        activeFeedbackAbortRef.current = null;
        setIsFeedbackLoading(false);
      }
    }
  };

  const handleSaveSession = async () => {
    resetReadingState();
    setPassage("");
    const trimmedId = tempLearnerId.trim() || null;
    const trimmedToken = tempToken.trim() || null;
    const trimmedRefreshToken = tempRefreshToken.trim() || null;
    const trimmedBaseUrl = tempBaseUrl.trim() || null;
    await setAuthSession({
      learnerId: trimmedId,
      accessToken: trimmedToken,
      refreshToken: trimmedRefreshToken,
      apiBaseUrl: trimmedBaseUrl,
    });
    setShowSessionConfig(false);
    if (apiError && apiError.code === "authentication_required") {
      setApiError(null);
    }
  };

  const handleClearSessionState = async () => {
    resetReadingState();
    setPassage("");
    await clearAuthSession();
    setTempLearnerId("");
    setTempToken("");
    setTempRefreshToken("");
    setTempBaseUrl(API_BASE_URL);
    setShowSessionConfig(false);
  };

  const handleSimplifyPress = async () => {
    // Prevent duplicate submissions
    if (activeSimplifyAbortRef.current) {
      return;
    }

    const trimmed = passage.trim();

    if (!trimmed) {
      setValidationError("Please enter or paste a reading passage first.");
      return;
    }

    if (passage.length > MAX_PASSAGE_LENGTH) {
      setValidationError(
        `Reading passage exceeds the maximum limit of ${MAX_PASSAGE_LENGTH.toLocaleString()} characters.`
      );
      return;
    }

    setValidationError(null);
    setApiError(null);

    // Authentication & Learner Context Boundary Check
    if (
      !authSession.learnerId ||
      (!authSession.accessToken && !authSession.refreshToken)
    ) {
      setApiError({
        title: "Learner Authentication Required",
        code: "authentication_required",
        message:
          "No active learner profile context. Text simplification requires a valid Learner UUID and authentication session. Please tap 'Configure Session' above to provide testing credentials.",
      });
      return;
    }

    resetReadingState();
    const controller = new AbortController();
    activeSimplifyAbortRef.current = controller;
    setIsLoading(true);

    try {
      const requestPayload: SimplificationRequest = {
        source_text: trimmed,
        target_reading_level: selectedLevel,
        preferred_strategy: selectedStrategy,
      };

      const result = await simplificationClient.simplifyText(
        authSession.learnerId,
        requestPayload,
        { signal: controller.signal }
      );

      // Successfully received real backend response
      if (!controller.signal.aborted) {
        setSimplifiedResult(result);
        setApiError(null);
      }
    } catch (err: unknown) {
      if (controller.signal.aborted) return;
      // Never log sensitive learner text or tokens
      if (err instanceof SimplificationApiError) {
        let title = "Request Failed";
        let message = err.message;

        switch (err.status) {
          case 401:
            title = "Authentication Required (401)";
            message =
              "The authentication session is invalid or expired. Please sign in again and update your session.";
            break;
          case 403:
            title = "Access Denied (403)";
            message =
              "You do not have permission to simplify reading passages for this learner profile.";
            break;
          case 404:
            title = "Learner Not Found (404)";
            message =
              "The specified learner ID was not found or is not associated with your account.";
            break;
          case 422:
            title = "Validation Error (422)";
            message =
              "The backend rejected the request parameters or source text.";
            break;
          case 429:
            title = "Rate Limit Exceeded (429)";
            message = `The simplification provider is currently rate limited. Please wait ${err.retryAfter ?? 60} seconds before retrying.`;
            break;
          case 503:
            title = "Service Unavailable (503)";
            message =
              "The AI text simplification engine is currently unavailable. Check that the AI provider (e.g. Gemini) is configured on the backend.";
            break;
          case 0:
            title = "Network Connection Error";
            message = `Could not reach the backend at ${effectiveEndpoint}. Ensure FastAPI is listening on the configured host and port, and your iPhone is connected to the same Wi-Fi network.`;
            break;
        }

        setApiError({
          title,
          code: err.code,
          message,
          retryAfter: err.retryAfter,
        });
      } else {
        setApiError({
          title: "Unexpected Error",
          code: "unexpected_error",
          message:
            err instanceof Error ? err.message : "An unexpected error occurred.",
        });
      }
    } finally {
      if (activeSimplifyAbortRef.current === controller) {
        activeSimplifyAbortRef.current = null;
        setIsLoading(false);
      }
    }
  };

  const isSessionActive = Boolean(
    authSession.learnerId &&
      (authSession.accessToken || authSession.refreshToken)
  );

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView
          contentContainerStyle={styles.scrollContainer}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          {/* Header Section */}
          <View style={styles.header}>
            <View style={styles.badgeRow}>
              <Text style={styles.appBadge}>ReadBuddy</Text>
              <Text style={styles.stagePill}>Stage 3: Vocabulary</Text>
            </View>
            <Text style={styles.heading}>Let's make reading easier!</Text>
            <Text style={styles.subheading}>
              Paste a passage from a book, homework, or article. Pick your reading
              level and we'll adapt it for you.
            </Text>
          </View>

          {/* Connection & Learner Session Boundary Card */}
          <View style={styles.sessionCard}>
            <View style={styles.sessionHeaderRow}>
              <View style={styles.sessionStatusIndicator}>
                <View
                  style={[
                    styles.sessionDot,
                    isSessionActive
                      ? styles.sessionDotActive
                      : styles.sessionDotInactive,
                  ]}
                />
                <Text style={styles.sessionStatusLabel}>
                  {isSessionActive
                    ? `Learner: ${authSession.learnerId?.slice(0, 8)}...`
                    : "No Active Learner Session"}
                </Text>
              </View>

              <TouchableOpacity
                onPress={() => {
                  if (!showSessionConfig) {
                    const current = getAuthSession();
                    setTempLearnerId(current.learnerId ?? "");
                    setTempToken(current.accessToken ?? "");
                    setTempRefreshToken(current.refreshToken ?? "");
                    setTempBaseUrl(current.apiBaseUrl ?? getEffectiveApiBaseUrl());
                  }
                  setShowSessionConfig(!showSessionConfig);
                }}
                accessibilityRole="button"
                accessibilityLabel="Toggle test session settings"
              >
                <Text style={styles.sessionToggleText}>
                  {showSessionConfig ? "Close" : "Configure Session"}
                </Text>
              </TouchableOpacity>
            </View>

            <Text style={styles.sessionEndpointText}>
              Backend: {effectiveEndpoint}
            </Text>

            {showSessionConfig && (
              <View style={styles.sessionConfigBox}>
                <Text style={styles.sessionConfigTitle}>
                  Test Learner Credentials
                </Text>
                <Text style={styles.sessionConfigDescription}>
                  Component 2 requires an authenticated learner context and Learner
                  UUID. The access token stays in memory; the refresh session uses
                  the device credential store.
                </Text>

                <Text style={styles.sessionFieldLabel}>Backend Base URL:</Text>
                <TextInput
                  style={styles.sessionInput}
                  placeholder="e.g. http://172.20.10.3:8001"
                  placeholderTextColor="#94A3B8"
                  value={tempBaseUrl}
                  onChangeText={setTempBaseUrl}
                  autoCapitalize="none"
                  autoCorrect={false}
                />

                <Text style={styles.sessionFieldLabel}>Learner UUID:</Text>
                <TextInput
                  style={styles.sessionInput}
                  placeholder="e.g. 00000000-0000-0000-0000-000000000000"
                  placeholderTextColor="#94A3B8"
                  value={tempLearnerId}
                  onChangeText={setTempLearnerId}
                  autoCapitalize="none"
                  autoCorrect={false}
                />

                <Text style={styles.sessionFieldLabel}>JWT Access Token:</Text>
                <TextInput
                  style={styles.sessionInput}
                  placeholder="Bearer access token from /api/v1/auth/login"
                  placeholderTextColor="#94A3B8"
                  value={tempToken}
                  onChangeText={setTempToken}
                  secureTextEntry
                  autoCapitalize="none"
                  autoCorrect={false}
                />

                <Text style={styles.sessionFieldLabel}>Refresh Token:</Text>
                <TextInput
                  style={styles.sessionInput}
                  placeholder="Refresh token from /api/v1/auth/login"
                  placeholderTextColor="#94A3B8"
                  value={tempRefreshToken}
                  onChangeText={setTempRefreshToken}
                  secureTextEntry
                  autoCapitalize="none"
                  autoCorrect={false}
                />

                <View style={styles.sessionButtonRow}>
                  <TouchableOpacity
                    style={styles.sessionSaveButton}
                    onPress={handleSaveSession}
                  >
                    <Text style={styles.sessionSaveButtonText}>Apply Session</Text>
                  </TouchableOpacity>

                  <TouchableOpacity
                    style={styles.sessionClearButton}
                    onPress={handleClearSessionState}
                  >
                    <Text style={styles.sessionClearButtonText}>Clear</Text>
                  </TouchableOpacity>
                </View>
              </View>
            )}
          </View>

          {/* Passage Input Section */}
          <View style={styles.sectionCard}>

            <View style={styles.labelRow}>
              <Text style={styles.inputLabel}>Paste your reading passage</Text>
              {passage.length > 0 && (
                <TouchableOpacity
                  onPress={handleClearPassage}
                  accessibilityRole="button"
                  accessibilityLabel="Clear passage text"
                  hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                  disabled={isLoading}
                >
                  <Text style={styles.clearButtonText}>Clear</Text>
                </TouchableOpacity>
              )}
            </View>

            <TextInput
              style={[
                styles.textInput,
                validationError ? styles.textInputError : null,
              ]}
              multiline
              numberOfLines={6}
              textAlignVertical="top"
              placeholder="Paste or type your reading passage here..."
              placeholderTextColor="#94A3B8"
              value={passage}
              onChangeText={handlePassageChange}
              editable={!isLoading}
              accessible
              accessibilityLabel="Reading passage input"
              accessibilityHint="Enter the text you want simplified"
            />

            <View style={styles.counterRow}>
              {validationError ? (
                <Text style={styles.errorMessage}>{validationError}</Text>
              ) : (
                <Text style={styles.helperText}>
                  Supports passages up to 50,000 characters
                </Text>
              )}
              <Text style={styles.charCounter}>
                {passage.length.toLocaleString()} /{" "}
                {MAX_PASSAGE_LENGTH.toLocaleString()}
              </Text>
            </View>
          </View>

          {/* Reading Level Selector */}
          <View style={styles.sectionCard}>
            <Text style={styles.sectionTitle}>1. Choose reading level</Text>
            <Text style={styles.sectionDescription}>
              Select the level that feels most comfortable for you:
            </Text>

            <View style={styles.optionsList}>
              {READING_LEVELS.map((item) => {
                const isSelected = selectedLevel === item.value;
                return (
                  <TouchableOpacity
                    key={item.value}
                    style={[
                      styles.optionCard,
                      isSelected && styles.optionCardSelected,
                    ]}
                    onPress={() => setSelectedLevel(item.value)}
                    disabled={isLoading}
                    accessibilityRole="radio"
                    accessibilityState={{ selected: isSelected }}
                    accessibilityLabel={`${item.label} level: ${item.description}`}
                  >
                    <View style={styles.optionHeader}>
                      <View style={styles.optionTitleRow}>
                        <View
                          style={[
                            styles.radioCircle,
                            isSelected && styles.radioCircleSelected,
                          ]}
                        >
                          {isSelected && <View style={styles.radioDot} />}
                        </View>
                        <Text
                          style={[
                            styles.optionLabel,
                            isSelected && styles.optionLabelSelected,
                          ]}
                        >
                          {item.label}
                        </Text>
                      </View>
                      <Text
                        style={[
                          styles.optionBadge,
                          isSelected && styles.optionBadgeSelected,
                        ]}
                      >
                        {item.badge}
                      </Text>
                    </View>
                    <Text
                      style={[
                        styles.optionDescription,
                        isSelected && styles.optionDescriptionSelected,
                      ]}
                    >
                      {item.description}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>

          {/* Simplification Strategy Selector */}
          <View style={styles.sectionCard}>
            <Text style={styles.sectionTitle}>2. Choose simplification strategy</Text>
            <Text style={styles.sectionDescription}>
              Pick how the assistant should adapt your passage:
            </Text>

            <View style={styles.optionsList}>
              {STRATEGIES.map((item) => {
                const isSelected = selectedStrategy === item.value;
                return (
                  <TouchableOpacity
                    key={item.value}
                    style={[
                      styles.optionCard,
                      isSelected && styles.optionCardSelected,
                    ]}
                    onPress={() => setSelectedStrategy(item.value)}
                    disabled={isLoading}
                    accessibilityRole="radio"
                    accessibilityState={{ selected: isSelected }}
                    accessibilityLabel={`${item.label} strategy: ${item.description}`}
                  >
                    <View style={styles.optionHeader}>
                      <View style={styles.optionTitleRow}>
                        <View
                          style={[
                            styles.radioCircle,
                            isSelected && styles.radioCircleSelected,
                          ]}
                        >
                          {isSelected && <View style={styles.radioDot} />}
                        </View>
                        <Text
                          style={[
                            styles.optionLabel,
                            isSelected && styles.optionLabelSelected,
                          ]}
                        >
                          {item.label}
                        </Text>
                      </View>
                      <Text
                        style={[
                          styles.optionBadge,
                          isSelected && styles.optionBadgeSelected,
                        ]}
                      >
                        {item.badge}
                      </Text>
                    </View>
                    <Text
                      style={[
                        styles.optionDescription,
                        isSelected && styles.optionDescriptionSelected,
                      ]}
                    >
                      {item.description}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>

          {/* Action Button Section */}
          <View style={styles.actionSection}>
            <TouchableOpacity
              style={[
                styles.primaryButton,
                isLoading && styles.primaryButtonDisabled,
              ]}
              onPress={handleSimplifyPress}
              disabled={isLoading}
              accessibilityRole="button"
              accessibilityLabel="Simplify my text"
              accessibilityHint="Sends reading passage to the FastAPI simplification service"
            >
              {isLoading ? (
                <View style={styles.loadingRow}>
                  <ActivityIndicator color="#FFFFFF" size="small" />
                  <Text style={styles.primaryButtonText}>
                    Simplifying passage...
                  </Text>
                </View>
              ) : (
                <Text style={styles.primaryButtonText}>Simplify my text</Text>
              )}
            </TouchableOpacity>

            {/* Error Message Box */}
            {apiError && (
              <View style={styles.errorBox}>
                <View style={styles.errorHeader}>
                  <Text style={styles.errorIcon}>⚠️</Text>
                  <Text style={styles.errorTitle}>{apiError.title}</Text>
                  <Text style={styles.errorCodePill}>{apiError.code}</Text>
                </View>
                <Text style={styles.errorDescription}>{apiError.message}</Text>
                <TouchableOpacity
                  style={styles.errorDismissButton}
                  onPress={() => setApiError(null)}
                >
                  <Text style={styles.errorDismissText}>Dismiss</Text>
                </TouchableOpacity>
              </View>
            )}
          </View>

          {/* Result Area */}
          <View style={styles.resultSection}>
            <Text style={styles.resultSectionTitle}>Simplified Reading Result</Text>

            {simplifiedResult ? (
              <View style={styles.resultCard}>
                <View style={styles.resultHeader}>
                  <View style={styles.resultTagsRow}>
                    <Text style={styles.resultTag}>
                      {simplifiedResult.target_reading_level.toUpperCase()}
                    </Text>
                    <Text style={styles.resultTagSecondary}>
                      {simplifiedResult.strategy_applied}
                    </Text>
                  </View>
                  <TouchableOpacity
                    onPress={resetReadingState}
                    hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                  >
                    <Text style={styles.clearResultText}>Reset</Text>
                  </TouchableOpacity>
                </View>

                <Text style={styles.simplifiedText} selectable>
                  {simplifiedResult.simplified_text}
                </Text>

                {/* Vocabulary Items Section (Task 1 & Task 2) */}
                {simplifiedResult.vocabulary_items &&
                  simplifiedResult.vocabulary_items.length > 0 && (
                    <View style={styles.vocabSection}>
                      <Text style={styles.vocabSectionTitle}>
                        📚 Vocabulary Helpers ({simplifiedResult.vocabulary_items.length})
                      </Text>
                      <Text style={styles.vocabSectionHint}>
                        Tap any word to see a child-friendly explanation, examples, and synonyms!
                      </Text>

                      {simplifiedResult.vocabulary_items.map((item, idx) => {
                        const isExpanded = explainTerm === item.term;
                        return (
                          <View
                            key={`${item.term}-${idx}`}
                            style={styles.vocabItemWrapper}
                          >
                            <TouchableOpacity
                              style={[
                                styles.vocabCard,
                                isExpanded && styles.vocabCardActive,
                              ]}
                              onPress={() => handleExplainWord(item)}
                              accessibilityRole="button"
                              accessibilityLabel={`Word: ${item.term}. Tap to explain.`}
                            >
                              <View style={styles.vocabCardHeader}>
                                <Text
                                  style={[
                                    styles.vocabTerm,
                                    isExpanded && styles.vocabTermActive,
                                  ]}
                                >
                                  {item.term}
                                </Text>
                                <View style={styles.vocabTermRight}>
                                  {isExplainLoading && isExpanded ? (
                                    <ActivityIndicator
                                      size="small"
                                      color="#4F46E5"
                                    />
                                  ) : (
                                    <Text style={styles.vocabChevron}>
                                      {isExpanded ? "▲" : "▼"}
                                    </Text>
                                  )}
                                </View>
                              </View>

                              <Text style={styles.vocabQuickDef}>
                                {item.simplified_definition}
                              </Text>

                              {item.synonyms &&
                                item.synonyms.filter((s) => Boolean(s && s.trim())).length > 0 && (
                                  <View style={styles.synonymRow}>
                                    {item.synonyms
                                      .filter((s) => Boolean(s && s.trim()))
                                      .map((syn, synIdx) => (
                                        <View
                                          key={synIdx}
                                          style={styles.synonymChip}
                                        >
                                          <Text style={styles.synonymChipText}>
                                            {syn}
                                          </Text>
                                        </View>
                                      ))}
                                  </View>
                                )}
                            </TouchableOpacity>

                            {/* Task 2: Inline Word Explanation Panel */}
                            {isExpanded && (
                              <View style={styles.explainPanel}>
                                {isExplainLoading ? (
                                  <View style={styles.explainLoading}>
                                    <View style={styles.explainLoadingContent}>
                                      <ActivityIndicator
                                        size="small"
                                        color="#059669"
                                      />
                                      <Text style={styles.explainLoadingText}>
                                        Asking ReadBuddy AI for a helpful explanation...
                                      </Text>
                                    </View>
                                    <TouchableOpacity
                                      onPress={handleCloseExplain}
                                      hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                                    >
                                      <Text style={styles.explainCloseText}>
                                        Cancel
                                      </Text>
                                    </TouchableOpacity>
                                  </View>
                                ) : explainError ? (
                                  <View style={styles.explainError}>
                                    <View style={styles.explainResultHeader}>
                                      <Text style={styles.explainErrorTitle}>
                                        ⚠️ {explainError.title}
                                      </Text>
                                      <TouchableOpacity
                                        onPress={handleCloseExplain}
                                        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                                      >
                                        <Text style={styles.explainCloseText}>
                                          Close
                                        </Text>
                                      </TouchableOpacity>
                                    </View>
                                    <Text style={styles.explainErrorMessage}>
                                      {explainError.message}
                                    </Text>
                                  </View>
                                ) : explainResult &&
                                  explainResult.item.term.trim().toLowerCase() === item.term.trim().toLowerCase() ? (
                                  <View>
                                    <View style={styles.explainResultHeader}>
                                      <Text style={styles.explainResultTerm}>
                                        💡 {explainResult.item.term}
                                      </Text>
                                      <TouchableOpacity
                                        onPress={handleCloseExplain}
                                        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                                      >
                                        <Text style={styles.explainCloseText}>
                                          Close
                                        </Text>
                                      </TouchableOpacity>
                                    </View>

                                    <Text style={styles.explainDefinition}>
                                      {explainResult.item.simplified_definition}
                                    </Text>

                                    {explainResult.item.example_sentence &&
                                    explainResult.item.example_sentence.trim().length > 0 ? (
                                      <View style={styles.explainExampleBox}>
                                        <Text
                                          style={styles.explainExampleLabel}
                                        >
                                          Example Sentence:
                                        </Text>
                                        <Text
                                          style={styles.explainExampleText}
                                        >
                                          "{explainResult.item.example_sentence.trim()}"
                                        </Text>
                                      </View>
                                    ) : null}

                                    {explainResult.item.synonyms &&
                                      explainResult.item.synonyms.filter((s) => Boolean(s && s.trim())).length > 0 && (
                                        <View
                                          style={styles.explainSynonymSection}
                                        >
                                          <Text
                                            style={styles.explainSynonymLabel}
                                          >
                                            Similar Words:
                                          </Text>
                                          <View style={styles.synonymRow}>
                                            {explainResult.item.synonyms
                                              .filter((s) => Boolean(s && s.trim()))
                                              .map((syn, sIdx) => (
                                                <View
                                                  key={sIdx}
                                                  style={
                                                    styles.synonymChipEmphasis
                                                  }
                                                >
                                                  <Text
                                                    style={
                                                      styles.synonymChipEmphasisText
                                                    }
                                                  >
                                                    {syn}
                                                  </Text>
                                                </View>
                                              ))}
                                          </View>
                                        </View>
                                      )}
                                  </View>
                                ) : (
                                  <View>
                                    <View style={styles.explainResultHeader}>
                                      <Text style={styles.explainResultTerm}>
                                        💡 {item.term}
                                      </Text>
                                      <TouchableOpacity
                                        onPress={handleCloseExplain}
                                        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                                      >
                                        <Text style={styles.explainCloseText}>
                                          Close
                                        </Text>
                                      </TouchableOpacity>
                                    </View>
                                    <Text style={styles.explainDefinition}>
                                      {item.simplified_definition}
                                    </Text>
                                    {item.example_sentence && item.example_sentence.trim().length > 0 ? (
                                      <View style={styles.explainExampleBox}>
                                        <Text
                                          style={styles.explainExampleLabel}
                                        >
                                          Example:
                                        </Text>
                                        <Text
                                          style={styles.explainExampleText}
                                        >
                                          "{item.example_sentence.trim()}"
                                        </Text>
                                      </View>
                                    ) : null}
                                  </View>
                                )}
                              </View>
                            )}
                          </View>
                        );
                      })}
                    </View>
                  )}

                {simplifiedResult.warnings &&
                  simplifiedResult.warnings.length > 0 && (
                    <View style={styles.warningsCard}>
                      <Text style={styles.warningsTitle}>Guidance Notes:</Text>
                      {simplifiedResult.warnings.map((warn, idx) => (
                        <Text key={idx} style={styles.warningItem}>
                          • {warn}
                        </Text>
                      ))}
                    </View>
                  )}

                {/* Task 3: Reading Feedback Section */}
                <View style={styles.feedbackSection}>
                  <Text style={styles.feedbackTitle}>
                    📝 How was this reading?
                  </Text>
                  <Text style={styles.feedbackHint}>
                    {feedbackResult
                      ? "Thanks for your feedback! It helps ReadBuddy learn."
                      : "Let us know how the simplified text felt:"}
                  </Text>

                  <View style={styles.feedbackOptionsRow}>
                    {FEEDBACK_OPTIONS.map((option) => {
                      const isSelected = selectedFeedback === option.value;
                      const isSubmitted = feedbackResult !== null;
                      const isDisabled =
                        isFeedbackLoading || (isSubmitted && !isSelected);

                      return (
                        <TouchableOpacity
                          key={option.value}
                          style={[
                            styles.feedbackOption,
                            isSelected && styles.feedbackOptionSelected,
                            isSubmitted &&
                              isSelected &&
                              styles.feedbackOptionSubmitted,
                            isDisabled && styles.feedbackOptionDisabled,
                          ]}
                          onPress={() => handleSubmitFeedback(option.value)}
                          disabled={isDisabled}
                          accessibilityRole="button"
                          accessibilityLabel={`Feedback: ${option.label}`}
                          accessibilityState={{
                            selected: isSelected,
                            disabled: isDisabled,
                          }}
                        >
                          <Text style={styles.feedbackEmoji}>
                            {option.emoji}
                          </Text>
                          <Text
                            style={[
                              styles.feedbackLabel,
                              isSelected && styles.feedbackLabelSelected,
                              isSubmitted &&
                                isSelected &&
                                styles.feedbackLabelSubmitted,
                            ]}
                          >
                            {option.label}
                          </Text>
                          {isFeedbackLoading && isSelected && (
                            <ActivityIndicator
                              size="small"
                              color="#4F46E5"
                              style={styles.feedbackSpinner}
                            />
                          )}
                          {isSubmitted && isSelected && (
                            <Text style={styles.feedbackCheckmark}>✓</Text>
                          )}
                        </TouchableOpacity>
                      );
                    })}
                  </View>

                  {feedbackError && (
                    <View style={styles.feedbackErrorBox}>
                      <Text style={styles.feedbackErrorTitle}>
                        ⚠️ {feedbackError.title}
                      </Text>
                      <Text style={styles.feedbackErrorMessage}>
                        {feedbackError.message}
                      </Text>
                      <TouchableOpacity
                        onPress={() => setFeedbackError(null)}
                        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                      >
                        <Text style={styles.feedbackErrorDismiss}>Dismiss</Text>
                      </TouchableOpacity>
                    </View>
                  )}

                  {feedbackResult && (
                    <View style={styles.feedbackSuccessBox}>
                      <Text style={styles.feedbackSuccessText}>
                        ✅ Feedback recorded • ID:{" "}
                        {feedbackResult.feedback_id.slice(0, 8)}...
                      </Text>
                    </View>
                  )}
                </View>

                <View style={styles.resultFooter}>
                  <Text style={styles.resultMetaText}>
                    Session: {simplifiedResult.session_id.slice(0, 8)}... • Attempt{" "}
                    {simplifiedResult.adaptation_attempt}
                  </Text>
                </View>
              </View>
            ) : (
              <View style={styles.emptyStateCard}>
                <Text style={styles.emptyStateIcon}>📖</Text>
                <Text style={styles.emptyStateTitle}>
                  Your simplified text will appear here
                </Text>
                <Text style={styles.emptyStateDescription}>
                  Paste your reading text above, choose your reading level and
                  strategy, and tap "Simplify my text" to receive adapted reading
                  support from the ReadBuddy API.
                </Text>
                <View style={styles.emptyStatePill}>
                  <Text style={styles.emptyStatePillText}>
                    Ready for Live Simplification Requests
                  </Text>
                </View>
              </View>
            )}
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: "#F8FAFC",
  },
  flex: {
    flex: 1,
  },
  scrollContainer: {
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 48,
  },
  header: {
    marginBottom: 16,
  },
  badgeRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginBottom: 10,
  },
  appBadge: {
    alignSelf: "flex-start",
    backgroundColor: "#4338CA",
    color: "#FFFFFF",
    fontSize: 13,
    fontWeight: "800",
    letterSpacing: 0.8,
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: 8,
    textTransform: "uppercase",
  },
  stagePill: {
    alignSelf: "flex-start",
    backgroundColor: "#EEF2FF",
    color: "#4338CA",
    fontSize: 12,
    fontWeight: "700",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#C7D2FE",
  },
  heading: {
    fontSize: 26,
    fontWeight: "800",
    color: "#0F172A",
    letterSpacing: -0.4,
    marginBottom: 6,
  },
  subheading: {
    fontSize: 15,
    color: "#475569",
    lineHeight: 22,
  },
  sessionCard: {
    backgroundColor: "#F1F5F9",
    borderRadius: 12,
    padding: 12,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  sessionHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  sessionStatusIndicator: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  sessionDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  sessionDotActive: {
    backgroundColor: "#10B981",
  },
  sessionDotInactive: {
    backgroundColor: "#F59E0B",
  },
  sessionStatusLabel: {
    fontSize: 12,
    fontWeight: "700",
    color: "#334155",
  },
  sessionToggleText: {
    fontSize: 12,
    fontWeight: "600",
    color: "#4338CA",
  },
  sessionEndpointText: {
    fontSize: 11,
    color: "#64748B",
    marginTop: 4,
  },
  sessionConfigBox: {
    marginTop: 10,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: "#E2E8F0",
  },
  sessionConfigTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: "#1E293B",
    marginBottom: 2,
  },
  sessionConfigDescription: {
    fontSize: 11,
    color: "#64748B",
    marginBottom: 8,
    lineHeight: 16,
  },
  sessionFieldLabel: {
    fontSize: 11,
    fontWeight: "600",
    color: "#475569",
    marginBottom: 2,
    marginTop: 4,
  },
  sessionInput: {
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#CBD5E1",
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
    fontSize: 12,
    color: "#0F172A",
    marginBottom: 6,
  },
  sessionButtonRow: {
    flexDirection: "row",
    gap: 8,
    marginTop: 6,
  },
  sessionSaveButton: {
    backgroundColor: "#4338CA",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
  },
  sessionSaveButtonText: {
    color: "#FFFFFF",
    fontSize: 12,
    fontWeight: "700",
  },
  sessionClearButton: {
    backgroundColor: "#E2E8F0",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
  },
  sessionClearButtonText: {
    color: "#475569",
    fontSize: 12,
    fontWeight: "600",
  },
  sectionCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    padding: 18,
    marginBottom: 18,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 1,
  },
  labelRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 8,
  },
  inputLabel: {
    fontSize: 16,
    fontWeight: "700",
    color: "#1E293B",
  },
  clearButtonText: {
    fontSize: 13,
    fontWeight: "600",
    color: "#DC2626",
    paddingHorizontal: 4,
  },
  textInput: {
    backgroundColor: "#F8FAFC",
    borderWidth: 1.5,
    borderColor: "#CBD5E1",
    borderRadius: 12,
    padding: 14,
    fontSize: 16,
    lineHeight: 24,
    color: "#0F172A",
    minHeight: 130,
  },
  textInputError: {
    borderColor: "#DC2626",
    backgroundColor: "#FEF2F2",
  },
  counterRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: 8,
    gap: 8,
  },
  helperText: {
    fontSize: 12,
    color: "#64748B",
    flex: 1,
  },
  errorMessage: {
    fontSize: 13,
    fontWeight: "600",
    color: "#DC2626",
    flex: 1,
  },
  charCounter: {
    fontSize: 12,
    color: "#64748B",
    fontVariant: ["tabular-nums"],
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: "#1E293B",
    marginBottom: 4,
  },
  sectionDescription: {
    fontSize: 13,
    color: "#64748B",
    marginBottom: 14,
    lineHeight: 18,
  },
  optionsList: {
    gap: 10,
  },
  optionCard: {
    backgroundColor: "#F8FAFC",
    borderWidth: 1.5,
    borderColor: "#E2E8F0",
    borderRadius: 12,
    padding: 14,
    minHeight: 64,
    justifyContent: "center",
  },
  optionCardSelected: {
    backgroundColor: "#EEF2FF",
    borderColor: "#4F46E5",
  },
  optionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 4,
  },
  optionTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    flex: 1,
  },
  radioCircle: {
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 2,
    borderColor: "#94A3B8",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#FFFFFF",
  },
  radioCircleSelected: {
    borderColor: "#4F46E5",
  },
  radioDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: "#4F46E5",
  },
  optionLabel: {
    fontSize: 15,
    fontWeight: "700",
    color: "#334155",
  },
  optionLabelSelected: {
    color: "#1E1B4B",
  },
  optionBadge: {
    fontSize: 11,
    fontWeight: "700",
    color: "#64748B",
    backgroundColor: "#F1F5F9",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    textTransform: "uppercase",
  },
  optionBadgeSelected: {
    color: "#4338CA",
    backgroundColor: "#E0E7FF",
  },
  optionDescription: {
    fontSize: 13,
    color: "#64748B",
    marginLeft: 30,
    lineHeight: 18,
  },
  optionDescriptionSelected: {
    color: "#4338CA",
  },
  actionSection: {
    marginBottom: 20,
  },
  primaryButton: {
    backgroundColor: "#4F46E5",
    borderRadius: 14,
    paddingVertical: 16,
    paddingHorizontal: 24,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#4F46E5",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.25,
    shadowRadius: 8,
    elevation: 3,
    minHeight: 54,
  },
  primaryButtonDisabled: {
    backgroundColor: "#818CF8",
    shadowOpacity: 0.1,
  },
  loadingRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  primaryButtonText: {
    color: "#FFFFFF",
    fontSize: 17,
    fontWeight: "700",
    letterSpacing: 0.2,
  },
  errorBox: {
    marginTop: 14,
    backgroundColor: "#FEF2F2",
    borderWidth: 1,
    borderColor: "#FECACA",
    borderRadius: 12,
    padding: 14,
  },
  errorHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginBottom: 6,
  },
  errorIcon: {
    fontSize: 16,
  },
  errorTitle: {
    fontSize: 14,
    fontWeight: "700",
    color: "#991B1B",
    flex: 1,
  },
  errorCodePill: {
    fontSize: 10,
    fontWeight: "700",
    color: "#DC2626",
    backgroundColor: "#FEE2E2",
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    fontFamily: Platform.OS === "ios" ? "Courier" : "monospace",
  },
  errorDescription: {
    fontSize: 13,
    color: "#7F1D1D",
    lineHeight: 18,
    marginBottom: 8,
  },
  errorDismissButton: {
    alignSelf: "flex-end",
    paddingVertical: 4,
    paddingHorizontal: 8,
  },
  errorDismissText: {
    fontSize: 12,
    fontWeight: "700",
    color: "#991B1B",
  },
  resultSection: {
    marginTop: 4,
  },
  resultSectionTitle: {
    fontSize: 18,
    fontWeight: "700",
    color: "#0F172A",
    marginBottom: 10,
  },
  resultCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    padding: 20,
    borderWidth: 1.5,
    borderColor: "#4F46E5",
    shadowColor: "#4F46E5",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 2,
  },
  resultHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 14,
    paddingBottom: 10,
    borderBottomWidth: 1,
    borderBottomColor: "#F1F5F9",
  },
  resultTagsRow: {
    flexDirection: "row",
    gap: 6,
  },
  resultTag: {
    backgroundColor: "#EEF2FF",
    color: "#4338CA",
    fontSize: 11,
    fontWeight: "700",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  resultTagSecondary: {
    backgroundColor: "#F1F5F9",
    color: "#475569",
    fontSize: 11,
    fontWeight: "600",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  clearResultText: {
    fontSize: 13,
    fontWeight: "600",
    color: "#64748B",
  },
  simplifiedText: {
    fontSize: 17,
    lineHeight: 27,
    color: "#0F172A",
    marginBottom: 16,
  },
  warningsCard: {
    backgroundColor: "#FFFBEB",
    borderWidth: 1,
    borderColor: "#FDE68A",
    borderRadius: 10,
    padding: 12,
    marginBottom: 14,
  },
  warningsTitle: {
    fontSize: 12,
    fontWeight: "700",
    color: "#92400E",
    marginBottom: 4,
  },
  warningItem: {
    fontSize: 12,
    color: "#B45309",
    lineHeight: 18,
  },
  resultFooter: {
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: "#F1F5F9",
  },
  resultMetaText: {
    fontSize: 11,
    color: "#94A3B8",
    fontFamily: Platform.OS === "ios" ? "Courier" : "monospace",
  },
  emptyStateCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    borderWidth: 1.5,
    borderColor: "#E2E8F0",
    borderStyle: "dashed",
    padding: 24,
    alignItems: "center",
    textAlign: "center",
  },
  emptyStateIcon: {
    fontSize: 40,
    marginBottom: 12,
  },
  emptyStateTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: "#1E293B",
    marginBottom: 8,
    textAlign: "center",
  },
  emptyStateDescription: {
    fontSize: 14,
    color: "#64748B",
    lineHeight: 20,
    textAlign: "center",
    marginBottom: 16,
    maxWidth: 320,
  },
  emptyStatePill: {
    backgroundColor: "#F1F5F9",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
  },
  emptyStatePillText: {
    fontSize: 12,
    fontWeight: "600",
    color: "#475569",
  },

  // ── Task 1: Vocabulary section styles ────────────────────────────────────
  vocabSection: {
    marginTop: 4,
    marginBottom: 4,
  },
  vocabSectionTitle: {
    fontSize: 15,
    fontWeight: "700",
    color: "#1E293B",
    marginBottom: 2,
  },
  vocabSectionHint: {
    fontSize: 12,
    color: "#64748B",
    marginBottom: 10,
  },
  vocabItemWrapper: {
    marginBottom: 8,
  },
  vocabCard: {
    backgroundColor: "#F8FAFC",
    borderWidth: 1.5,
    borderColor: "#E2E8F0",
    borderRadius: 12,
    padding: 12,
  },
  vocabCardActive: {
    backgroundColor: "#EEF2FF",
    borderColor: "#4F46E5",
    borderBottomLeftRadius: 0,
    borderBottomRightRadius: 0,
  },
  vocabCardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 4,
  },
  vocabTerm: {
    fontSize: 16,
    fontWeight: "700",
    color: "#1E293B",
    flex: 1,
  },
  vocabTermActive: {
    color: "#3730A3",
  },
  vocabTermRight: {
    marginLeft: 8,
    minWidth: 24,
    alignItems: "center",
  },
  vocabChevron: {
    fontSize: 12,
    color: "#94A3B8",
  },
  vocabQuickDef: {
    fontSize: 13,
    color: "#475569",
    lineHeight: 18,
    marginBottom: 6,
  },
  synonymRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
    marginTop: 2,
  },
  synonymChip: {
    backgroundColor: "#E0E7FF",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  synonymChipText: {
    fontSize: 11,
    fontWeight: "600",
    color: "#3730A3",
  },

  // ── Task 2: Explanation panel styles ─────────────────────────────────────
  explainPanel: {
    backgroundColor: "#F0FDF4",
    borderWidth: 1.5,
    borderColor: "#86EFAC",
    borderTopWidth: 0,
    borderBottomLeftRadius: 12,
    borderBottomRightRadius: 12,
    padding: 14,
    marginTop: -2,
  },
  explainLoading: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 8,
  },
  explainLoadingContent: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    flex: 1,
  },
  explainLoadingText: {
    fontSize: 13,
    color: "#065F46",
    fontStyle: "italic",
  },
  explainError: {
    backgroundColor: "#FEF2F2",
    borderWidth: 1,
    borderColor: "#FECACA",
    borderRadius: 8,
    padding: 10,
  },
  explainErrorTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: "#991B1B",
    flex: 1,
  },
  explainErrorMessage: {
    fontSize: 12,
    color: "#7F1D1D",
    lineHeight: 17,
    marginBottom: 6,
  },
  explainResultHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 8,
  },
  explainResultTerm: {
    fontSize: 15,
    fontWeight: "800",
    color: "#065F46",
    flex: 1,
  },
  explainCloseText: {
    fontSize: 12,
    fontWeight: "700",
    color: "#059669",
  },
  explainDefinition: {
    fontSize: 14,
    color: "#064E3B",
    lineHeight: 21,
    marginBottom: 10,
  },
  explainExampleBox: {
    backgroundColor: "#DCFCE7",
    borderRadius: 8,
    padding: 10,
    marginBottom: 10,
  },
  explainExampleLabel: {
    fontSize: 11,
    fontWeight: "700",
    color: "#065F46",
    marginBottom: 2,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  explainExampleText: {
    fontSize: 13,
    color: "#064E3B",
    lineHeight: 19,
    fontStyle: "italic",
  },
  explainSynonymSection: {
    marginTop: 2,
  },
  explainSynonymLabel: {
    fontSize: 11,
    fontWeight: "700",
    color: "#065F46",
    marginBottom: 6,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  synonymChipEmphasis: {
    backgroundColor: "#BBF7D0",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
  },
  synonymChipEmphasisText: {
    fontSize: 12,
    fontWeight: "700",
    color: "#065F46",
  },

  // ── Task 3: Reading Feedback styles ────────────────────────────────────────
  feedbackSection: {
    marginTop: 16,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: "#E2E8F0",
  },
  feedbackTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: "#1E293B",
    marginBottom: 2,
  },
  feedbackHint: {
    fontSize: 13,
    color: "#64748B",
    marginBottom: 12,
  },
  feedbackOptionsRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 8,
  },
  feedbackOption: {
    flex: 1,
    alignItems: "center",
    paddingVertical: 12,
    paddingHorizontal: 4,
    borderRadius: 12,
    borderWidth: 1.5,
    borderColor: "#E2E8F0",
    backgroundColor: "#FFFFFF",
  },
  feedbackOptionSelected: {
    borderColor: "#4F46E5",
    backgroundColor: "#EEF2FF",
  },
  feedbackOptionSubmitted: {
    borderColor: "#059669",
    backgroundColor: "#F0FDF4",
  },
  feedbackOptionDisabled: {
    opacity: 0.45,
  },
  feedbackEmoji: {
    fontSize: 24,
    marginBottom: 4,
  },
  feedbackLabel: {
    fontSize: 11,
    fontWeight: "600",
    color: "#475569",
    textAlign: "center",
  },
  feedbackLabelSelected: {
    color: "#4338CA",
    fontWeight: "700",
  },
  feedbackLabelSubmitted: {
    color: "#059669",
  },
  feedbackSpinner: {
    marginTop: 4,
  },
  feedbackCheckmark: {
    fontSize: 14,
    fontWeight: "800",
    color: "#059669",
    marginTop: 2,
  },
  feedbackErrorBox: {
    marginTop: 10,
    backgroundColor: "#FEF2F2",
    borderWidth: 1,
    borderColor: "#FECACA",
    borderRadius: 8,
    padding: 10,
  },
  feedbackErrorTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: "#991B1B",
    marginBottom: 2,
  },
  feedbackErrorMessage: {
    fontSize: 12,
    color: "#7F1D1D",
    lineHeight: 17,
    marginBottom: 6,
  },
  feedbackErrorDismiss: {
    fontSize: 12,
    fontWeight: "700",
    color: "#B91C1C",
  },
  feedbackSuccessBox: {
    marginTop: 10,
    backgroundColor: "#F0FDF4",
    borderWidth: 1,
    borderColor: "#BBF7D0",
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 8,
  },
  feedbackSuccessText: {
    fontSize: 12,
    fontWeight: "600",
    color: "#065F46",
  },
});
