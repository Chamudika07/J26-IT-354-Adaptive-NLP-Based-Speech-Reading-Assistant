import React, { useState, useRef, useEffect, useMemo } from "react";
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
  Image,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import * as Print from "expo-print";
import * as Sharing from "expo-sharing";
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
  accentColor: string;
  backgroundColor: string;
  borderColor: string;
  iconBg: string;
}

interface StrategyOption {
  value: SimplificationStrategy;
  label: string;
  badge: string;
  description: string;
  accentColor: string;
  backgroundColor: string;
  borderColor: string;
  iconBg: string;
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
  subLabel: string;
  accentColor: string;
  backgroundColor: string;
  borderColor: string;
}

export type ReadingLevelSuggestionKind = "adjust" | "keep" | "boundary" | "none";

export interface ReadingLevelSuggestion {
  kind: ReadingLevelSuggestionKind;
  actualLevel: ReadingLevel;
  suggestedLevel: ReadingLevel | null;
  title: string;
  message: string;
}

const READING_LEVEL_ORDER: readonly ReadingLevel[] = [
  "beginner",
  "elementary",
  "intermediate",
  "advanced",
];

const READING_LEVEL_LABELS: Record<ReadingLevel, string> = {
  beginner: "Beginner",
  elementary: "Elementary",
  intermediate: "Intermediate",
  advanced: "Advanced",
};

export const getReadingLevelSuggestion = (
  feedback: FeedbackSignal,
  actualLevel: ReadingLevel
): ReadingLevelSuggestion => {
  const levelIndex = READING_LEVEL_ORDER.indexOf(actualLevel);

  if (feedback === "too_hard") {
    if (levelIndex <= 0) {
      return {
        kind: "boundary",
        actualLevel,
        suggestedLevel: null,
        title: "You already have the most reading support",
        message:
          "Beginner is the most supported level. You can keep it and ask a trusted adult for help if the passage still feels tricky.",
      };
    }
    const suggestedLevel = READING_LEVEL_ORDER[levelIndex - 1];
    return {
      kind: "adjust",
      actualLevel,
      suggestedLevel,
      title: "Would a little more support help?",
      message: `${READING_LEVEL_LABELS[suggestedLevel]} uses shorter sentences and more familiar words. You can choose it for your next passage.`,
    };
  }

  if (feedback === "too_easy") {
    if (levelIndex >= READING_LEVEL_ORDER.length - 1) {
      return {
        kind: "boundary",
        actualLevel,
        suggestedLevel: null,
        title: "You are already using the lightest support",
        message:
          "Advanced keeps the most original wording. You can keep it or choose any level that feels useful next time.",
      };
    }
    const suggestedLevel = READING_LEVEL_ORDER[levelIndex + 1];
    return {
      kind: "adjust",
      actualLevel,
      suggestedLevel,
      title: "Ready for a little less support?",
      message: `${READING_LEVEL_LABELS[suggestedLevel]} keeps a little more sentence and word challenge. You can choose it for your next passage.`,
    };
  }

  if (feedback === "just_right") {
    return {
      kind: "keep",
      actualLevel,
      suggestedLevel: null,
      title: "This level can stay",
      message: `${READING_LEVEL_LABELS[actualLevel]} felt right for this passage. You can keep it next time or choose a different amount of support whenever you want.`,
    };
  }

  return {
    kind: "none",
    actualLevel,
    suggestedLevel: null,
    title: "No level suggestion this time",
    message: "You skipped this question, so ReadBuddy will not guess. Choose any level that feels useful for your next passage.",
  };
};

interface SampleStory {
  id: string;
  title: string;
  emoji: string;
  tag: string;
  accentColor: string;
  backgroundColor: string;
  borderColor: string;
  image: number;
  text: string;
}

type ResultTextView = "simplified" | "compare";

export type TextHighlightKind = "changed" | "vocabulary";

export interface TextHighlightSegment {
  text: string;
  kind: TextHighlightKind | null;
}

export interface PassageHighlights {
  original: TextHighlightSegment[];
  simplified: TextHighlightSegment[];
  usedFallback: boolean;
}

interface WordToken {
  value: string;
  comparisonValue: string;
  vocabularyValue: string;
  start: number;
  end: number;
}

interface TextRange {
  start: number;
  end: number;
}

export interface LearningPackSnapshot {
  originalText: string | null;
  simplifiedText: string;
  readingLevel: string;
  strategy: string;
  vocabularyItems: Array<{
    term: string;
    simplifiedDefinition: string;
    exampleSentence: string | null;
    synonyms: string[];
  }>;
}

export const escapeLearningPackHtml = (value: string): string =>
  value.replace(
    /[&<>"']/g,
    (character) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      })[character] ?? character
  );

const formatLearningPackLabel = (value: string): string =>
  value
    .split("_")
    .filter(Boolean)
    .map((part) => `${part.charAt(0).toUpperCase()}${part.slice(1)}`)
    .join(" ");

export const buildLearningPackHtml = (snapshot: LearningPackSnapshot): string => {
  const vocabularyHtml = snapshot.vocabularyItems.length
    ? snapshot.vocabularyItems
        .map((item, index) => {
          const example = item.exampleSentence;
          const hasExample = Boolean(example && example.trim().length > 0);
          const synonyms = item.synonyms.filter((synonym) => synonym.trim().length > 0);
          return `
            <section class="word-card word-card-${index % 4}">
              <h3>${escapeLearningPackHtml(item.term)}</h3>
              <p class="definition-label">What it means</p>
              <p class="definition">${escapeLearningPackHtml(item.simplifiedDefinition)}</p>
              ${
                hasExample && example
                  ? `<p class="detail-label">Example</p><p class="example">${escapeLearningPackHtml(example)}</p>`
                  : ""
              }
              ${
                synonyms.length
                  ? `<p class="detail-label">Similar words</p><p class="synonyms">${synonyms
                      .map((synonym) => `<span>${escapeLearningPackHtml(synonym)}</span>`)
                      .join("")}</p>`
                  : ""
              }
            </section>`;
        })
        .join("")
    : `<p class="empty-words">No extra vocabulary words were needed for this passage.</p>`;

  const originalHtml =
    snapshot.originalText !== null
      ? `<section class="passage-card original">
          <h2>Original Passage</h2>
          <p class="passage">${escapeLearningPackHtml(snapshot.originalText)}</p>
        </section>`
      : "";

  return `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>ReadBuddy Learning Pack</title>
    <style>
      @page { margin: 28px; }
      * { box-sizing: border-box; }
      body { margin: 0; color: #1e293b; background: #ffffff; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; font-size: 16px; line-height: 1.65; }
      header { padding: 24px; color: #ffffff; background: #6d28d9; border-radius: 22px; margin-bottom: 20px; }
      h1 { margin: 0 0 6px; font-size: 30px; line-height: 1.2; }
      header p { margin: 0; color: #ede9fe; }
      .labels { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 20px; }
      .label { display: inline-block; padding: 6px 12px; color: #4338ca; background: #eef2ff; border: 1px solid #c7d2fe; border-radius: 999px; font-size: 13px; font-weight: 700; }
      section { break-inside: avoid; }
      .passage-card { padding: 20px; border: 2px solid #a7f3d0; border-radius: 18px; background: #ecfdf5; margin-bottom: 18px; }
      .passage-card.original { border-color: #fde68a; background: #fffbeb; }
      h2 { margin: 0 0 10px; color: #134e4a; font-size: 21px; }
      .original h2 { color: #92400e; }
      .passage { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; }
      .vocabulary-heading { margin: 26px 0 12px; color: #4c1d95; font-size: 23px; }
      .word-card { padding: 17px; border: 2px solid #bfdbfe; border-radius: 16px; background: #eff6ff; margin-bottom: 12px; }
      .word-card-1 { border-color: #fde68a; background: #fffbeb; }
      .word-card-2 { border-color: #ddd6fe; background: #f5f3ff; }
      .word-card-3 { border-color: #fbcfe8; background: #fdf2f8; }
      h3 { margin: 0 0 8px; color: #1d4ed8; font-size: 20px; }
      .definition-label, .detail-label { margin: 8px 0 2px; color: #64748b; font-size: 11px; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; }
      .definition, .example { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; }
      .example { font-style: italic; }
      .synonyms { display: flex; flex-wrap: wrap; gap: 6px; margin: 4px 0 0; }
      .synonyms span { display: inline-block; padding: 3px 9px; background: #ffffff; border: 1px solid #cbd5e1; border-radius: 999px; }
      .empty-words { padding: 16px; color: #475569; background: #f8fafc; border-radius: 14px; }
      footer { margin-top: 24px; padding-top: 12px; color: #64748b; border-top: 1px solid #e2e8f0; font-size: 12px; text-align: center; }
    </style>
  </head>
  <body>
    <header>
      <h1>ReadBuddy Learning Pack</h1>
      <p>Your reading adventure, ready to revisit.</p>
    </header>
    <div class="labels">
      <span class="label">Reading level: ${escapeLearningPackHtml(formatLearningPackLabel(snapshot.readingLevel))}</span>
      <span class="label">Strategy: ${escapeLearningPackHtml(formatLearningPackLabel(snapshot.strategy))}</span>
    </div>
    <section class="passage-card">
      <h2>Simplified Passage</h2>
      <p class="passage">${escapeLearningPackHtml(snapshot.simplifiedText)}</p>
    </section>
    ${originalHtml}
    <h2 class="vocabulary-heading">Vocabulary Helpers</h2>
    ${vocabularyHtml}
    <footer>Made with ReadBuddy</footer>
  </body>
</html>`;
};

// The exact LCS matrix is intentionally bounded. Above this limit, the
// unmatched middle is highlighted conservatively so a long rewrite cannot
// block the mobile JavaScript thread with quadratic work.
export const MAX_DIFF_MATRIX_CELLS = 250_000;

const tokenizeWords = (text: string): WordToken[] => {
  const tokens: WordToken[] = [];
  const expression = /[\p{L}\p{M}\p{N}]+/gu;
  let match: RegExpExecArray | null;
  while ((match = expression.exec(text)) !== null) {
    tokens.push({
      value: match[0],
      comparisonValue: match[0],
      vocabularyValue: match[0].toLowerCase(),
      start: match.index,
      end: match.index + match[0].length,
    });
  }
  return tokens;
};

const rangesFromWordIndexes = (
  tokens: WordToken[],
  indexes: Set<number>
): TextRange[] => {
  const sortedIndexes = [...indexes].sort((left, right) => left - right);
  const ranges: TextRange[] = [];
  let firstIndex: number | null = null;
  let previousIndex: number | null = null;

  const finishRange = () => {
    if (firstIndex !== null && previousIndex !== null) {
      ranges.push({
        start: tokens[firstIndex].start,
        end: tokens[previousIndex].end,
      });
    }
  };

  for (const index of sortedIndexes) {
    if (firstIndex === null || previousIndex === null) {
      firstIndex = index;
    } else if (index !== previousIndex + 1) {
      finishRange();
      firstIndex = index;
    }
    previousIndex = index;
  }
  finishRange();
  return ranges;
};

const findVocabularyRanges = (
  tokens: WordToken[],
  vocabularyTerms: string[]
): TextRange[] => {
  const termSequences = vocabularyTerms
    .map((term) => tokenizeWords(term).map((token) => token.vocabularyValue))
    .filter((sequence) => sequence.length > 0)
    .sort((left, right) => {
      if (left.length !== right.length) return right.length - left.length;
      return left.join("\u0000").localeCompare(right.join("\u0000"));
    });
  const uniqueSequences = termSequences.filter(
    (sequence, index) =>
      index === 0 ||
      sequence.join("\u0000") !== termSequences[index - 1].join("\u0000")
  );
  const occupiedIndexes = new Set<number>();
  const ranges: TextRange[] = [];

  for (const sequence of uniqueSequences) {
    for (let start = 0; start <= tokens.length - sequence.length; start += 1) {
      let matches = true;
      for (let offset = 0; offset < sequence.length; offset += 1) {
        if (
          occupiedIndexes.has(start + offset) ||
          tokens[start + offset].vocabularyValue !== sequence[offset]
        ) {
          matches = false;
          break;
        }
      }
      if (!matches) continue;
      for (let offset = 0; offset < sequence.length; offset += 1) {
        occupiedIndexes.add(start + offset);
      }
      ranges.push({
        start: tokens[start].start,
        end: tokens[start + sequence.length - 1].end,
      });
    }
  }
  return ranges;
};

const sliceTextByRanges = (
  text: string,
  changedRanges: TextRange[],
  vocabularyRanges: TextRange[]
): TextHighlightSegment[] => {
  const boundaries = new Set<number>([0, text.length]);
  for (const range of [...changedRanges, ...vocabularyRanges]) {
    boundaries.add(range.start);
    boundaries.add(range.end);
  }
  const orderedBoundaries = [...boundaries].sort((left, right) => left - right);
  const segments: TextHighlightSegment[] = [];

  for (let index = 0; index < orderedBoundaries.length - 1; index += 1) {
    const start = orderedBoundaries[index];
    const end = orderedBoundaries[index + 1];
    if (end <= start) continue;
    const inRange = (range: TextRange) => range.start <= start && range.end >= end;
    const kind = vocabularyRanges.some(inRange)
      ? "vocabulary"
      : changedRanges.some(inRange)
        ? "changed"
        : null;
    segments.push({ text: text.slice(start, end), kind });
  }

  return segments.length > 0 ? segments : [{ text, kind: null }];
};

export const calculatePassageHighlights = (
  originalText: string,
  simplifiedText: string,
  vocabularyTerms: string[]
): PassageHighlights => {
  const originalTokens = tokenizeWords(originalText);
  const simplifiedTokens = tokenizeWords(simplifiedText);
  const changedOriginalIndexes = new Set<number>();
  const changedSimplifiedIndexes = new Set<number>();

  let prefixLength = 0;
  while (
    prefixLength < originalTokens.length &&
    prefixLength < simplifiedTokens.length &&
    originalTokens[prefixLength].comparisonValue ===
      simplifiedTokens[prefixLength].comparisonValue
  ) {
    prefixLength += 1;
  }

  let suffixLength = 0;
  while (
    suffixLength < originalTokens.length - prefixLength &&
    suffixLength < simplifiedTokens.length - prefixLength &&
    originalTokens[originalTokens.length - 1 - suffixLength].comparisonValue ===
      simplifiedTokens[simplifiedTokens.length - 1 - suffixLength].comparisonValue
  ) {
    suffixLength += 1;
  }

  const originalMiddleLength =
    originalTokens.length - prefixLength - suffixLength;
  const simplifiedMiddleLength =
    simplifiedTokens.length - prefixLength - suffixLength;
  const usedFallback =
    originalMiddleLength * simplifiedMiddleLength > MAX_DIFF_MATRIX_CELLS;

  if (usedFallback) {
    for (let index = 0; index < originalMiddleLength; index += 1) {
      changedOriginalIndexes.add(prefixLength + index);
    }
    for (let index = 0; index < simplifiedMiddleLength; index += 1) {
      changedSimplifiedIndexes.add(prefixLength + index);
    }
  } else {
    const columns = simplifiedMiddleLength + 1;
    const matrix = new Uint32Array((originalMiddleLength + 1) * columns);
    for (let originalIndex = originalMiddleLength - 1; originalIndex >= 0; originalIndex -= 1) {
      for (
        let simplifiedIndex = simplifiedMiddleLength - 1;
        simplifiedIndex >= 0;
        simplifiedIndex -= 1
      ) {
        const matrixIndex = originalIndex * columns + simplifiedIndex;
        if (
          originalTokens[prefixLength + originalIndex].comparisonValue ===
          simplifiedTokens[prefixLength + simplifiedIndex].comparisonValue
        ) {
          matrix[matrixIndex] =
            matrix[(originalIndex + 1) * columns + simplifiedIndex + 1] + 1;
        } else {
          matrix[matrixIndex] = Math.max(
            matrix[(originalIndex + 1) * columns + simplifiedIndex],
            matrix[originalIndex * columns + simplifiedIndex + 1]
          );
        }
      }
    }

    let originalIndex = 0;
    let simplifiedIndex = 0;
    while (
      originalIndex < originalMiddleLength &&
      simplifiedIndex < simplifiedMiddleLength
    ) {
      if (
        originalTokens[prefixLength + originalIndex].comparisonValue ===
        simplifiedTokens[prefixLength + simplifiedIndex].comparisonValue
      ) {
        originalIndex += 1;
        simplifiedIndex += 1;
      } else if (
        matrix[(originalIndex + 1) * columns + simplifiedIndex] >=
        matrix[originalIndex * columns + simplifiedIndex + 1]
      ) {
        changedOriginalIndexes.add(prefixLength + originalIndex);
        originalIndex += 1;
      } else {
        changedSimplifiedIndexes.add(prefixLength + simplifiedIndex);
        simplifiedIndex += 1;
      }
    }
    while (originalIndex < originalMiddleLength) {
      changedOriginalIndexes.add(prefixLength + originalIndex);
      originalIndex += 1;
    }
    while (simplifiedIndex < simplifiedMiddleLength) {
      changedSimplifiedIndexes.add(prefixLength + simplifiedIndex);
      simplifiedIndex += 1;
    }
  }

  const originalChangedRanges = rangesFromWordIndexes(
    originalTokens,
    changedOriginalIndexes
  );
  const simplifiedChangedRanges = rangesFromWordIndexes(
    simplifiedTokens,
    changedSimplifiedIndexes
  );
  const originalVocabularyRanges = findVocabularyRanges(
    originalTokens,
    vocabularyTerms
  );
  const simplifiedVocabularyRanges = findVocabularyRanges(
    simplifiedTokens,
    vocabularyTerms
  );

  return {
    original: sliceTextByRanges(
      originalText,
      originalChangedRanges,
      originalVocabularyRanges
    ),
    simplified: sliceTextByRanges(
      simplifiedText,
      simplifiedChangedRanges,
      simplifiedVocabularyRanges
    ),
    usedFallback,
  };
};

const SAMPLE_STORIES: SampleStory[] = [
  {
    id: "dragon",
    title: "The Emerald Dragon",
    emoji: "🐉",
    tag: "Fantasy",
    accentColor: "#059669",
    backgroundColor: "#ECFDF5",
    borderColor: "#A7F3D0",
    image: require("./assets/home/emerald-dragon.png"),
    text: "Deep within the Whispering Caverns, an ancient emerald dragon named Zephyr guarded a chamber of luminescent crystals. These dazzling stones emitted a mysterious radiant glow that illuminated subterranean pathways. The cautious villagers believed the dragon's territory was perilous, yet Zephyr simply sought tranquility and nourishment from geothermal springs.",
  },
  {
    id: "space",
    title: "Mission to Mars",
    emoji: "🚀",
    tag: "Sci-Fi",
    accentColor: "#2563EB",
    backgroundColor: "#EFF6FF",
    borderColor: "#BFDBFE",
    image: require("./assets/home/mission-mars.png"),
    text: "Astronaut Maya adjusted her pressurized helmet as the planetary rover traversed the treacherous terrain of Mars. Colossal dust storms threatened communication satellites in orbit. Her autonomous companion robot detected subterranean ice reservoirs beneath the oxidized bedrock, signaling a triumphant breakthrough for the interplanetary expedition.",
  },
  {
    id: "ocean",
    title: "Coral Reef Mystery",
    emoji: "🐬",
    tag: "Ocean",
    accentColor: "#7C3AED",
    backgroundColor: "#F5F3FF",
    borderColor: "#DDD6FE",
    image: require("./assets/home/coral-dolphin.png"),
    text: "Beneath the turquoise waves of the Caribbean sea, an adventurous dolphin named Echo investigated an ancient Spanish galleon. Encrusted with vibrant polyps and delicate sea anemones, the wooden vessel sheltered elusive marine creatures from pelagic predators navigating the tempestuous currents.",
  },
];

const FEEDBACK_OPTIONS: FeedbackOption[] = [
  {
    value: "too_hard",
    emoji: "😓",
    label: "Too Hard",
    subLabel: "Words felt tricky",
    accentColor: "#E11D48",
    backgroundColor: "#FFF1F2",
    borderColor: "#FECDD3",
  },
  {
    value: "just_right",
    emoji: "😊",
    label: "Just Right",
    subLabel: "Felt awesome!",
    accentColor: "#059669",
    backgroundColor: "#ECFDF5",
    borderColor: "#A7F3D0",
  },
  {
    value: "too_easy",
    emoji: "🥱",
    label: "Too Easy",
    subLabel: "Ready for more",
    accentColor: "#D97706",
    backgroundColor: "#FFFBEB",
    borderColor: "#FDE68A",
  },
  {
    value: "skipped",
    emoji: "⏭️",
    label: "Skipped",
    subLabel: "Moved on",
    accentColor: "#7C3AED",
    backgroundColor: "#F5F3FF",
    borderColor: "#DDD6FE",
  },
];

const READING_LEVELS: ReadingLevelOption[] = [
  {
    value: "beginner",
    label: "Beginner",
    badge: "Most Support",
    description: "Very short sentences and familiar everyday words",
    accentColor: "#059669",
    backgroundColor: "#ECFDF5",
    borderColor: "#A7F3D0",
    iconBg: "#D1FAE5",
  },
  {
    value: "elementary",
    label: "Elementary",
    badge: "Extra Support",
    description: "Clear sentences with familiar words and gentle explanations",
    accentColor: "#D97706",
    backgroundColor: "#FFFBEB",
    borderColor: "#FDE68A",
    iconBg: "#FEF3C7",
  },
  {
    value: "intermediate",
    label: "Intermediate",
    badge: "Some Support",
    description: "Varied sentences with a few more challenging words",
    accentColor: "#2563EB",
    backgroundColor: "#EFF6FF",
    borderColor: "#BFDBFE",
    iconBg: "#DBEAFE",
  },
  {
    value: "advanced",
    label: "Advanced",
    badge: "Light Support",
    description: "Keeps more of the original wording, detail, and sentence style",
    accentColor: "#7C3AED",
    backgroundColor: "#F5F3FF",
    borderColor: "#DDD6FE",
    iconBg: "#EDE9FE",
  },
];

const STRATEGIES: StrategyOption[] = [
  {
    value: "combined",
    label: "Combined (Recommended)",
    badge: "Auto-Pick",
    description: "Balances shorter sentences and simpler vocabulary automatically",
    accentColor: "#0EA5E9",
    backgroundColor: "#F0F9FF",
    borderColor: "#BAE6FD",
    iconBg: "#E0F2FE",
  },
  {
    value: "sentence_split",
    label: "Sentence Split",
    badge: "Short & Sweet",
    description: "Breaks long, winding sentences into bite-sized pieces",
    accentColor: "#EC4899",
    backgroundColor: "#FDF2F8",
    borderColor: "#FBCFE8",
    iconBg: "#FCE7F3",
  },
  {
    value: "vocabulary_swap",
    label: "Vocabulary Swap",
    badge: "Friendly Words",
    description: "Replaces complex terms with familiar alternatives",
    accentColor: "#8B5CF6",
    backgroundColor: "#F5F3FF",
    borderColor: "#DDD6FE",
    iconBg: "#EDE9FE",
  },
  {
    value: "concept_reduction",
    label: "Concept Reduction",
    badge: "Explain & Define",
    description: "Focuses on core ideas, filtering non-essential details",
    accentColor: "#D97706",
    backgroundColor: "#FFFBEB",
    borderColor: "#FDE68A",
    iconBg: "#FEF3C7",
  },
  {
    value: "full_rewrite",
    label: "Full Rewrite",
    badge: "Story Explorer",
    description: "Rephrases the passage from scratch at the target level",
    accentColor: "#F97316",
    backgroundColor: "#FFF7ED",
    borderColor: "#FED7AA",
    iconBg: "#FFEDD5",
  },
];

const VOCABULARY_PALETTES = [
  { backgroundColor: "#EFF6FF", borderColor: "#BFDBFE", accentColor: "#2563EB", tagBg: "#DBEAFE" },
  { backgroundColor: "#FFFBEB", borderColor: "#FDE68A", accentColor: "#D97706", tagBg: "#FEF3C7" },
  { backgroundColor: "#F5F3FF", borderColor: "#DDD6FE", accentColor: "#7C3AED", tagBg: "#EDE9FE" },
  { backgroundColor: "#FDF2F8", borderColor: "#FBCFE8", accentColor: "#EC4899", tagBg: "#FCE7F3" },
  { backgroundColor: "#ECFDF5", borderColor: "#A7F3D0", accentColor: "#059669", tagBg: "#D1FAE5" },
] as const;

const MAX_PASSAGE_LENGTH = 50000;

export default function App() {
  const [passage, setPassage] = useState("");
  const [selectedLevel, setSelectedLevel] = useState<ReadingLevel>("elementary");
  const [selectedStrategy, setSelectedStrategy] =
    useState<SimplificationStrategy>("combined");
  const [validationError, setValidationError] = useState<string | null>(null);

  const [isLoading, setIsLoading] = useState(false);
  const [apiError, setApiError] = useState<ApiErrorMessage | null>(null);
  const [simplifiedResult, setSimplifiedResult] =
    useState<SimplificationResponse | null>(null);
  const [submittedSourceText, setSubmittedSourceText] = useState<string | null>(
    null
  );
  const [resultTextView, setResultTextView] =
    useState<ResultTextView>("simplified");
  const [showHighlights, setShowHighlights] = useState(true);
  const [reviewedVocabularyItems, setReviewedVocabularyItems] = useState<Set<string>>(
    () => new Set()
  );
  const [isLearningPackBusy, setIsLearningPackBusy] = useState(false);
  const [learningPackError, setLearningPackError] = useState<string | null>(null);
  const activeLearningPackRef = useRef(false);
  const learningPackGenerationRef = useRef(0);
  const activeSimplifyAbortRef = useRef<AbortController | null>(null);
  const activeFeedbackAbortRef = useRef<AbortController | null>(null);

  const [explainTerm, setExplainTerm] = useState<string | null>(null);
  const [explainItemKey, setExplainItemKey] = useState<string | null>(null);
  const [explainResult, setExplainResult] =
    useState<WordExplanationResponse | null>(null);
  const [isExplainLoading, setIsExplainLoading] = useState(false);
  const [explainError, setExplainError] = useState<ApiErrorMessage | null>(null);
  const activeExplainAbortRef = useRef<AbortController | null>(null);

  const [selectedFeedback, setSelectedFeedback] =
    useState<FeedbackSignal | null>(null);
  const [isFeedbackLoading, setIsFeedbackLoading] = useState(false);
  const [feedbackResult, setFeedbackResult] =
    useState<ReadingFeedbackResponse | null>(null);
  const [feedbackError, setFeedbackError] =
    useState<ApiErrorMessage | null>(null);
  const [acceptedSuggestedLevel, setAcceptedSuggestedLevel] =
    useState<ReadingLevel | null>(null);

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

  const [currentScreen, setCurrentScreen] = useState<"home" | "guided">("home");
  const [guidedStep, setGuidedStep] = useState<1 | 2 | 3>(1);

  const effectiveEndpoint =
    authSession.apiBaseUrl?.trim() || getEffectiveApiBaseUrl();
  const passageHighlights = useMemo(
    () =>
      calculatePassageHighlights(
        submittedSourceText ?? "",
        simplifiedResult?.simplified_text ?? "",
        simplifiedResult?.vocabulary_items.map((item) => item.term) ?? []
      ),
    [submittedSourceText, simplifiedResult]
  );
  const feedbackLevelSuggestion = useMemo(
    () =>
      feedbackResult && selectedFeedback && simplifiedResult
        ? getReadingLevelSuggestion(selectedFeedback, simplifiedResult.target_reading_level)
        : null,
    [feedbackResult, selectedFeedback, simplifiedResult]
  );

  const renderHighlightedPassage = (
    text: string,
    segments: TextHighlightSegment[],
    variant: "comparison" | "simplified",
    accessibilityLabel: string
  ) => (
    <Text
      style={variant === "comparison" ? styles.comparisonText : styles.simplifiedText}
      selectable
      accessibilityLabel={accessibilityLabel}
    >
      {showHighlights
        ? segments.map((segment, index) => (
            <Text
              key={`${index}-${segment.kind ?? "plain"}`}
              style={
                segment.kind === "vocabulary"
                  ? styles.vocabularyHighlight
                  : segment.kind === "changed"
                    ? styles.changedHighlight
                    : undefined
              }
            >
              {segment.text}
            </Text>
          ))
        : text}
    </Text>
  );

  useEffect(() => {
    let mounted = true;
    const unsubscribe = subscribeAuthSession((session) => {
      if (mounted) setLocalAuthSession(session);
    });
    void restoreAuthSession();
    return () => {
      mounted = false;
      learningPackGenerationRef.current += 1;
      activeLearningPackRef.current = false;
      unsubscribe();
      activeSimplifyAbortRef.current?.abort();
      activeExplainAbortRef.current?.abort();
      activeFeedbackAbortRef.current?.abort();
    };
  }, []);

  const resetReadingState = () => {
    learningPackGenerationRef.current += 1;
    activeLearningPackRef.current = false;
    activeSimplifyAbortRef.current?.abort();
    activeSimplifyAbortRef.current = null;
    activeExplainAbortRef.current?.abort();
    activeExplainAbortRef.current = null;
    activeFeedbackAbortRef.current?.abort();
    activeFeedbackAbortRef.current = null;
    setIsLoading(false);
    setSimplifiedResult(null);
    setSubmittedSourceText(null);
    setResultTextView("simplified");
    setShowHighlights(true);
    setReviewedVocabularyItems(new Set());
    setIsLearningPackBusy(false);
    setLearningPackError(null);
    setApiError(null);
    setValidationError(null);
    setExplainTerm(null);
    setExplainItemKey(null);
    setExplainResult(null);
    setExplainError(null);
    setIsExplainLoading(false);
    setSelectedFeedback(null);
    setFeedbackResult(null);
    setFeedbackError(null);
    setIsFeedbackLoading(false);
    setAcceptedSuggestedLevel(null);
    setCurrentScreen("guided");
    setGuidedStep(1);
  };

  const handlePassageChange = (text: string) => {
    learningPackGenerationRef.current += 1;
    activeLearningPackRef.current = false;
    setPassage(text);
    setSubmittedSourceText(null);
    setResultTextView("simplified");
    setShowHighlights(true);
    setReviewedVocabularyItems(new Set());
    setIsLearningPackBusy(false);
    setLearningPackError(null);
    if (validationError) {
      setValidationError(null);
    }
    if (apiError) {
      setApiError(null);
    }
  };

  const handleClearPassage = () => {
    setPassage("");
    setReviewedVocabularyItems(new Set());
    setValidationError(null);
    setApiError(null);
  };

  const handleSelectSampleStory = (story: SampleStory) => {
    handlePassageChange(story.text);
    setCurrentScreen("guided");
    setGuidedStep(2);
  };

  const handleExplainWord = async (item: VocabularyItemResponse, itemKey: string) => {
    if (explainItemKey === itemKey && activeExplainAbortRef.current) {
      return;
    }

    if (explainItemKey === itemKey && !explainError) {
      if (activeExplainAbortRef.current) {
        activeExplainAbortRef.current.abort();
        activeExplainAbortRef.current = null;
      }
      setExplainTerm(null);
      setExplainItemKey(null);
      setExplainResult(null);
      return;
    }

    if (activeExplainAbortRef.current) {
      activeExplainAbortRef.current.abort();
      activeExplainAbortRef.current = null;
    }

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
      setExplainTerm(item.term);
      setExplainItemKey(itemKey);
      return;
    }

    setExplainTerm(item.term);
    setExplainItemKey(itemKey);
    setExplainResult(null);
    setExplainError(null);
    setIsExplainLoading(true);

    const controller = new AbortController();
    activeExplainAbortRef.current = controller;

    try {
      const response = await simplificationClient.explainWord(
        authSession.learnerId,
        {
          term: item.term,
          session_id: simplifiedResult?.session_id,
          context_sentence: item.example_sentence,
        },
        { signal: controller.signal }
      );
      if (!controller.signal.aborted) {
        setExplainResult(response);
      }
    } catch (err: unknown) {
      if (controller.signal.aborted) return;
      if (err instanceof SimplificationApiError) {
        let title = "Explanation Failed";
        let message = err.message;
        switch (err.status) {
          case 401:
            title = "Session Expired (401)";
            message =
              "Your login session has expired. Please sign in again and update your test session.";
            break;
          case 403:
            title = "Access Denied (403)";
            message =
              "You do not have permission to view word explanations for this learner profile.";
            break;
          case 404:
            title = "Learner Not Found (404)";
            message =
              "The learner profile or session was not found. Please re-run simplification.";
            break;
          case 422:
            title = "Invalid Request (422)";
            message =
              "The vocabulary term could not be processed by the server.";
            break;
          case 429:
            title = "Rate Limit Exceeded (429)";
            message = `Too many explanation requests. Please wait ${err.retryAfter ?? 60} seconds before retrying.`;
            break;
          case 503:
            title = "Service Unavailable (503)";
            message =
              "The AI vocabulary engine is currently unavailable. Please check backend provider configuration.";
            break;
          case 0:
            title = "Network Error";
            message = `Could not reach ${effectiveEndpoint}. Ensure the backend is reachable from this device.`;
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
    setExplainItemKey(null);
    setExplainResult(null);
    setExplainError(null);
    setIsExplainLoading(false);
  };

  const handleAcknowledgeVocabulary = (itemKey: string) => {
    setReviewedVocabularyItems((current) => {
      if (current.has(itemKey)) return current;
      const next = new Set(current);
      next.add(itemKey);
      return next;
    });
  };

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
    setAcceptedSuggestedLevel(null);
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
      setSelectedFeedback(null);
    } finally {
      if (activeFeedbackAbortRef.current === controller) {
        activeFeedbackAbortRef.current = null;
        setIsFeedbackLoading(false);
      }
    }
  };

  const handleAcceptSuggestedLevel = (level: ReadingLevel) => {
    setSelectedLevel(level);
    setAcceptedSuggestedLevel(level);
  };

  const handleSaveSession = async () => {
    resetReadingState();
    setPassage("");
    setSelectedLevel("elementary");
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
    setSelectedLevel("elementary");
    await clearAuthSession();
    setTempLearnerId("");
    setTempToken("");
    setTempRefreshToken("");
    setTempBaseUrl(API_BASE_URL);
    setShowSessionConfig(false);
  };

  const handleSimplifyPress = async () => {
    if (activeSimplifyAbortRef.current) {
      return;
    }

    const sourceTextForDisplay = passage;
    const trimmed = passage.trim();

    if (!trimmed) {
      setValidationError("Please enter or paste a reading passage first.");
      setGuidedStep(2);
      return;
    }

    if (passage.length > MAX_PASSAGE_LENGTH) {
      setValidationError(
        `Reading passage exceeds the maximum limit of ${MAX_PASSAGE_LENGTH.toLocaleString()} characters.`
      );
      setGuidedStep(2);
      return;
    }

    setValidationError(null);
    setApiError(null);
    setSimplifiedResult(null);
    setSubmittedSourceText(null);
    setResultTextView("simplified");
    setShowHighlights(true);
    setReviewedVocabularyItems(new Set());
    learningPackGenerationRef.current += 1;
    activeLearningPackRef.current = false;
    setIsLearningPackBusy(false);
    setLearningPackError(null);
    setExplainTerm(null);
    setExplainItemKey(null);
    setExplainResult(null);
    setExplainError(null);
    setSelectedFeedback(null);
    setFeedbackResult(null);
    setFeedbackError(null);
    setAcceptedSuggestedLevel(null);

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

      if (!controller.signal.aborted) {
        setSimplifiedResult(result);
        setSubmittedSourceText(sourceTextForDisplay);
        setResultTextView("simplified");
        setShowHighlights(true);
        setReviewedVocabularyItems(new Set());
        setApiError(null);
      }
    } catch (err: unknown) {
      if (controller.signal.aborted) return;
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
            message = `Could not reach the backend at ${effectiveEndpoint}. Ensure FastAPI is listening on the configured host and port, and your device is on the same network.`;
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

  const createLearningPackSnapshot = (): LearningPackSnapshot | null => {
    if (!simplifiedResult) return null;
    return {
      originalText: submittedSourceText,
      simplifiedText: simplifiedResult.simplified_text,
      readingLevel: simplifiedResult.target_reading_level,
      strategy: simplifiedResult.strategy_applied,
      vocabularyItems: simplifiedResult.vocabulary_items.map((item) => ({
        term: item.term,
        simplifiedDefinition: item.simplified_definition,
        exampleSentence: item.example_sentence ?? null,
        synonyms: [...(item.synonyms ?? [])],
      })),
    };
  };

  const handleLearningPackAction = async (action: "print" | "share") => {
    if (activeLearningPackRef.current) return;
    const snapshot = createLearningPackSnapshot();
    if (!snapshot) return;

    const generation = learningPackGenerationRef.current;
    const html = buildLearningPackHtml(snapshot);
    activeLearningPackRef.current = true;
    setIsLearningPackBusy(true);
    setLearningPackError(null);

    try {
      if (action === "print") {
        await Print.printAsync({ html });
        return;
      }

      const { uri } = await Print.printToFileAsync({ html });
      if (generation !== learningPackGenerationRef.current) return;
      const sharingAvailable = await Sharing.isAvailableAsync();
      if (generation !== learningPackGenerationRef.current) return;
      if (!sharingAvailable) {
        throw new Error("Sharing is not available on this device.");
      }
      await Sharing.shareAsync(uri, {
        mimeType: "application/pdf",
        UTI: "com.adobe.pdf",
        dialogTitle: "Share or save your ReadBuddy Learning Pack",
      });
    } catch (error: unknown) {
      if (generation === learningPackGenerationRef.current) {
        setLearningPackError(
          error instanceof Error && error.message === "Sharing is not available on this device."
            ? error.message
            : "We could not prepare your learning pack. Please try again."
        );
      }
    } finally {
      if (generation === learningPackGenerationRef.current) {
        activeLearningPackRef.current = false;
        setIsLearningPackBusy(false);
      }
    }
  };

  const isSessionActive = Boolean(
    authSession.learnerId &&
      (authSession.accessToken || authSession.refreshToken)
  );

  // ─────────────────────────────────────────────────────────────────────────────
  // ILLUSTRATION: Buddy Mascot — cartoon purple book character
  // ─────────────────────────────────────────────────────────────────────────────
  const renderBuddyMascot = (
    mood: "welcome" | "read" | "cheer" | "think" = "welcome"
  ) => (
    <View style={styles.buddyWrap} accessible accessibilityLabel="Buddy the ReadBuddy book mascot">
      {/* floating decoration stars */}
      <Text style={[styles.buddyFloatStar, { top: 2, left: 6, fontSize: 18, color: "#FCD34D" }]}>✦</Text>
      <Text style={[styles.buddyFloatStar, { top: 4, right: 4, fontSize: 14, color: "#F9A8D4" }]}>★</Text>
      <Text style={[styles.buddyFloatStar, { bottom: 32, right: 2, fontSize: 11, color: "#FCD34D" }]}>✧</Text>

      {/* mood badge: party hat for cheer, thinking cloud for think */}
      {mood === "cheer" && (
        <View style={styles.buddyMoodHat}>
          <View style={styles.buddyHatBrim} />
          <View style={styles.buddyHatBody} />
          <Text style={styles.buddyHatStar}>★</Text>
        </View>
      )}
      {mood === "think" && (
        <Text style={styles.buddyThinkCloud}>🤔</Text>
      )}

      {/* open-book page wings behind the cover */}
      <View style={[styles.buddyPage, styles.buddyPageLeft]} />
      <View style={[styles.buddyPage, styles.buddyPageRight]} />

      {/* ── main purple book cover ── */}
      <View style={styles.buddyCover}>
        {/* yellow bookmark ribbon at top */}
        <View style={styles.buddyBookmark}>
          <Text style={styles.buddyBookmarkStar}>★</Text>
        </View>

        {/* white face area */}
        <View style={styles.buddyFace}>
          {/* reading glasses (shown in read mode) */}
          {mood === "read" && (
            <View style={styles.buddyGlassesRow}>
              <View style={styles.buddyGlassRim} />
              <View style={styles.buddyGlassBridge} />
              <View style={styles.buddyGlassRim} />
            </View>
          )}

          {/* eyes */}
          <View style={styles.buddyEyesRow}>
            <View style={styles.buddyEyeWhite}>
              <View style={styles.buddyEyePupil}>
                <View style={styles.buddyEyeShine} />
              </View>
            </View>
            <View style={styles.buddyEyeWhite}>
              <View style={styles.buddyEyePupil}>
                <View style={styles.buddyEyeShine} />
              </View>
            </View>
          </View>

          {/* cheeks + smile row */}
          <View style={styles.buddyExprRow}>
            <View style={styles.buddyCheek} />
            <View style={styles.buddySmileWrap}>
              <View style={styles.buddySmile}>
                <View style={styles.buddyTeeth} />
              </View>
            </View>
            <View style={styles.buddyCheek} />
          </View>
        </View>

        {/* left arm */}
        <View style={[styles.buddyArm, styles.buddyArmLeft]}>
          <View style={styles.buddyGlove} />
        </View>
        {/* right arm */}
        <View style={[styles.buddyArm, styles.buddyArmRight]}>
          <View style={styles.buddyGlove} />
        </View>
      </View>

      {/* name badge below */}
      <View style={styles.buddyNameBadge}>
        <Text style={styles.buddyNameText}>BUDDY</Text>
      </View>
    </View>
  );

  // ─────────────────────────────────────────────────────────────────────────────
  // ILLUSTRATION: Reading Level Icon (plant / sun / rocket / star)
  // Matches the reference's rounded-square icon cards
  // ─────────────────────────────────────────────────────────────────────────────
  const renderLevelIcon = (level: ReadingLevel) => {
    switch (level) {
      /* ── 🌱 Beginner: seedling plant ── */
      case "beginner":
        return (
          <View style={[styles.levelIconCanvas, { backgroundColor: "#D1FAE5" }]}>
            {/* soil mound */}
            <View style={styles.plantSoil} />
            {/* stem */}
            <View style={styles.plantStem} />
            {/* left leaf */}
            <View style={styles.plantLeafLeft} />
            {/* right leaf */}
            <View style={styles.plantLeafRight} />
            {/* tiny sparkle */}
            <Text style={styles.levelIconSpark}>✦</Text>
          </View>
        );

      /* ── ☀️ Elementary: happy smiling sun ── */
      case "elementary":
        return (
          <View style={[styles.levelIconCanvas, { backgroundColor: "#FEF3C7" }]}>
            {/* sun rays — 4 pairs forming 8-ray star */}
            <View style={[styles.sunRay, { transform: [{ rotate: "0deg" }] }]} />
            <View style={[styles.sunRay, { transform: [{ rotate: "45deg" }] }]} />
            <View style={[styles.sunRay, { transform: [{ rotate: "90deg" }] }]} />
            <View style={[styles.sunRay, { transform: [{ rotate: "135deg" }] }]} />
            {/* sun circle face */}
            <View style={styles.sunCircle}>
              <View style={styles.sunEyesRow}>
                <View style={styles.sunEye} />
                <View style={styles.sunEye} />
              </View>
              <View style={styles.sunSmile} />
            </View>
          </View>
        );

      /* ── 🚀 Intermediate: rocket ── */
      case "intermediate":
        return (
          <View style={[styles.levelIconCanvas, { backgroundColor: "#DBEAFE" }]}>
            {/* rocket flame */}
            <View style={styles.rocketFlame} />
            {/* rocket body */}
            <View style={styles.rocketBody}>
              {/* nose cone */}
              <View style={styles.rocketNose} />
              {/* porthole window */}
              <View style={styles.rocketWindow} />
            </View>
            {/* left fin */}
            <View style={styles.rocketFinLeft} />
            {/* right fin */}
            <View style={styles.rocketFinRight} />
            <Text style={styles.levelIconSpark}>✦</Text>
          </View>
        );

      /* ── ⭐ Advanced: glowing star ── */
      case "advanced":
        return (
          <View style={[styles.levelIconCanvas, { backgroundColor: "#EDE9FE" }]}>
            {/* outer glow ring */}
            <View style={styles.starGlow} />
            {/* star text — large emoji star at this scale looks great */}
            <Text style={styles.levelStarText}>⭐</Text>
            <Text style={styles.levelIconSpark}>✦</Text>
          </View>
        );
    }
  };

  // ─────────────────────────────────────────────────────────────────────────────
  // ILLUSTRATION: Strategy Icon (robot / scissors / bubbles / lightbulb / compass)
  // ─────────────────────────────────────────────────────────────────────────────
  const renderStrategyIcon = (value: SimplificationStrategy, accentColor: string, iconBg: string) => {
    switch (value) {
      /* ── 🤖 Combined: friendly robot ── */
      case "combined":
        return (
          <View style={[styles.stratIconCanvas, { backgroundColor: iconBg }]}>
            {/* antenna */}
            <View style={styles.robotAntennaPole} />
            <View style={[styles.robotAntennaLight, { backgroundColor: accentColor }]} />
            {/* robot head */}
            <View style={[styles.robotHead, { borderColor: accentColor }]}>
              <View style={styles.robotEyesRow}>
                <View style={[styles.robotEye, { backgroundColor: accentColor }]} />
                <View style={[styles.robotEye, { backgroundColor: accentColor }]} />
              </View>
              <View style={[styles.robotMouth, { backgroundColor: accentColor }]}>
                <View style={styles.robotGrillLine} />
                <View style={styles.robotGrillLine} />
                <View style={styles.robotGrillLine} />
              </View>
            </View>
          </View>
        );

      /* ── ✂️ Sentence Split: scissors ── */
      case "sentence_split":
        return (
          <View style={[styles.stratIconCanvas, { backgroundColor: iconBg }]}>
            {/* upper blade */}
            <View style={[styles.scissorBlade, styles.scissorBladeTop, { backgroundColor: accentColor }]} />
            {/* lower blade */}
            <View style={[styles.scissorBlade, styles.scissorBladeBot, { backgroundColor: accentColor }]} />
            {/* pivot */}
            <View style={[styles.scissorPivot, { backgroundColor: "#fff", borderColor: accentColor }]} />
            {/* handle rings */}
            <View style={[styles.scissorHandle, styles.scissorHandleTop, { borderColor: accentColor }]} />
            <View style={[styles.scissorHandle, styles.scissorHandleBot, { borderColor: accentColor }]} />
          </View>
        );

      /* ── 💬 Vocabulary Swap: speech bubbles ── */
      case "vocabulary_swap":
        return (
          <View style={[styles.stratIconCanvas, { backgroundColor: iconBg }]}>
            {/* three overlapping speech bubbles */}
            <View style={[styles.speechBubble, styles.speechBubble1, { backgroundColor: "#C4B5FD" }]} />
            <View style={[styles.speechBubble, styles.speechBubble2, { backgroundColor: "#F9A8D4" }]} />
            <View style={[styles.speechBubble, styles.speechBubble3, { backgroundColor: "#6EE7B7" }]} />
            {/* dots inside front bubble */}
            <View style={styles.speechDots}>
              <View style={[styles.speechDot, { backgroundColor: accentColor }]} />
              <View style={[styles.speechDot, { backgroundColor: accentColor }]} />
              <View style={[styles.speechDot, { backgroundColor: accentColor }]} />
            </View>
          </View>
        );

      /* ── 💡 Concept Reduction: lightbulb ── */
      case "concept_reduction":
        return (
          <View style={[styles.stratIconCanvas, { backgroundColor: iconBg }]}>
            {/* glow halo */}
            <View style={[styles.bulbGlow, { backgroundColor: accentColor + "30" }]} />
            {/* bulb glass */}
            <View style={[styles.bulbGlass, { backgroundColor: accentColor }]}>
              {/* filament lines */}
              <View style={styles.bulbFilament} />
            </View>
            {/* bulb base segments */}
            <View style={[styles.bulbBase1, { backgroundColor: accentColor }]} />
            <View style={[styles.bulbBase2, { backgroundColor: accentColor }]} />
            {/* shine rays */}
            <Text style={[styles.bulbRay, { top: 4, right: 6, transform: [{ rotate: "30deg" }] }]}>|</Text>
            <Text style={[styles.bulbRay, { top: 8, right: 2, transform: [{ rotate: "60deg" }] }]}>|</Text>
          </View>
        );

      /* ── 🧭 Full Rewrite: compass ── */
      case "full_rewrite":
        return (
          <View style={[styles.stratIconCanvas, { backgroundColor: iconBg }]}>
            {/* compass outer ring */}
            <View style={[styles.compassRing, { borderColor: accentColor }]}>
              {/* N/S arrow (north red, south white) */}
              <View style={styles.compassArrowWrap}>
                <View style={[styles.compassArrowN, { backgroundColor: accentColor }]} />
                <View style={styles.compassArrowS} />
              </View>
              {/* center pivot */}
              <View style={[styles.compassCenter, { backgroundColor: accentColor }]} />
            </View>
            {/* cardinal labels */}
            <Text style={[styles.compassLabel, { top: 2 }]}>N</Text>
            <Text style={[styles.compassLabel, { bottom: 2 }]}>S</Text>
          </View>
        );
    }
  };

  // ─────────────────────────────────────────────────────────────────────────────
  // ILLUSTRATION: Notepad & Pencil (story input step)
  // ─────────────────────────────────────────────────────────────────────────────
  const renderNotepadPencil = () => (
    <View style={styles.notepadWrap} accessible={false}>
      {/* spiral notepad */}
      <View style={styles.notepad}>
        {/* rings along top */}
        <View style={styles.notepadRingsRow}>
          {[0, 1, 2, 3, 4].map((i) => (
            <View key={i} style={styles.notepadRing} />
          ))}
        </View>
        {/* ruled lines */}
        <View style={styles.notepadLine} />
        <View style={[styles.notepadLine, { width: "80%" }]} />
        <View style={styles.notepadLine} />
        <View style={[styles.notepadLine, { width: "70%" }]} />
        <View style={styles.notepadLine} />
      </View>

      {/* yellow pencil, angled */}
      <View style={styles.pencilWrap}>
        {/* eraser (pink) */}
        <View style={styles.pencilEraser} />
        {/* metal band */}
        <View style={styles.pencilMetal} />
        {/* pencil body (yellow) */}
        <View style={styles.pencilBody} />
        {/* wood tip */}
        <View style={styles.pencilWood} />
        {/* graphite tip */}
        <View style={styles.pencilTip} />
      </View>

      <Text style={styles.notepadSpark}>✨</Text>
    </View>
  );

  // ─────────────────────────────────────────────────────────────────────────────
  // ILLUSTRATION: Trophy / Success (results screen)
  // ─────────────────────────────────────────────────────────────────────────────
  const renderTrophy = () => (
    <View style={styles.trophyWrap}>
      {/* confetti */}
      <Text style={[styles.trophyDeco, { top: 0, left: 4, color: "#EC4899" }]}>🎉</Text>
      <Text style={[styles.trophyDeco, { top: 2, right: 4, color: "#FCD34D" }]}>🌟</Text>
      <Text style={[styles.trophyDeco, { bottom: 20, left: 2, color: "#34D399" }]}>✨</Text>

      {/* cup handles + body */}
      <View style={styles.trophyCupRow}>
        <View style={styles.trophyHandle} />
        <View style={styles.trophyCup}>
          {/* star emblem on cup */}
          <Text style={styles.trophyCupStar}>⭐</Text>
          {/* shine on cup */}
          <View style={styles.trophyCupShine} />
        </View>
        <View style={styles.trophyHandle} />
      </View>

      {/* stem */}
      <View style={styles.trophyStem} />

      {/* base */}
      <View style={styles.trophyBase}>
        <Text style={styles.trophyBaseLabel}>READING HERO</Text>
      </View>
    </View>
  );

  // ─────────────────────────────────────────────────────────────────────────────
  // ICON: Open storybook used by the primary home action.
  // ─────────────────────────────────────────────────────────────────────────────
  const renderOpenBookIcon = () => (
    <View style={styles.startBookIcon}>
      <View style={styles.startBookPages}>
        <View style={styles.startBookPageLeft} />
        <View style={styles.startBookPageRight} />
      </View>
      <View style={styles.startBookSpine} />
    </View>
  );

  const isResultsMode = Boolean(simplifiedResult);

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
          {/* ══════════════════════════════════════════════════════════════════ */}
          {/* APP HEADER                                                         */}
          {/* ══════════════════════════════════════════════════════════════════ */}
          <View style={styles.header}>
            <View style={styles.headerInner}>
              {/* Logo mark */}
              <TouchableOpacity
                style={styles.logoMark}
                onPress={() => setCurrentScreen("home")}
                accessibilityRole="button"
                accessibilityLabel="ReadBuddy Home"
              >
                <View style={styles.logoBookMini}>
                  <View style={styles.logoBookEyeL} />
                  <View style={styles.logoBookEyeR} />
                  <View style={styles.logoBookSmile} />
                </View>
              </TouchableOpacity>

              {/* Brand text */}
              <View style={styles.headerBrand}>
                <Text style={styles.headerTitle}>ReadBuddy</Text>
                <View style={styles.headerKidsBadge}>
                  <Text style={styles.headerKidsBadgeText}>Ages 9–12</Text>
                </View>
              </View>

              <View
                style={styles.readerProfile}
                accessible
                accessibilityLabel={isSessionActive ? "Reader profile ready" : "Reader profile needs setup"}
              >
                <Text style={styles.readerAvatar}>🙂</Text>
                <View
                  style={[
                    styles.readerStatusDot,
                    isSessionActive ? styles.sessionDotActive : styles.sessionDotInactive,
                  ]}
                />
              </View>

              {/* Settings opens the existing session configuration drawer. */}
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
                style={styles.settingsButton}
              >
                <Text style={styles.settingsButtonIcon}>{showSessionConfig ? "×" : "⚙️"}</Text>
              </TouchableOpacity>
            </View>

            {/* Session configuration drawer */}
            {showSessionConfig && (
              <View style={styles.sessionCard}>
                <Text style={styles.sessionCardTitle}>Test Learner Credentials</Text>
                <Text style={styles.sessionCardDesc}>
                  Component 2 requires an authenticated learner context. Tokens remain in memory; refresh session uses secure device storage.
                </Text>
                <Text style={styles.sessionEndpoint}>Current backend: {effectiveEndpoint}</Text>

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

                <View style={styles.sessionBtnRow}>
                  <TouchableOpacity style={styles.sessionSaveBtn} onPress={handleSaveSession} accessibilityRole="button">
                    <Text style={styles.sessionSaveBtnText}>Apply Session</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={styles.sessionClearBtn} onPress={handleClearSessionState} accessibilityRole="button">
                    <Text style={styles.sessionClearBtnText}>Clear</Text>
                  </TouchableOpacity>
                </View>
              </View>
            )}
          </View>

          {/* ══════════════════════════════════════════════════════════════════ */}
          {/* SCREEN A: HOME / WELCOME                                           */}
          {/* ══════════════════════════════════════════════════════════════════ */}
          <View
            style={[
              styles.screen,
              currentScreen === "home" && !isResultsMode
                ? styles.screenVisible
                : styles.screenHidden,
            ]}
          >
            <View style={styles.homeCanvas}>
              <View style={styles.homeCloudOne} />
              <View style={styles.homeCloudTwo} />
              <View style={styles.homeHillBack} />
              <View style={styles.homeHillFront} />
              <View style={styles.homeFlowerOne}>
                <View style={[styles.flowerPetal, styles.flowerPetalTop]} />
                <View style={[styles.flowerPetal, styles.flowerPetalLeft]} />
                <View style={[styles.flowerPetal, styles.flowerPetalRight]} />
                <View style={styles.flowerCenter} />
              </View>
              <View style={styles.homeFlowerTwo}>
                <View style={[styles.flowerPetal, styles.flowerPetalTop]} />
                <View style={[styles.flowerPetal, styles.flowerPetalLeft]} />
                <View style={[styles.flowerPetal, styles.flowerPetalRight]} />
                <View style={styles.flowerCenter} />
              </View>

              {/* Hero welcome card */}
              <View style={styles.heroCard}>
                <View style={styles.heroRight}>
                  <View style={styles.heroBadge}>
                    <Text style={styles.heroBadgeText}>HELLO, READING EXPLORER!</Text>
                  </View>
                  <Text style={styles.heroHeading}>Welcome! Let’s make reading fun together!</Text>
                  <Text style={styles.heroSub}>
                    Pick a story and Buddy will help make every page feel friendlier.
                  </Text>
                </View>
                <View
                  style={styles.heroIllustration}
                  accessible
                  accessibilityLabel="A cheerful child reading a book"
                >
                  <View style={styles.heroIllustrationGlow} />
                  <Image
                    source={require("./assets/home/reading-child.png")}
                    style={styles.heroIllustrationImage}
                    resizeMode="contain"
                    accessibilityIgnoresInvertColors
                  />
                </View>
                <TouchableOpacity
                  style={styles.heroBtn}
                  onPress={() => {
                    setCurrentScreen("guided");
                    setGuidedStep(1);
                  }}
                  accessibilityRole="button"
                  accessibilityLabel="Start My Reading Adventure"
                  accessibilityHint="Opens the reading support choices"
                >
                  {renderOpenBookIcon()}
                  <Text style={styles.heroBtnText}>Start Reading</Text>
                  <Text style={styles.heroBtnArrow}>→</Text>
                </TouchableOpacity>
              </View>

              <View style={styles.homeSectionHeader}>
                <View>
                  <Text style={styles.homeSectionEyebrow}>YOUR READING TOOLS</Text>
                  <Text style={styles.homeSectionTitle}>Choose Your Adventure</Text>
                </View>
                <Text style={styles.homeSectionSpark}>✨</Text>
              </View>

              <View style={styles.featuresCard}>
                <View style={styles.featuresRow}>
                  {[
                    {
                      title: "Pick Your Level",
                      description: "Choose how much reading support feels right.",
                      icon: "🎯",
                      backgroundColor: "#E7F8EF",
                      borderColor: "#89D6AD",
                      iconColor: "#D1FAE5",
                      step: 1 as const,
                    },
                    {
                      title: "Reading Magic",
                      description: "Choose how Buddy makes tricky text friendlier.",
                      icon: "🪄",
                      backgroundColor: "#FFF4D6",
                      borderColor: "#F7C95C",
                      iconColor: "#FEF3C7",
                      step: 3 as const,
                    },
                    {
                      title: "Word Detective",
                      description: "Simplify a story, then explore helpful words.",
                      icon: "🔍",
                      backgroundColor: "#EEE9FF",
                      borderColor: "#B8A5F7",
                      iconColor: "#DDD6FE",
                      step: 2 as const,
                    },
                    {
                      title: "Read at Your Pace",
                      description: "Choose your support and take your time—there’s no timer.",
                      icon: "📖",
                      backgroundColor: "#FFE8E2",
                      borderColor: "#F5A893",
                      iconColor: "#FED7CC",
                      step: 1 as const,
                    },
                  ].map((feature) => (
                    <TouchableOpacity
                      key={feature.title}
                      style={[
                        styles.featureChip,
                        { backgroundColor: feature.backgroundColor, borderColor: feature.borderColor },
                      ]}
                      onPress={() => {
                        setCurrentScreen("guided");
                        setGuidedStep(feature.step);
                      }}
                      accessibilityRole="button"
                      accessibilityLabel={`Open ${feature.title}`}
                      accessibilityHint={feature.description}
                    >
                      <View style={[styles.featureIconBubble, { backgroundColor: feature.iconColor }]}>
                        <Text style={styles.featureChipIcon}>{feature.icon}</Text>
                      </View>
                      <Text style={styles.featureChipLabel}>{feature.title}</Text>
                      <Text style={styles.featureChipArrow}>→</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </View>

              {/* Quick-Try Sample Stories */}
              <View style={styles.sampleCard}>
                <View style={styles.sampleCardHeader}>
                  <View>
                    <Text style={styles.homeSectionEyebrow}>JUMP INTO A STORY</Text>
                    <Text style={styles.sampleCardTitle}>Try a Sample Story</Text>
                  </View>
                  <Text style={styles.sampleCardSub}>Swipe to explore →</Text>
                </View>
                <ScrollView
                  horizontal
                  nestedScrollEnabled
                  showsHorizontalScrollIndicator={false}
                  contentContainerStyle={styles.sampleStoriesGrid}
                >
                  {SAMPLE_STORIES.map((story) => (
                    <TouchableOpacity
                      key={story.id}
                      style={[
                        styles.sampleStoryCard,
                        { backgroundColor: story.backgroundColor, borderColor: story.borderColor },
                      ]}
                      onPress={() => handleSelectSampleStory(story)}
                      accessibilityRole="button"
                      accessibilityLabel={`Load sample story: ${story.title}`}
                      accessibilityHint={`Loads the ${story.tag} passage into the reading workflow`}
                    >
                      <View style={[styles.sampleCover, { backgroundColor: story.borderColor }]}>
                        <View style={styles.sampleCoverCloud} />
                        <View style={[styles.sampleCoverHill, { backgroundColor: story.accentColor }]} />
                        <Image
                          source={story.image}
                          style={styles.sampleArtwork}
                          resizeMode="contain"
                          accessibilityIgnoresInvertColors
                        />
                      </View>
                      <Text style={[styles.sampleTitle, { color: story.accentColor }]}>{story.title}</Text>
                      <View style={[styles.sampleTag, { backgroundColor: story.borderColor }]}>
                        <Text style={[styles.sampleTagText, { color: story.accentColor }]}>{story.tag}</Text>
                      </View>
                    </TouchableOpacity>
                  ))}
                </ScrollView>
              </View>
            </View>
          </View>

          {/* ══════════════════════════════════════════════════════════════════ */}
          {/* GUIDED JOURNEY (Steps 1 → 2 → 3)                                  */}
          {/* ══════════════════════════════════════════════════════════════════ */}
          <View
            style={[
              styles.screen,
              currentScreen === "guided" && !isResultsMode
                ? styles.screenVisible
                : styles.screenHidden,
            ]}
          >
            {/* Step progress bar */}
            <View style={styles.stepperWrap}>
              {[
                { n: 1, icon: "🎯", label: "Level" },
                { n: 2, icon: "📝", label: "Story" },
                { n: 3, icon: "🪄", label: "Magic" },
              ].map(({ n, icon, label }, idx) => (
                <React.Fragment key={n}>
                  <TouchableOpacity
                    style={[styles.stepBtn, guidedStep === n && styles.stepBtnActive]}
                    onPress={() => setGuidedStep(n as 1 | 2 | 3)}
                  >
                    <View
                      style={[
                        styles.stepCircle,
                        guidedStep >= n ? styles.stepCircleDone : styles.stepCircleTodo,
                      ]}
                    >
                      <Text style={styles.stepCircleText}>
                        {guidedStep > n ? "✓" : icon}
                      </Text>
                    </View>
                    <Text style={[styles.stepLabel, guidedStep === n && styles.stepLabelActive]}>
                      {label}
                    </Text>
                  </TouchableOpacity>
                  {idx < 2 && (
                    <View style={[styles.stepConnector, guidedStep > n && styles.stepConnectorDone]} />
                  )}
                </React.Fragment>
              ))}
            </View>
            <View style={styles.stepProgressTrack}>
              <View
                style={[
                  styles.stepProgressFill,
                  { width: guidedStep === 1 ? "33%" : guidedStep === 2 ? "66%" : "100%" },
                ]}
              />
            </View>

            {/* ── STEP 1: CHOOSE READING LEVEL ───────────────────────────────── */}
            <View
              style={[
                styles.stepSection,
                guidedStep === 1 ? styles.stepVisible : styles.stepHidden,
              ]}
            >
              <View style={styles.stepCard}>
                <Text style={styles.stepEyebrow}>STEP 1 OF 3 • READING SUPPORT</Text>
                <Text style={styles.stepTitle}>Choose Your Reading Support</Text>
                <Text style={styles.stepDesc}>
                  Pick the amount of help that feels useful today. These choices change the text,
                  not what you are capable of — and you can change them anytime.
                </Text>

                {/* 2×2 illustrated level icon grid */}
                <View style={styles.levelGrid}>
                  {READING_LEVELS.map((item) => {
                    const isSelected = selectedLevel === item.value;
                    return (
                      <TouchableOpacity
                        key={item.value}
                        style={[
                          styles.levelCard,
                          {
                            backgroundColor: item.backgroundColor,
                            borderColor: isSelected ? item.accentColor : item.borderColor,
                            borderWidth: isSelected ? 2.5 : 1.5,
                          },
                        ]}
                        onPress={() => setSelectedLevel(item.value)}
                        disabled={isLoading}
                        accessibilityRole="radio"
                        accessibilityState={{ selected: isSelected }}
                        accessibilityLabel={`${item.label} level: ${item.description}`}
                      >
                        {/* Illustrated icon */}
                        {renderLevelIcon(item.value)}

                        {/* Text info */}
                        <View style={styles.levelCardInfo}>
                          <View style={styles.levelCardTitleRow}>
                            <Text style={[styles.levelCardName, { color: item.accentColor }]}>
                              {item.label}
                            </Text>
                            {isSelected && (
                              <View style={[styles.levelCheckBadge, { backgroundColor: item.accentColor }]}>
                                <Text style={styles.levelCheckText}>✓</Text>
                              </View>
                            )}
                          </View>
                          <Text style={styles.levelCardBadge}>{item.badge}</Text>
                          <Text style={styles.levelCardDesc}>{item.description}</Text>
                        </View>
                      </TouchableOpacity>
                    );
                  })}
                </View>

                <View style={styles.navRow}>
                  <TouchableOpacity
                    style={styles.navBackText}
                    onPress={() => setCurrentScreen("home")}
                  >
                    <Text style={styles.navBackTextLabel}>← Home</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={styles.navNextBtn}
                    onPress={() => setGuidedStep(2)}
                  >
                    <Text style={styles.navNextBtnText}>Next: Story →</Text>
                  </TouchableOpacity>
                </View>
              </View>
            </View>

            {/* ── STEP 2: ADD A STORY ─────────────────────────────────────────── */}
            <View
              style={[
                styles.stepSection,
                guidedStep === 2 ? styles.stepVisible : styles.stepHidden,
              ]}
            >
              <View style={styles.stepCard}>
                {/* Header with notepad illustration */}
                <View style={styles.storyHeaderRow}>
                  <View style={styles.storyHeaderCopy}>
                    <Text style={styles.stepEyebrow}>STEP 2 OF 3 • YOUR PASSAGE</Text>
                    <Text style={styles.stepTitle}>What shall we read?</Text>
                    <Text style={styles.stepDesc}>
                      Paste homework or pick a sample adventure below!
                    </Text>
                  </View>
                  {renderNotepadPencil()}
                </View>

                {/* Quick sample pills */}
                <ScrollView
                  horizontal
                  showsHorizontalScrollIndicator={false}
                  style={styles.samplePillsScroll}
                  contentContainerStyle={styles.samplePillsContent}
                >
                  {SAMPLE_STORIES.map((s) => (
                    <TouchableOpacity
                      key={s.id}
                      style={[styles.samplePill, { borderColor: s.borderColor, backgroundColor: s.backgroundColor }]}
                      onPress={() => handleSelectSampleStory(s)}
                    >
                      <Text style={[styles.samplePillText, { color: s.accentColor }]}>
                        {s.emoji} {s.title}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </ScrollView>

                {/* Passage input */}
                <View style={styles.inputLabelRow}>
                  <Text style={styles.inputLabel}>Reading Passage</Text>
                  {passage.length > 0 && (
                    <TouchableOpacity
                      onPress={handleClearPassage}
                      accessibilityRole="button"
                      accessibilityLabel="Clear passage text"
                      hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                      disabled={isLoading}
                    >
                      <Text style={styles.inputClearText}>Clear</Text>
                    </TouchableOpacity>
                  )}
                </View>

                <TextInput
                  style={[styles.textInput, validationError ? styles.textInputError : null]}
                  multiline
                  numberOfLines={7}
                  textAlignVertical="top"
                  placeholder="Paste your homework, science text, or favourite story here..."
                  placeholderTextColor="#94A3B8"
                  value={passage}
                  onChangeText={handlePassageChange}
                  editable={!isLoading}
                  accessible
                  accessibilityLabel="Reading passage input"
                  accessibilityHint="Enter the text you want simplified"
                />

                <View style={styles.inputFooterRow}>
                  {validationError ? (
                    <Text style={styles.inputErrorText}>{validationError}</Text>
                  ) : (
                    <Text style={styles.inputHelperText}>Supports up to 50,000 characters</Text>
                  )}
                  <Text style={styles.charCounter}>
                    {passage.length.toLocaleString()} / {MAX_PASSAGE_LENGTH.toLocaleString()}
                  </Text>
                </View>

                <View style={styles.navRow}>
                  <TouchableOpacity style={styles.navBackBtn} onPress={() => setGuidedStep(1)}>
                    <Text style={styles.navBackBtnText}>← Level</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={styles.navNextBtn}
                    onPress={() => {
                      if (!passage.trim()) {
                        setValidationError("Please enter or paste a reading passage first.");
                        return;
                      }
                      setValidationError(null);
                      setGuidedStep(3);
                    }}
                  >
                    <Text style={styles.navNextBtnText}>Next: Magic →</Text>
                  </TouchableOpacity>
                </View>
              </View>
            </View>

            {/* ── STEP 3: CHOOSE STRATEGY & SIMPLIFY ─────────────────────────── */}
            <View
              style={[
                styles.stepSection,
                guidedStep === 3 ? styles.stepVisible : styles.stepHidden,
              ]}
            >
              <View style={styles.stepCard}>
                <Text style={styles.stepEyebrow}>STEP 3 OF 3 • READING MAGIC</Text>
                <Text style={styles.stepTitle}>How should Buddy help?</Text>
                <Text style={styles.stepDesc}>Pick how you would like your text adapted:</Text>

                {/* Strategy illustrated cards */}
                <View style={styles.strategyList}>
                  {STRATEGIES.map((item) => {
                    const isSelected = selectedStrategy === item.value;
                    return (
                      <TouchableOpacity
                        key={item.value}
                        style={[
                          styles.strategyCard,
                          {
                            backgroundColor: item.backgroundColor,
                            borderColor: isSelected ? item.accentColor : item.borderColor,
                            borderWidth: isSelected ? 2.5 : 1.5,
                          },
                        ]}
                        onPress={() => setSelectedStrategy(item.value)}
                        disabled={isLoading}
                        accessibilityRole="radio"
                        accessibilityState={{ selected: isSelected }}
                        accessibilityLabel={`${item.label} strategy: ${item.description}`}
                      >
                        {/* Illustrated icon on the left */}
                        {renderStrategyIcon(item.value, item.accentColor, item.iconBg)}

                        {/* Text on the right */}
                        <View style={styles.strategyCardInfo}>
                          <View style={styles.strategyCardTitleRow}>
                            <Text style={[styles.strategyCardName, { color: item.accentColor }]}>
                              {item.label}
                            </Text>
                            {isSelected && (
                              <View style={[styles.strategyCheck, { backgroundColor: item.accentColor }]}>
                                <Text style={styles.strategyCheckText}>✓</Text>
                              </View>
                            )}
                          </View>
                          <View style={[styles.strategyBadge, { backgroundColor: item.iconBg }]}>
                            <Text style={[styles.strategyBadgeText, { color: item.accentColor }]}>
                              {item.badge}
                            </Text>
                          </View>
                          <Text style={styles.strategyCardDesc}>{item.description}</Text>
                        </View>
                      </TouchableOpacity>
                    );
                  })}
                </View>

                <View style={styles.navRow}>
                  <TouchableOpacity style={styles.navBackBtn} onPress={() => setGuidedStep(2)}>
                    <Text style={styles.navBackBtnText}>← Story</Text>
                  </TouchableOpacity>
                </View>
              </View>

              {/* ── MAKE IT EASIER! primary CTA ── */}
              <View style={styles.ctaSection}>
                <TouchableOpacity
                  style={[styles.ctaBtn, isLoading && styles.ctaBtnDisabled]}
                  onPress={handleSimplifyPress}
                  disabled={isLoading}
                  accessibilityRole="button"
                  accessibilityLabel="Simplify my text"
                  accessibilityHint="Sends reading passage to the FastAPI simplification service"
                >
                  {isLoading ? (
                    <View style={styles.ctaBtnInner}>
                      <ActivityIndicator color="#FFFFFF" size="small" />
                      <Text style={styles.ctaBtnText}>Buddy is working magic...</Text>
                    </View>
                  ) : (
                    <View style={styles.ctaBtnInner}>
                      <Text style={styles.ctaBtnEmoji}>✨</Text>
                      <Text style={styles.ctaBtnText}>Make It Easier!</Text>
                    </View>
                  )}
                </TouchableOpacity>

                {apiError && (
                  <View style={styles.errorBox}>
                    <View style={styles.errorBoxHeader}>
                      <Text style={styles.errorBoxIcon}>⚠️</Text>
                      <Text style={styles.errorBoxTitle}>{apiError.title}</Text>
                      <View style={styles.errorCodeChip}>
                        <Text style={styles.errorCodeText}>{apiError.code}</Text>
                      </View>
                    </View>
                    <Text style={styles.errorBoxMsg}>{apiError.message}</Text>
                    <TouchableOpacity style={styles.errorDismissBtn} onPress={() => setApiError(null)}>
                      <Text style={styles.errorDismissText}>Dismiss</Text>
                    </TouchableOpacity>
                  </View>
                )}
              </View>
            </View>
          </View>

          {/* ══════════════════════════════════════════════════════════════════ */}
          {/* RESULTS SCREEN                                                     */}
          {/* ══════════════════════════════════════════════════════════════════ */}
          {simplifiedResult ? (
            <View style={styles.resultsSection}>
              {/* Celebration hero banner */}
              <View style={styles.celebCard}>
                <View style={styles.celebLeft}>
                  <View style={styles.celebBadge}>
                    <Text style={styles.celebBadgeText}>🏆 QUEST COMPLETE!</Text>
                  </View>
                  <Text style={styles.celebHeading}>Your Easier Story Is Ready!</Text>
                  <Text style={styles.celebSub}>
                    Tap any highlighted word to become a Word Detective!
                  </Text>
                </View>
                {renderTrophy()}
              </View>

              {/* Control bar */}
              <View style={styles.resultCtrlRow}>
                <View style={styles.resultTags}>
                  <View style={styles.resultTagPill}>
                    <Text style={styles.resultTagText}>
                      {simplifiedResult.target_reading_level.toUpperCase()}
                    </Text>
                  </View>
                  <View style={styles.resultTagPillSecondary}>
                    <Text style={styles.resultTagTextSecondary}>
                      {simplifiedResult.strategy_applied}
                    </Text>
                  </View>
                </View>
                <TouchableOpacity
                  style={styles.resetBtn}
                  onPress={resetReadingState}
                  hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                >
                  <Text style={styles.resetBtnText}>Reset</Text>
                </TouchableOpacity>
              </View>

              {submittedSourceText !== null && (
                <View>
                  <View
                    style={styles.resultViewSelector}
                    accessibilityRole="tablist"
                    accessibilityLabel="Choose how to view your reading"
                  >
                    <TouchableOpacity
                      style={[
                        styles.resultViewOption,
                        resultTextView === "simplified" && styles.resultViewOptionSelected,
                      ]}
                      onPress={() => setResultTextView("simplified")}
                      accessibilityRole="tab"
                      accessibilityLabel="Simplified Only"
                      accessibilityState={{ selected: resultTextView === "simplified" }}
                    >
                      <Text
                        style={[
                          styles.resultViewOptionText,
                          resultTextView === "simplified" &&
                            styles.resultViewOptionTextSelected,
                        ]}
                      >
                        📖 Simplified Only
                      </Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={[
                        styles.resultViewOption,
                        resultTextView === "compare" && styles.resultViewOptionSelected,
                      ]}
                      onPress={() => setResultTextView("compare")}
                      accessibilityRole="tab"
                      accessibilityLabel="Compare"
                      accessibilityState={{ selected: resultTextView === "compare" }}
                    >
                      <Text
                        style={[
                          styles.resultViewOptionText,
                          resultTextView === "compare" && styles.resultViewOptionTextSelected,
                        ]}
                      >
                        🔎 Compare
                      </Text>
                    </TouchableOpacity>
                  </View>

                  <View style={styles.highlightControls}>
                    <View style={styles.highlightSwitchRow}>
                      <View style={styles.highlightSwitchCopy}>
                        <Text style={styles.highlightSwitchTitle}>✨ Show highlights</Text>
                        <Text style={styles.highlightSwitchHint}>
                          See what changed and find helpful words
                        </Text>
                      </View>
                      <TouchableOpacity
                        style={[
                          styles.highlightSwitch,
                          showHighlights && styles.highlightSwitchEnabled,
                        ]}
                        onPress={() => setShowHighlights((current) => !current)}
                        accessibilityRole="switch"
                        accessibilityLabel="Show highlights"
                        accessibilityState={{ checked: showHighlights }}
                      >
                        <View
                          style={[
                            styles.highlightSwitchThumb,
                            showHighlights && styles.highlightSwitchThumbEnabled,
                          ]}
                        />
                      </TouchableOpacity>
                    </View>
                    {showHighlights && (
                      <View style={styles.highlightLegend}>
                        <View style={styles.highlightLegendItem}>
                          <View style={[styles.highlightLegendSwatch, styles.changedLegendSwatch]} />
                          <Text style={styles.highlightLegendText}>Changed text</Text>
                        </View>
                        <View style={styles.highlightLegendItem}>
                          <View
                            style={[styles.highlightLegendSwatch, styles.vocabularyLegendSwatch]}
                          />
                          <Text style={styles.highlightLegendText}>Helpful vocabulary</Text>
                        </View>
                      </View>
                    )}
                  </View>
                </View>
              )}

              {/* Reading text and vocabulary card */}
              <View style={styles.textResultCard}>
                {resultTextView === "compare" && submittedSourceText !== null ? (
                  <View style={styles.comparisonStack}>
                    <View style={[styles.comparisonCard, styles.originalTextCard]}>
                      <View style={styles.comparisonCardHeader}>
                        <Text style={styles.originalTextCardTitle}>📝 ORIGINAL TEXT</Text>
                      </View>
                      {renderHighlightedPassage(
                        submittedSourceText,
                        passageHighlights.original,
                        "comparison",
                        "Original passage"
                      )}
                    </View>
                    <View style={[styles.comparisonCard, styles.simplifiedTextCard]}>
                      <View style={styles.comparisonCardHeader}>
                        <Text style={styles.simplifiedTextCardTitle}>
                          📖 SIMPLIFIED TEXT
                        </Text>
                      </View>
                      {renderHighlightedPassage(
                        simplifiedResult.simplified_text,
                        passageHighlights.simplified,
                        "comparison",
                        "Simplified passage"
                      )}
                    </View>
                  </View>
                ) : (
                  <View>
                    <View style={styles.textResultHeader}>
                      <Text style={styles.textResultHeaderTitle}>📖 YOUR ADAPTED STORY</Text>
                      <Text style={styles.textResultHeaderHint}>Comfortable Reading Font</Text>
                    </View>
                    {renderHighlightedPassage(
                      simplifiedResult.simplified_text,
                      passageHighlights.simplified,
                      "simplified",
                      "Simplified passage"
                    )}
                  </View>
                )}

                {/* ── VOCABULARY DISCOVERY ── */}
                <View style={styles.vocabSection}>
                  {simplifiedResult.vocabulary_items.length > 0 ? (
                    <View>
                      <View style={styles.vocabHeader}>
                        <View style={styles.vocabHeaderRow}>
                          <Text style={styles.vocabHeaderTitle}>
                            🔍 Word Detective Helpers ({simplifiedResult.vocabulary_items.length})
                          </Text>
                          <View style={styles.vocabReviewCountPill}>
                            <Text style={styles.vocabReviewCountText}>
                              {`${reviewedVocabularyItems.size} of ${simplifiedResult.vocabulary_items.length} reviewed this time`}
                            </Text>
                          </View>
                        </View>
                        <Text style={styles.vocabHeaderHint}>
                          Read each card, explore more if you want, then tap Got it!
                        </Text>
                      </View>

                      {simplifiedResult.vocabulary_items.map((item, idx) => {
                        const itemKey = `${idx}:${item.term}`;
                        const isExpanded = explainItemKey === itemKey;
                        const isReviewed = reviewedVocabularyItems.has(itemKey);
                        const palette = VOCABULARY_PALETTES[idx % VOCABULARY_PALETTES.length];
                        return (
                          <View key={itemKey} style={styles.vocabItemWrap}>
                            <View
                              style={[
                                styles.vocabCard,
                                isExpanded && styles.vocabCardActive,
                                isReviewed && styles.vocabCardReviewed,
                                {
                                  backgroundColor: palette.backgroundColor,
                                  borderColor: isReviewed
                                    ? "#10B981"
                                    : isExpanded
                                      ? palette.accentColor
                                      : palette.borderColor,
                                },
                              ]}
                            >
                              <TouchableOpacity
                                style={styles.vocabLearnArea}
                                onPress={() => handleExplainWord(item, itemKey)}
                                accessibilityRole="button"
                                accessibilityLabel={`Word: ${item.term}. Tap to explain.`}
                                accessibilityState={{ expanded: isExpanded }}
                              >
                                <View style={styles.vocabCardRow}>
                                  <View style={styles.vocabTermRow}>
                                    <Text style={styles.vocabDetBadge}>📚</Text>
                                    <Text style={[styles.vocabTerm, { color: palette.accentColor }]}>
                                      {item.term}
                                    </Text>
                                    {isReviewed && (
                                      <View style={styles.vocabReviewedBadge}>
                                        <Text style={styles.vocabReviewedBadgeText}>✓ REVIEWED</Text>
                                      </View>
                                    )}
                                  </View>
                                  <View style={styles.vocabCardRight}>
                                    {isExplainLoading && isExpanded ? (
                                      <ActivityIndicator size="small" color={palette.accentColor} />
                                    ) : (
                                      <View
                                        style={[
                                          styles.vocabActionPill,
                                          { backgroundColor: palette.tagBg },
                                        ]}
                                      >
                                        <Text
                                          style={[
                                            styles.vocabActionText,
                                            { color: palette.accentColor },
                                          ]}
                                        >
                                          {isExpanded ? "Close ▲" : "Explain ▼"}
                                        </Text>
                                      </View>
                                    )}
                                  </View>
                                </View>

                                <View style={styles.vocabDefinitionBox}>
                                  <Text style={styles.vocabDefinitionLabel}>WHAT IT MEANS</Text>
                                  <Text style={styles.vocabDef}>{item.simplified_definition}</Text>
                                </View>

                                {item.example_sentence &&
                                  item.example_sentence.trim().length > 0 && (
                                    <View style={styles.vocabExample}>
                                      <Text style={styles.vocabExampleLabel}>
                                        TRY IT IN A SENTENCE
                                      </Text>
                                      <Text style={styles.vocabExampleText}>
                                        "{item.example_sentence.trim()}"
                                      </Text>
                                    </View>
                                  )}

                                {item.synonyms &&
                                  item.synonyms.filter((s) => Boolean(s && s.trim())).length > 0 && (
                                    <View style={styles.synonymsRow}>
                                      {item.synonyms
                                        .filter((s) => Boolean(s && s.trim()))
                                        .map((syn, si) => (
                                          <View key={si} style={styles.synonymChip}>
                                            <Text style={styles.synonymChipText}>{syn}</Text>
                                          </View>
                                        ))}
                                    </View>
                                  )}
                              </TouchableOpacity>

                              <View style={styles.vocabReviewFooter}>
                                <Text style={styles.vocabReviewHint}>
                                  {isReviewed
                                    ? "Nice work — reviewed for this reading!"
                                    : "Finished reading this card?"}
                                </Text>
                                <TouchableOpacity
                                  style={[
                                    styles.vocabGotItButton,
                                    isReviewed && styles.vocabGotItButtonReviewed,
                                  ]}
                                  onPress={() => handleAcknowledgeVocabulary(itemKey)}
                                  disabled={isReviewed}
                                  accessibilityRole="button"
                                  accessibilityLabel={`Got it: ${item.term}, card ${idx + 1}`}
                                  accessibilityState={{ selected: isReviewed, disabled: isReviewed }}
                                >
                                  <Text
                                    style={[
                                      styles.vocabGotItText,
                                      isReviewed && styles.vocabGotItTextReviewed,
                                    ]}
                                  >
                                    {isReviewed ? "✓ Got it!" : "Got it!"}
                                  </Text>
                                </TouchableOpacity>
                              </View>
                            </View>

                            {/* Explain drawer */}
                            {isExpanded && (
                              <View style={styles.explainPanel}>
                                {isExplainLoading ? (
                                  <View style={styles.explainLoadingRow}>
                                    <View style={styles.explainLoadingInner}>
                                      <ActivityIndicator size="small" color="#7C3AED" />
                                      <Text style={styles.explainLoadingText}>
                                        Asking ReadBuddy AI for a helpful explanation...
                                      </Text>
                                    </View>
                                    <TouchableOpacity
                                      onPress={handleCloseExplain}
                                      hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                                    >
                                      <Text style={styles.explainCloseText}>Cancel</Text>
                                    </TouchableOpacity>
                                  </View>
                                ) : explainError ? (
                                  <View style={styles.explainErrorWrap}>
                                    <View style={styles.explainPanelRow}>
                                      <Text style={styles.explainErrorTitle}>
                                        ⚠️ {explainError.title}
                                      </Text>
                                      <TouchableOpacity
                                        onPress={handleCloseExplain}
                                        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                                      >
                                        <Text style={styles.explainCloseText}>Close</Text>
                                      </TouchableOpacity>
                                    </View>
                                    <Text style={styles.explainErrorMsg}>{explainError.message}</Text>
                                    <TouchableOpacity
                                      style={styles.explainRetryBtn}
                                      onPress={() => handleExplainWord(item, itemKey)}
                                      accessibilityRole="button"
                                      accessibilityLabel={`Retry explanation for ${item.term}`}
                                    >
                                      <Text style={styles.explainRetryText}>Try explanation again</Text>
                                    </TouchableOpacity>
                                  </View>
                                ) : explainResult &&
                                  explainResult.item.term.trim().toLowerCase() ===
                                    item.term.trim().toLowerCase() ? (
                                  <View>
                                    <View style={styles.explainPanelRow}>
                                      <Text style={styles.explainResultTerm}>
                                        💡 {explainResult.item.term}
                                      </Text>
                                      <TouchableOpacity
                                        onPress={handleCloseExplain}
                                        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                                      >
                                        <Text style={styles.explainCloseText}>Close</Text>
                                      </TouchableOpacity>
                                    </View>
                                    <View style={styles.explainFriendlyBox}>
                                      <Text style={styles.explainFriendlyLabel}>IN SIMPLE WORDS</Text>
                                      <Text style={styles.explainFriendlyText}>
                                        {explainResult.item.simplified_definition}
                                      </Text>
                                    </View>
                                    {explainResult.item.example_sentence && (
                                      <View style={styles.explainExampleBox}>
                                        <Text style={styles.explainExampleLabel}>EXAMPLE SENTENCE</Text>
                                        <Text style={styles.explainExampleText}>
                                          "{explainResult.item.example_sentence}"
                                        </Text>
                                      </View>
                                    )}
                                    {explainResult.item.synonyms &&
                                      explainResult.item.synonyms.filter((s) => Boolean(s && s.trim()))
                                        .length > 0 && (
                                        <View>
                                          <Text style={styles.explainSynLabel}>SIMILAR WORDS</Text>
                                          <View style={styles.synonymsRow}>
                                            {explainResult.item.synonyms
                                              .filter((s) => Boolean(s && s.trim()))
                                              .map((syn, si) => (
                                                <View key={si} style={styles.synonymChip}>
                                                  <Text style={styles.synonymChipText}>{syn}</Text>
                                                </View>
                                              ))}
                                          </View>
                                        </View>
                                      )}
                                  </View>
                                ) : null}
                              </View>
                            )}
                          </View>
                        );
                      })}
                    </View>
                  ) : (
                    <View style={styles.vocabEmptyBox}>
                      <Text style={styles.vocabEmptyIcon}>✅</Text>
                      <Text style={styles.vocabEmptyText}>
                        No tricky words this time! This passage is already super easy to read, so no extra vocabulary help is needed.
                      </Text>
                    </View>
                  )}
                </View>
              </View>

              {/* ── PDF LEARNING PACK ── */}
              <View style={styles.learningPackSection}>
                <View style={styles.learningPackHeaderRow}>
                  <View style={styles.learningPackIcon}>
                    <Text style={styles.learningPackIconText}>PDF</Text>
                  </View>
                  <View style={styles.learningPackHeaderCopy}>
                    <Text style={styles.learningPackTitle}>PDF Learning Pack</Text>
                    <Text style={styles.learningPackSubtitle}>
                      Keep this reading adventure to revisit, share, or print.
                    </Text>
                  </View>
                </View>

                <View style={styles.learningPackActions}>
                  <TouchableOpacity
                    style={[
                      styles.learningPackButton,
                      styles.learningPackPreviewButton,
                      isLearningPackBusy && styles.learningPackButtonDisabled,
                    ]}
                    onPress={() => handleLearningPackAction("print")}
                    disabled={isLearningPackBusy}
                    accessibilityRole="button"
                    accessibilityLabel="Preview and print learning pack"
                    accessibilityState={{ disabled: isLearningPackBusy, busy: isLearningPackBusy }}
                  >
                    <Text style={styles.learningPackPreviewButtonText}>Preview &amp; Print</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[
                      styles.learningPackButton,
                      styles.learningPackShareButton,
                      isLearningPackBusy && styles.learningPackButtonDisabled,
                    ]}
                    onPress={() => handleLearningPackAction("share")}
                    disabled={isLearningPackBusy}
                    accessibilityRole="button"
                    accessibilityLabel="Share or save PDF learning pack"
                    accessibilityState={{ disabled: isLearningPackBusy, busy: isLearningPackBusy }}
                  >
                    <Text style={styles.learningPackShareButtonText}>Share or Save PDF</Text>
                  </TouchableOpacity>
                </View>

                {isLearningPackBusy && (
                  <View style={styles.learningPackStatus} accessibilityRole="progressbar">
                    <ActivityIndicator size="small" color="#6D28D9" />
                    <Text style={styles.learningPackStatusText}>
                      Preparing your learning pack...
                    </Text>
                  </View>
                )}
                {learningPackError && (
                  <View style={styles.learningPackError} accessibilityRole="alert">
                    <Text style={styles.learningPackErrorText}>{learningPackError}</Text>
                    <Text style={styles.learningPackRetryText}>Choose an option above to try again.</Text>
                  </View>
                )}
              </View>

              {/* ── FEEDBACK SECTION ── */}
              <View style={styles.feedbackSection}>
                <View style={styles.feedbackHeader}>
                  <Text style={styles.feedbackTitle}>How did this reading feel?</Text>
                  <Text style={styles.feedbackSub}>
                    Share how it felt, then choose the support you want for your next passage.
                  </Text>
                </View>

                {feedbackResult ? (
                  <View>
                    <View style={styles.feedbackThanksBanner}>
                      <Text style={styles.feedbackThanksIcon}>🎉</Text>
                      <Text style={styles.feedbackThanksText}>
                        Thanks! Your answer was saved for this reading.
                      </Text>
                    </View>

                    {feedbackLevelSuggestion && (
                      <View
                        style={styles.levelSuggestionCard}
                        accessibilityLabel="Reading support suggestion"
                      >
                        <Text style={styles.levelSuggestionEyebrow}>FOR YOUR NEXT PASSAGE</Text>
                        <Text style={styles.levelSuggestionTitle}>
                          {feedbackLevelSuggestion.title}
                        </Text>
                        <Text style={styles.levelSuggestionMessage}>
                          {feedbackLevelSuggestion.message}
                        </Text>

                        {feedbackLevelSuggestion.kind === "adjust" &&
                          feedbackLevelSuggestion.suggestedLevel &&
                          (acceptedSuggestedLevel === feedbackLevelSuggestion.suggestedLevel ? (
                            <View
                              style={styles.levelSuggestionAccepted}
                              accessible
                              accessibilityLabel={`${READING_LEVEL_LABELS[feedbackLevelSuggestion.suggestedLevel]} is ready for your next passage`}
                            >
                              <Text style={styles.levelSuggestionAcceptedText}>
                                ✓ {READING_LEVEL_LABELS[feedbackLevelSuggestion.suggestedLevel]} is
                                ready for your next passage
                              </Text>
                            </View>
                          ) : (
                            <TouchableOpacity
                              style={styles.levelSuggestionButton}
                              onPress={() =>
                                handleAcceptSuggestedLevel(
                                  feedbackLevelSuggestion.suggestedLevel as ReadingLevel
                                )
                              }
                              accessibilityRole="button"
                              accessibilityLabel={`Use ${READING_LEVEL_LABELS[feedbackLevelSuggestion.suggestedLevel]} next time`}
                            >
                              <Text style={styles.levelSuggestionButtonText}>
                                Use {READING_LEVEL_LABELS[feedbackLevelSuggestion.suggestedLevel]} Next
                                Time
                              </Text>
                            </TouchableOpacity>
                          ))}

                        <Text style={styles.levelSuggestionNote}>
                          This is a choice for next time. It does not change this result or measure
                          your reading ability.
                        </Text>
                      </View>
                    )}
                  </View>
                ) : (
                  <View style={styles.feedbackGrid}>
                    {FEEDBACK_OPTIONS.map((opt) => {
                      const isChosen = selectedFeedback === opt.value;
                      const isDisabled =
                        Boolean(feedbackResult) ||
                        (isFeedbackLoading && !isChosen) ||
                        Boolean(selectedFeedback && selectedFeedback !== opt.value);
                      return (
                        <TouchableOpacity
                          key={opt.value}
                          style={[
                            styles.feedbackCard,
                            {
                              backgroundColor: isChosen ? opt.backgroundColor : "#FFFFFF",
                              borderColor: isChosen ? opt.accentColor : "#E2E8F0",
                              borderWidth: isChosen ? 2.5 : 1.5,
                              opacity: isDisabled ? 0.45 : 1,
                            },
                          ]}
                          onPress={() => handleSubmitFeedback(opt.value)}
                          disabled={
                            isDisabled ||
                            Boolean(feedbackResult) ||
                            Boolean(activeFeedbackAbortRef.current)
                          }
                          accessibilityRole="button"
                          accessibilityLabel={`Feedback: ${opt.label}`}
                          accessibilityState={{ selected: isChosen }}
                        >
                          {isFeedbackLoading && isChosen ? (
                            <ActivityIndicator size="small" color={opt.accentColor} />
                          ) : (
                            <Text style={styles.feedbackEmoji}>{opt.emoji}</Text>
                          )}
                          <Text style={[styles.feedbackLabel, isChosen && { color: opt.accentColor }]}>
                            {opt.label}
                          </Text>
                          <Text style={styles.feedbackSubLabel}>{opt.subLabel}</Text>
                        </TouchableOpacity>
                      );
                    })}
                  </View>
                )}

                {feedbackError && (
                  <View style={styles.feedbackErrorBox}>
                    <Text style={styles.feedbackErrorText}>
                      ⚠️ {feedbackError.title}: {feedbackError.message}
                    </Text>
                  </View>
                )}
              </View>

              {/* New reading button */}
              <TouchableOpacity
                style={styles.newReadingBtn}
                onPress={resetReadingState}
                accessibilityRole="button"
                accessibilityLabel="Read another story"
              >
                <Text style={styles.newReadingBtnText}>📚 Read Another Story</Text>
              </TouchableOpacity>
            </View>
          ) : null}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  // ── layout ──────────────────────────────────────────────────────────────────
  safeArea: {
    flex: 1,
    backgroundColor: "#F5F3FF",
  },
  flex: { flex: 1 },
  scrollContainer: {
    paddingBottom: 40,
  },
  screen: { width: "100%" },
  screenVisible: { display: "flex" },
  screenHidden: { display: "none" },
  stepSection: { width: "100%" },
  stepVisible: { display: "flex" },
  stepHidden: { display: "none" },

  // ── header ──────────────────────────────────────────────────────────────────
  header: {
    backgroundColor: "#FFFDF5",
    borderBottomWidth: 1,
    borderBottomColor: "#D8D1F2",
    paddingHorizontal: 16,
    paddingTop: 9,
    paddingBottom: 9,
  },
  headerInner: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  logoMark: {
    width: 44,
    height: 44,
    borderRadius: 12,
    backgroundColor: "#7C3AED",
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#7C3AED",
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.35,
    shadowRadius: 6,
    elevation: 5,
  },
  logoBookMini: {
    width: 26,
    height: 26,
    borderRadius: 6,
    backgroundColor: "#6D28D9",
    alignItems: "center",
    justifyContent: "center",
    position: "relative",
  },
  logoBookEyeL: {
    position: "absolute",
    top: 7,
    left: 5,
    width: 6,
    height: 7,
    borderRadius: 3,
    backgroundColor: "#FFFFFF",
  },
  logoBookEyeR: {
    position: "absolute",
    top: 7,
    right: 5,
    width: 6,
    height: 7,
    borderRadius: 3,
    backgroundColor: "#FFFFFF",
  },
  logoBookSmile: {
    position: "absolute",
    bottom: 5,
    width: 12,
    height: 5,
    borderBottomLeftRadius: 6,
    borderBottomRightRadius: 6,
    backgroundColor: "#FFFFFF",
  },
  headerBrand: {
    flex: 1,
    alignItems: "flex-start",
    gap: 2,
  },
  headerTitle: {
    fontSize: 22,
    fontWeight: "900",
    color: "#7C3AED",
    letterSpacing: -0.5,
  },
  headerKidsBadge: {
    backgroundColor: "#FFF0C2",
    borderRadius: 20,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderWidth: 1,
    borderColor: "#F3C861",
  },
  headerKidsBadgeText: {
    fontSize: 10,
    fontWeight: "700",
    color: "#8A4B08",
    letterSpacing: 0.3,
  },
  readerProfile: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: "#DDF7EC",
    borderWidth: 2,
    borderColor: "#72C9A6",
    alignItems: "center",
    justifyContent: "center",
    position: "relative",
  },
  readerAvatar: {
    fontSize: 24,
  },
  readerStatusDot: {
    position: "absolute",
    right: -1,
    bottom: 1,
    width: 10,
    height: 10,
    borderRadius: 5,
    borderWidth: 2,
    borderColor: "#FFFDF5",
  },
  settingsButton: {
    width: 44,
    height: 44,
    borderRadius: 14,
    backgroundColor: "#F0ECFF",
    borderWidth: 1.5,
    borderColor: "#C8BAF4",
    alignItems: "center",
    justifyContent: "center",
  },
  settingsButtonIcon: {
    fontSize: 20,
    color: "#5B3BB5",
    fontWeight: "800",
  },
  sessionPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    backgroundColor: "#F1F5F9",
    borderRadius: 20,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  sessionPillActive: {
    backgroundColor: "#ECFDF5",
    borderColor: "#A7F3D0",
  },
  sessionDot: {
    width: 7,
    height: 7,
    borderRadius: 3.5,
  },
  sessionDotActive: { backgroundColor: "#10B981" },
  sessionDotInactive: { backgroundColor: "#94A3B8" },
  sessionPillText: {
    fontSize: 12,
    fontWeight: "700",
    color: "#475569",
  },

  // ── session card ─────────────────────────────────────────────────────────────
  sessionCard: {
    marginTop: 10,
    backgroundColor: "#FAFAFA",
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  sessionCardTitle: {
    fontSize: 14,
    fontWeight: "800",
    color: "#1E293B",
    marginBottom: 4,
  },
  sessionCardDesc: {
    fontSize: 12,
    color: "#64748B",
    marginBottom: 8,
    lineHeight: 17,
  },
  sessionEndpoint: {
    fontSize: 11,
    color: "#7C3AED",
    fontWeight: "600",
    marginBottom: 10,
    fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace",
  },
  sessionFieldLabel: {
    fontSize: 12,
    fontWeight: "700",
    color: "#374151",
    marginTop: 8,
    marginBottom: 4,
  },
  sessionInput: {
    borderWidth: 1.5,
    borderColor: "#DDD6FE",
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 8,
    fontSize: 13,
    color: "#1E293B",
    backgroundColor: "#FFFFFF",
  },
  sessionBtnRow: {
    flexDirection: "row",
    gap: 10,
    marginTop: 14,
  },
  sessionSaveBtn: {
    flex: 1,
    backgroundColor: "#7C3AED",
    borderRadius: 12,
    paddingVertical: 11,
    alignItems: "center",
    borderBottomWidth: 3,
    borderBottomColor: "#5B21B6",
  },
  sessionSaveBtnText: {
    color: "#FFFFFF",
    fontWeight: "800",
    fontSize: 14,
  },
  sessionClearBtn: {
    flex: 1,
    backgroundColor: "#FEF2F2",
    borderRadius: 12,
    paddingVertical: 11,
    alignItems: "center",
    borderWidth: 1.5,
    borderColor: "#FECDD3",
    borderBottomWidth: 3,
    borderBottomColor: "#FECDD3",
  },
  sessionClearBtnText: {
    color: "#E11D48",
    fontWeight: "800",
    fontSize: 14,
  },

  // ── BUDDY MASCOT ─────────────────────────────────────────────────────────────
  buddyWrap: {
    width: 140,
    height: 170,
    alignItems: "center",
    justifyContent: "center",
    position: "relative",
  },
  buddyFloatStar: {
    position: "absolute",
    fontWeight: "900",
  },
  // mood decorations
  buddyMoodHat: {
    position: "absolute",
    top: -8,
    zIndex: 10,
    alignItems: "center",
  },
  buddyHatBrim: {
    width: 48,
    height: 7,
    backgroundColor: "#EC4899",
    borderRadius: 3,
  },
  buddyHatBody: {
    width: 30,
    height: 30,
    backgroundColor: "#EC4899",
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    marginBottom: 0,
    borderBottomWidth: 0,
  },
  buddyHatStar: {
    position: "absolute",
    top: 4,
    right: 4,
    fontSize: 10,
    color: "#FCD34D",
  },
  buddyThinkCloud: {
    position: "absolute",
    top: -2,
    right: 6,
    fontSize: 22,
  },

  // open book page wings
  buddyPage: {
    position: "absolute",
    width: 52,
    height: 90,
    backgroundColor: "#F9FAFB",
    borderRadius: 6,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.08,
    shadowRadius: 3,
    elevation: 2,
  },
  buddyPageLeft: {
    left: 4,
    transform: [{ rotate: "-8deg" }],
  },
  buddyPageRight: {
    right: 4,
    transform: [{ rotate: "8deg" }],
  },

  // main purple cover
  buddyCover: {
    width: 100,
    height: 118,
    backgroundColor: "#7C3AED",
    borderRadius: 16,
    alignItems: "center",
    shadowColor: "#7C3AED",
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.4,
    shadowRadius: 10,
    elevation: 8,
    position: "relative",
  },
  buddyBookmark: {
    position: "absolute",
    top: -16,
    width: 10,
    height: 28,
    backgroundColor: "#F59E0B",
    borderTopLeftRadius: 3,
    borderTopRightRadius: 3,
    borderBottomLeftRadius: 5,
    borderBottomRightRadius: 5,
    alignItems: "center",
    justifyContent: "flex-start",
    paddingTop: 3,
  },
  buddyBookmarkStar: {
    fontSize: 6,
    color: "#92400E",
    fontWeight: "900",
  },
  // face area (white oval on cover)
  buddyFace: {
    marginTop: 22,
    width: 78,
    height: 62,
    backgroundColor: "#FFFFFF",
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
    elevation: 1,
  },
  // reading glasses
  buddyGlassesRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 3,
    gap: 2,
  },
  buddyGlassRim: {
    width: 16,
    height: 10,
    borderRadius: 5,
    borderWidth: 2,
    borderColor: "#7C3AED",
    backgroundColor: "transparent",
  },
  buddyGlassBridge: {
    width: 6,
    height: 2,
    backgroundColor: "#7C3AED",
    borderRadius: 1,
  },
  // eyes
  buddyEyesRow: {
    flexDirection: "row",
    gap: 12,
    marginBottom: 6,
  },
  buddyEyeWhite: {
    width: 20,
    height: 22,
    borderRadius: 10,
    backgroundColor: "#1E1B4B",
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
  },
  buddyEyePupil: {
    width: 12,
    height: 14,
    borderRadius: 7,
    backgroundColor: "#0F172A",
    position: "relative",
    alignItems: "flex-end",
    justifyContent: "flex-start",
    paddingTop: 2,
    paddingRight: 2,
  },
  buddyEyeShine: {
    width: 4,
    height: 4,
    borderRadius: 2,
    backgroundColor: "#FFFFFF",
  },
  // cheeks + smile
  buddyExprRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  buddyCheek: {
    width: 12,
    height: 8,
    borderRadius: 6,
    backgroundColor: "#FECDD3",
    opacity: 0.85,
  },
  buddySmileWrap: {
    overflow: "hidden",
    height: 13,
    width: 26,
  },
  buddySmile: {
    width: 26,
    height: 16,
    borderBottomLeftRadius: 13,
    borderBottomRightRadius: 13,
    backgroundColor: "#1E1B4B",
    alignItems: "center",
    justifyContent: "flex-start",
    paddingTop: 3,
  },
  buddyTeeth: {
    width: 20,
    height: 6,
    backgroundColor: "#FFFFFF",
    borderRadius: 3,
  },
  // arms / hands
  buddyArm: {
    position: "absolute",
    width: 14,
    height: 26,
    backgroundColor: "#6D28D9",
    borderRadius: 7,
    bottom: 24,
    alignItems: "center",
    justifyContent: "flex-end",
    paddingBottom: 0,
  },
  buddyArmLeft: {
    left: -12,
    transform: [{ rotate: "-20deg" }],
  },
  buddyArmRight: {
    right: -12,
    transform: [{ rotate: "20deg" }],
  },
  buddyGlove: {
    width: 14,
    height: 14,
    borderRadius: 7,
    backgroundColor: "#FFFFFF",
    marginBottom: -4,
  },
  // name badge
  buddyNameBadge: {
    marginTop: 8,
    backgroundColor: "#EDE9FE",
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 4,
    borderWidth: 1.5,
    borderColor: "#DDD6FE",
  },
  buddyNameText: {
    fontSize: 11,
    fontWeight: "900",
    color: "#7C3AED",
    letterSpacing: 1.5,
  },

  // ── LEVEL ICON ILLUSTRATIONS ──────────────────────────────────────────────
  levelIconCanvas: {
    width: "100%",
    height: 80,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
    position: "relative",
    overflow: "hidden",
    marginBottom: 10,
  },
  levelIconSpark: {
    position: "absolute",
    top: 6,
    right: 8,
    fontSize: 12,
    color: "#FCD34D",
    fontWeight: "900",
  },
  // plant (beginner)
  plantSoil: {
    position: "absolute",
    bottom: 10,
    width: 36,
    height: 10,
    backgroundColor: "#92400E",
    borderRadius: 5,
    opacity: 0.35,
  },
  plantStem: {
    position: "absolute",
    bottom: 18,
    width: 5,
    height: 32,
    backgroundColor: "#065F46",
    borderRadius: 3,
  },
  plantLeafLeft: {
    position: "absolute",
    bottom: 32,
    left: "28%",
    width: 24,
    height: 14,
    backgroundColor: "#10B981",
    borderTopLeftRadius: 12,
    borderTopRightRadius: 2,
    borderBottomRightRadius: 12,
    borderBottomLeftRadius: 2,
    transform: [{ rotate: "-35deg" }],
  },
  plantLeafRight: {
    position: "absolute",
    bottom: 36,
    right: "28%",
    width: 24,
    height: 14,
    backgroundColor: "#34D399",
    borderTopLeftRadius: 2,
    borderTopRightRadius: 12,
    borderBottomRightRadius: 2,
    borderBottomLeftRadius: 12,
    transform: [{ rotate: "35deg" }],
  },
  // sun (elementary)
  sunRay: {
    position: "absolute",
    width: 6,
    height: 54,
    backgroundColor: "#FDE68A",
    borderRadius: 3,
  },
  sunCircle: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: "#F59E0B",
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#F59E0B",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.4,
    shadowRadius: 4,
    elevation: 4,
  },
  sunEyesRow: {
    flexDirection: "row",
    gap: 8,
    marginBottom: 5,
  },
  sunEye: {
    width: 6,
    height: 7,
    borderRadius: 3,
    backgroundColor: "#92400E",
  },
  sunSmile: {
    width: 18,
    height: 9,
    borderBottomLeftRadius: 9,
    borderBottomRightRadius: 9,
    backgroundColor: "#92400E",
  },
  // rocket (intermediate)
  rocketFlame: {
    position: "absolute",
    bottom: 6,
    width: 18,
    height: 14,
    backgroundColor: "#F97316",
    borderBottomLeftRadius: 9,
    borderBottomRightRadius: 9,
    borderTopLeftRadius: 3,
    borderTopRightRadius: 3,
  },
  rocketBody: {
    width: 26,
    height: 50,
    backgroundColor: "#EFF6FF",
    borderRadius: 13,
    alignItems: "center",
    borderWidth: 2,
    borderColor: "#BFDBFE",
    position: "relative",
    overflow: "visible",
    shadowColor: "#2563EB",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 4,
    elevation: 3,
  },
  rocketNose: {
    width: 26,
    height: 18,
    backgroundColor: "#3B82F6",
    borderTopLeftRadius: 13,
    borderTopRightRadius: 13,
    marginTop: -2,
  },
  rocketWindow: {
    marginTop: 6,
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: "#BFDBFE",
    borderWidth: 2,
    borderColor: "#3B82F6",
  },
  rocketFinLeft: {
    position: "absolute",
    bottom: 16,
    left: "22%",
    width: 10,
    height: 18,
    backgroundColor: "#2563EB",
    borderBottomLeftRadius: 8,
    transform: [{ skewX: "-15deg" }],
  },
  rocketFinRight: {
    position: "absolute",
    bottom: 16,
    right: "22%",
    width: 10,
    height: 18,
    backgroundColor: "#2563EB",
    borderBottomRightRadius: 8,
    transform: [{ skewX: "15deg" }],
  },
  // star (advanced)
  starGlow: {
    position: "absolute",
    width: 50,
    height: 50,
    borderRadius: 25,
    backgroundColor: "#DDD6FE",
    opacity: 0.6,
  },
  levelStarText: {
    fontSize: 38,
    lineHeight: 42,
  },

  // ── STRATEGY ICON ILLUSTRATIONS ──────────────────────────────────────────
  stratIconCanvas: {
    width: 60,
    height: 60,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
    position: "relative",
    flexShrink: 0,
  },
  // robot (combined)
  robotAntennaPole: {
    position: "absolute",
    top: 2,
    width: 3,
    height: 10,
    backgroundColor: "#9CA3AF",
    borderRadius: 2,
  },
  robotAntennaLight: {
    position: "absolute",
    top: 0,
    width: 7,
    height: 7,
    borderRadius: 3.5,
  },
  robotHead: {
    marginTop: 10,
    width: 38,
    height: 30,
    backgroundColor: "#E0F2FE",
    borderRadius: 8,
    borderWidth: 2,
    alignItems: "center",
    justifyContent: "center",
    gap: 5,
  },
  robotEyesRow: {
    flexDirection: "row",
    gap: 6,
  },
  robotEye: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  robotMouth: {
    width: 26,
    height: 7,
    borderRadius: 4,
    alignItems: "center",
    justifyContent: "space-evenly",
    flexDirection: "row",
    paddingHorizontal: 2,
  },
  robotGrillLine: {
    width: 2,
    height: 5,
    backgroundColor: "#FFFFFF",
    borderRadius: 1,
    opacity: 0.7,
  },
  // scissors (sentence_split)
  scissorBlade: {
    position: "absolute",
    width: 36,
    height: 8,
    borderRadius: 4,
  },
  scissorBladeTop: {
    top: 14,
    transform: [{ rotate: "-25deg" }],
  },
  scissorBladeBot: {
    bottom: 14,
    transform: [{ rotate: "25deg" }],
  },
  scissorPivot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    borderWidth: 2,
    position: "absolute",
  },
  scissorHandle: {
    position: "absolute",
    width: 16,
    height: 16,
    borderRadius: 8,
    borderWidth: 2.5,
    backgroundColor: "transparent",
  },
  scissorHandleTop: {
    top: 2,
    right: 4,
  },
  scissorHandleBot: {
    bottom: 2,
    left: 4,
  },
  // speech bubbles (vocabulary_swap)
  speechBubble: {
    position: "absolute",
    borderRadius: 12,
  },
  speechBubble1: {
    width: 34,
    height: 24,
    top: 8,
    left: 6,
  },
  speechBubble2: {
    width: 28,
    height: 20,
    top: 14,
    right: 4,
  },
  speechBubble3: {
    width: 24,
    height: 18,
    bottom: 6,
    left: 14,
  },
  speechDots: {
    position: "absolute",
    top: 14,
    left: 13,
    flexDirection: "row",
    gap: 3,
  },
  speechDot: {
    width: 4,
    height: 4,
    borderRadius: 2,
  },
  // lightbulb (concept_reduction)
  bulbGlow: {
    position: "absolute",
    width: 44,
    height: 44,
    borderRadius: 22,
  },
  bulbGlass: {
    width: 30,
    height: 30,
    borderRadius: 15,
    alignItems: "center",
    justifyContent: "center",
    marginTop: -6,
  },
  bulbFilament: {
    width: 14,
    height: 8,
    borderBottomWidth: 2,
    borderBottomColor: "rgba(255,255,255,0.6)",
    borderLeftWidth: 2,
    borderRightWidth: 2,
    borderLeftColor: "rgba(255,255,255,0.6)",
    borderRightColor: "rgba(255,255,255,0.6)",
  },
  bulbBase1: {
    width: 20,
    height: 6,
    borderRadius: 2,
    marginTop: 2,
  },
  bulbBase2: {
    width: 14,
    height: 5,
    borderRadius: 2,
    marginTop: 2,
    opacity: 0.7,
  },
  bulbRay: {
    position: "absolute",
    fontSize: 11,
    fontWeight: "900",
    color: "#FCD34D",
  },
  // compass (full_rewrite)
  compassRing: {
    width: 40,
    height: 40,
    borderRadius: 20,
    borderWidth: 3,
    backgroundColor: "transparent",
    alignItems: "center",
    justifyContent: "center",
    position: "relative",
  },
  compassArrowWrap: {
    width: 6,
    height: 28,
    alignItems: "center",
    justifyContent: "center",
  },
  compassArrowN: {
    width: 6,
    height: 14,
    borderTopLeftRadius: 3,
    borderTopRightRadius: 3,
  },
  compassArrowS: {
    width: 6,
    height: 14,
    backgroundColor: "#FFFFFF",
    borderBottomLeftRadius: 3,
    borderBottomRightRadius: 3,
    borderWidth: 1,
    borderColor: "#D1D5DB",
  },
  compassCenter: {
    position: "absolute",
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  compassLabel: {
    position: "absolute",
    fontSize: 8,
    fontWeight: "900",
    color: "#6B7280",
    left: "50%",
  },

  // ── NOTEPAD & PENCIL ────────────────────────────────────────────────────────
  notepadWrap: {
    width: 90,
    height: 90,
    position: "relative",
    flexShrink: 0,
  },
  notepad: {
    position: "absolute",
    top: 8,
    left: 0,
    width: 62,
    height: 72,
    backgroundColor: "#FFFFFF",
    borderRadius: 8,
    borderWidth: 1.5,
    borderColor: "#DDD6FE",
    paddingHorizontal: 8,
    paddingTop: 14,
    gap: 6,
    shadowColor: "#7C3AED",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  notepadRingsRow: {
    position: "absolute",
    top: 4,
    left: 0,
    right: 0,
    flexDirection: "row",
    justifyContent: "space-around",
    paddingHorizontal: 6,
  },
  notepadRing: {
    width: 7,
    height: 9,
    borderRadius: 4,
    backgroundColor: "#C4B5FD",
    borderWidth: 1.5,
    borderColor: "#7C3AED",
  },
  notepadLine: {
    width: "100%",
    height: 2,
    backgroundColor: "#EDE9FE",
    borderRadius: 1,
  },
  pencilWrap: {
    position: "absolute",
    top: 0,
    right: 0,
    width: 16,
    height: 78,
    transform: [{ rotate: "15deg" }],
    alignItems: "center",
  },
  pencilEraser: {
    width: 14,
    height: 12,
    backgroundColor: "#FDA4AF",
    borderTopLeftRadius: 4,
    borderTopRightRadius: 4,
  },
  pencilMetal: {
    width: 14,
    height: 6,
    backgroundColor: "#D1D5DB",
  },
  pencilBody: {
    width: 14,
    height: 44,
    backgroundColor: "#FCD34D",
  },
  pencilWood: {
    width: 14,
    height: 8,
    backgroundColor: "#FEF3C7",
    borderBottomLeftRadius: 3,
    borderBottomRightRadius: 3,
  },
  pencilTip: {
    width: 4,
    height: 6,
    backgroundColor: "#374151",
    borderBottomLeftRadius: 2,
    borderBottomRightRadius: 2,
  },
  notepadSpark: {
    position: "absolute",
    top: 0,
    right: 18,
    fontSize: 14,
  },

  // ── TROPHY ──────────────────────────────────────────────────────────────────
  trophyWrap: {
    width: 90,
    height: 110,
    alignItems: "center",
    position: "relative",
  },
  trophyDeco: {
    position: "absolute",
    fontSize: 16,
  },
  trophyCupRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    marginTop: 18,
  },
  trophyHandle: {
    width: 10,
    height: 24,
    borderWidth: 3,
    borderColor: "#D97706",
    borderRadius: 12,
    backgroundColor: "transparent",
    marginTop: 8,
  },
  trophyCup: {
    width: 46,
    height: 44,
    backgroundColor: "#F59E0B",
    borderTopLeftRadius: 8,
    borderTopRightRadius: 8,
    borderBottomLeftRadius: 22,
    borderBottomRightRadius: 22,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#D97706",
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.4,
    shadowRadius: 5,
    elevation: 5,
    position: "relative",
  },
  trophyCupStar: {
    fontSize: 20,
  },
  trophyCupShine: {
    position: "absolute",
    top: 6,
    left: 8,
    width: 8,
    height: 18,
    backgroundColor: "rgba(255,255,255,0.4)",
    borderRadius: 4,
    transform: [{ rotate: "-15deg" }],
  },
  trophyStem: {
    width: 10,
    height: 14,
    backgroundColor: "#D97706",
    borderRadius: 2,
  },
  trophyBase: {
    width: 56,
    height: 12,
    backgroundColor: "#92400E",
    borderRadius: 6,
    alignItems: "center",
    justifyContent: "center",
  },
  trophyBaseLabel: {
    fontSize: 7,
    fontWeight: "900",
    color: "#FCD34D",
    letterSpacing: 0.8,
  },

  // ── START BUTTON BOOK ICON ────────────────────────────────────────────────
  startBookIcon: {
    width: 31,
    height: 25,
    position: "relative",
    justifyContent: "center",
  },
  startBookPages: {
    flexDirection: "row",
    alignItems: "center",
  },
  startBookPageLeft: {
    width: 15,
    height: 20,
    backgroundColor: "#FFFFFF",
    borderTopLeftRadius: 5,
    borderBottomLeftRadius: 5,
    transform: [{ rotate: "-7deg" }],
  },
  startBookPageRight: {
    width: 15,
    height: 20,
    backgroundColor: "#FFF7ED",
    borderTopRightRadius: 5,
    borderBottomRightRadius: 5,
    transform: [{ rotate: "7deg" }],
  },
  startBookSpine: {
    position: "absolute",
    left: 14,
    bottom: 2,
    width: 3,
    height: 19,
    borderRadius: 2,
    backgroundColor: "#FFD3B8",
  },

  // ── HOME SCREEN ──────────────────────────────────────────────────────────────
  homeCanvas: {
    paddingTop: 14,
    paddingBottom: 30,
    backgroundColor: "#7CCCF1",
    overflow: "hidden",
    position: "relative",
  },
  homeCloudOne: {
    position: "absolute",
    top: 24,
    left: -24,
    width: 105,
    height: 42,
    borderRadius: 30,
    backgroundColor: "rgba(255,255,255,0.52)",
  },
  homeCloudTwo: {
    position: "absolute",
    top: 205,
    right: -32,
    width: 124,
    height: 48,
    borderRadius: 30,
    backgroundColor: "rgba(255,255,255,0.44)",
  },
  homeHillBack: {
    position: "absolute",
    top: 270,
    left: -80,
    width: 270,
    height: 160,
    borderRadius: 140,
    backgroundColor: "#6BCB8E",
    opacity: 0.62,
  },
  homeHillFront: {
    position: "absolute",
    top: 310,
    right: -95,
    width: 300,
    height: 175,
    borderRadius: 150,
    backgroundColor: "#38A96B",
    opacity: 0.48,
  },
  homeFlowerOne: {
    position: "absolute",
    top: 390,
    left: 14,
    width: 30,
    height: 30,
  },
  homeFlowerTwo: {
    position: "absolute",
    top: 455,
    right: 17,
    width: 30,
    height: 30,
    transform: [{ scale: 0.82 }],
  },
  flowerPetal: {
    position: "absolute",
    width: 13,
    height: 13,
    borderRadius: 7,
    backgroundColor: "#FFF4A8",
  },
  flowerPetalTop: { top: 0, left: 8 },
  flowerPetalLeft: { top: 11, left: 1 },
  flowerPetalRight: { top: 11, right: 1 },
  flowerCenter: {
    position: "absolute",
    top: 10,
    left: 10,
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: "#F59E0B",
  },
  heroCard: {
    flexDirection: "row",
    flexWrap: "wrap",
    alignItems: "center",
    marginHorizontal: 16,
    backgroundColor: "#FFF9E9",
    borderRadius: 28,
    padding: 17,
    shadowColor: "#2D5A48",
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.16,
    shadowRadius: 14,
    elevation: 7,
    borderWidth: 2,
    borderColor: "#F2E4BD",
    gap: 10,
  },
  heroRight: {
    flex: 1,
    minWidth: 158,
    gap: 6,
  },
  heroIllustration: {
    width: 130,
    height: 145,
    alignItems: "center",
    justifyContent: "center",
    position: "relative",
  },
  heroIllustrationGlow: {
    position: "absolute",
    width: 124,
    height: 124,
    borderRadius: 62,
    backgroundColor: "#FFF0B4",
  },
  heroIllustrationImage: {
    width: 146,
    height: 146,
  },
  heroBadge: {
    alignSelf: "flex-start",
    backgroundColor: "#E9E3FF",
    borderRadius: 20,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderWidth: 1,
    borderColor: "#C5B7F3",
  },
  heroBadgeText: {
    fontSize: 11,
    fontWeight: "800",
    color: "#7C3AED",
    letterSpacing: 0.5,
  },
  heroHeading: {
    fontSize: 20,
    fontWeight: "900",
    color: "#2F235A",
    lineHeight: 25,
  },
  heroSub: {
    fontSize: 13,
    color: "#5D5870",
    lineHeight: 20,
  },
  heroBtn: {
    width: "100%",
    minHeight: 54,
    flexDirection: "row",
    justifyContent: "center",
    gap: 10,
    backgroundColor: "#F47C35",
    borderRadius: 18,
    paddingVertical: 14,
    paddingHorizontal: 18,
    alignItems: "center",
    borderBottomWidth: 4,
    borderBottomColor: "#C65318",
    shadowColor: "#B94B14",
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.35,
    shadowRadius: 6,
    elevation: 5,
  },
  heroBtnText: {
    color: "#FFFFFF",
    fontWeight: "900",
    fontSize: 18,
  },
  heroBtnArrow: {
    color: "#FFFFFF",
    fontSize: 22,
    fontWeight: "900",
  },
  homeSectionHeader: {
    marginHorizontal: 18,
    marginTop: 17,
    marginBottom: 8,
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between",
  },
  homeSectionEyebrow: {
    fontSize: 10,
    fontWeight: "900",
    color: "#493586",
    letterSpacing: 1.2,
    marginBottom: 3,
  },
  homeSectionTitle: {
    fontSize: 19,
    fontWeight: "900",
    color: "#2F235A",
  },
  homeSectionSpark: {
    fontSize: 24,
  },

  // feature chips
  featuresCard: {
    marginHorizontal: 16,
    backgroundColor: "#FFFDF5",
    borderRadius: 22,
    padding: 10,
    borderWidth: 2,
    borderColor: "#E8DDBD",
    shadowColor: "#315A48",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 3,
  },
  featuresRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  featureChip: {
    flexGrow: 1,
    flexBasis: "46%",
    minWidth: 128,
    minHeight: 92,
    borderRadius: 17,
    padding: 10,
    paddingRight: 32,
    alignItems: "flex-start",
    justifyContent: "center",
    gap: 5,
    borderWidth: 2,
    position: "relative",
  },
  featureIconBubble: {
    width: 36,
    height: 36,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
  },
  featureChipIcon: {
    fontSize: 20,
  },
  featureChipLabel: {
    fontSize: 13,
    fontWeight: "900",
    color: "#30264F",
    lineHeight: 16,
  },
  featureChipArrow: {
    position: "absolute",
    right: 10,
    bottom: 9,
    color: "#5B3BB5",
    fontWeight: "900",
    fontSize: 18,
  },

  // sample stories card
  sampleCard: {
    marginHorizontal: 16,
    marginTop: 14,
    backgroundColor: "#FFFDF5",
    borderRadius: 24,
    paddingVertical: 16,
    borderWidth: 2,
    borderColor: "#E8DDBD",
    shadowColor: "#315A48",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 3,
  },
  sampleCardHeader: {
    marginBottom: 13,
    paddingHorizontal: 16,
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between",
    gap: 10,
  },
  sampleCardTitle: {
    fontSize: 20,
    fontWeight: "900",
    color: "#2F235A",
  },
  sampleCardSub: {
    fontSize: 11,
    color: "#6D6182",
    fontWeight: "700",
    paddingBottom: 2,
  },
  sampleStoriesGrid: {
    paddingHorizontal: 16,
    paddingBottom: 3,
    gap: 10,
  },
  sampleStoryCard: {
    width: 150,
    minHeight: 190,
    borderRadius: 19,
    padding: 10,
    alignItems: "flex-start",
    gap: 7,
    borderWidth: 2,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 2,
  },
  sampleCover: {
    width: "100%",
    height: 100,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
    position: "relative",
  },
  sampleCoverCloud: {
    position: "absolute",
    width: 60,
    height: 22,
    top: 12,
    right: -8,
    borderRadius: 14,
    backgroundColor: "rgba(255,255,255,0.65)",
  },
  sampleCoverHill: {
    position: "absolute",
    width: 135,
    height: 70,
    borderRadius: 70,
    bottom: -45,
    opacity: 0.58,
  },
  sampleArtwork: {
    width: 118,
    height: 108,
    zIndex: 3,
  },
  sampleTitle: {
    fontSize: 13,
    fontWeight: "900",
    lineHeight: 17,
  },
  sampleTag: {
    borderRadius: 10,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  sampleTagText: {
    fontSize: 9,
    fontWeight: "700",
    letterSpacing: 0.3,
  },

  // ── STEPPER ───────────────────────────────────────────────────────────────
  stepperWrap: {
    flexDirection: "row",
    alignItems: "center",
    marginHorizontal: 16,
    marginTop: 16,
    backgroundColor: "#FFFFFF",
    borderRadius: 18,
    padding: 12,
    borderWidth: 1.5,
    borderColor: "#EDE9FE",
  },
  stepBtn: {
    flex: 1,
    alignItems: "center",
    gap: 4,
  },
  stepBtnActive: {},
  stepCircle: {
    width: 38,
    height: 38,
    borderRadius: 19,
    alignItems: "center",
    justifyContent: "center",
  },
  stepCircleDone: {
    backgroundColor: "#7C3AED",
    shadowColor: "#7C3AED",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.35,
    shadowRadius: 4,
    elevation: 4,
  },
  stepCircleTodo: {
    backgroundColor: "#EDE9FE",
  },
  stepCircleText: {
    fontSize: 16,
  },
  stepLabel: {
    fontSize: 11,
    fontWeight: "700",
    color: "#9CA3AF",
  },
  stepLabelActive: {
    color: "#7C3AED",
    fontWeight: "900",
  },
  stepConnector: {
    width: 24,
    height: 3,
    backgroundColor: "#EDE9FE",
    borderRadius: 2,
  },
  stepConnectorDone: {
    backgroundColor: "#7C3AED",
  },
  stepProgressTrack: {
    marginHorizontal: 16,
    marginTop: 6,
    height: 5,
    backgroundColor: "#EDE9FE",
    borderRadius: 3,
    overflow: "hidden",
  },
  stepProgressFill: {
    height: "100%",
    backgroundColor: "#7C3AED",
    borderRadius: 3,
  },

  // ── STEP CARDS ───────────────────────────────────────────────────────────
  stepCard: {
    marginHorizontal: 16,
    marginTop: 14,
    backgroundColor: "#FFFFFF",
    borderRadius: 24,
    padding: 18,
    borderWidth: 1.5,
    borderColor: "#EDE9FE",
    shadowColor: "#7C3AED",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 12,
    elevation: 5,
  },
  stepEyebrow: {
    fontSize: 10,
    fontWeight: "800",
    color: "#7C3AED",
    letterSpacing: 1,
    marginBottom: 4,
  },
  stepTitle: {
    fontSize: 22,
    fontWeight: "900",
    color: "#1E1B4B",
    marginBottom: 6,
    lineHeight: 28,
  },
  stepDesc: {
    fontSize: 13,
    color: "#64748B",
    lineHeight: 18,
    marginBottom: 14,
  },

  // ── LEVEL GRID ────────────────────────────────────────────────────────────
  levelGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10,
    marginBottom: 16,
  },
  levelCard: {
    width: "47%",
    borderRadius: 20,
    overflow: "hidden",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 6,
    elevation: 3,
    padding: 10,
  },
  levelCardInfo: {
    gap: 3,
  },
  levelCardTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  levelCardName: {
    fontSize: 15,
    fontWeight: "900",
  },
  levelCheckBadge: {
    width: 20,
    height: 20,
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
  },
  levelCheckText: {
    color: "#FFFFFF",
    fontSize: 11,
    fontWeight: "900",
  },
  levelCardBadge: {
    fontSize: 10,
    fontWeight: "700",
    color: "#9CA3AF",
    letterSpacing: 0.3,
  },
  levelCardDesc: {
    fontSize: 11,
    color: "#374151",
    lineHeight: 15,
  },

  // ── STORY INPUT STEP ──────────────────────────────────────────────────────
  storyHeaderRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 8,
    marginBottom: 4,
  },
  storyHeaderCopy: {
    flex: 1,
  },
  samplePillsScroll: {
    marginBottom: 12,
  },
  samplePillsContent: {
    gap: 8,
    paddingRight: 4,
  },
  samplePill: {
    borderRadius: 20,
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderWidth: 1.5,
  },
  samplePillText: {
    fontSize: 12,
    fontWeight: "700",
  },
  inputLabelRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 6,
  },
  inputLabel: {
    fontSize: 13,
    fontWeight: "800",
    color: "#374151",
  },
  inputClearText: {
    fontSize: 13,
    fontWeight: "700",
    color: "#E11D48",
  },
  textInput: {
    borderWidth: 2,
    borderColor: "#DDD6FE",
    borderRadius: 16,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 15,
    color: "#1E293B",
    backgroundColor: "#FAFAFA",
    minHeight: 140,
    lineHeight: 22,
  },
  textInputError: {
    borderColor: "#F87171",
    backgroundColor: "#FFF5F5",
  },
  inputFooterRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: 6,
  },
  inputErrorText: {
    fontSize: 12,
    fontWeight: "600",
    color: "#E11D48",
    flex: 1,
  },
  inputHelperText: {
    fontSize: 12,
    color: "#94A3B8",
    flex: 1,
  },
  charCounter: {
    fontSize: 12,
    color: "#94A3B8",
    fontWeight: "600",
  },

  // ── STRATEGY LIST ─────────────────────────────────────────────────────────
  strategyList: {
    gap: 10,
    marginBottom: 14,
  },
  strategyCard: {
    borderRadius: 18,
    padding: 12,
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 2,
  },
  strategyCardInfo: {
    flex: 1,
    gap: 4,
  },
  strategyCardTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  strategyCardName: {
    fontSize: 14,
    fontWeight: "900",
  },
  strategyCheck: {
    width: 20,
    height: 20,
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
  },
  strategyCheckText: {
    color: "#FFFFFF",
    fontSize: 11,
    fontWeight: "900",
  },
  strategyBadge: {
    alignSelf: "flex-start",
    borderRadius: 20,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  strategyBadgeText: {
    fontSize: 10,
    fontWeight: "800",
    letterSpacing: 0.3,
  },
  strategyCardDesc: {
    fontSize: 12,
    color: "#374151",
    lineHeight: 16,
  },

  // ── CTA BUTTON ────────────────────────────────────────────────────────────
  ctaSection: {
    marginHorizontal: 16,
    marginTop: 12,
  },
  ctaBtn: {
    backgroundColor: "#7C3AED",
    borderRadius: 20,
    paddingVertical: 18,
    paddingHorizontal: 24,
    alignItems: "center",
    borderBottomWidth: 5,
    borderBottomColor: "#5B21B6",
    shadowColor: "#7C3AED",
    shadowOffset: { width: 0, height: 5 },
    shadowOpacity: 0.45,
    shadowRadius: 12,
    elevation: 10,
  },
  ctaBtnDisabled: {
    backgroundColor: "#A78BFA",
    borderBottomColor: "#8B5CF6",
    shadowOpacity: 0.2,
    elevation: 3,
  },
  ctaBtnInner: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  ctaBtnEmoji: {
    fontSize: 22,
  },
  ctaBtnText: {
    color: "#FFFFFF",
    fontWeight: "900",
    fontSize: 18,
    letterSpacing: 0.3,
  },

  // ── NAV ROW ──────────────────────────────────────────────────────────────
  navRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: 4,
  },
  navBackText: {
    padding: 8,
  },
  navBackTextLabel: {
    fontSize: 14,
    fontWeight: "700",
    color: "#7C3AED",
  },
  navBackBtn: {
    backgroundColor: "#F5F3FF",
    borderRadius: 12,
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderWidth: 1.5,
    borderColor: "#DDD6FE",
    borderBottomWidth: 3,
    borderBottomColor: "#DDD6FE",
  },
  navBackBtnText: {
    fontSize: 14,
    fontWeight: "700",
    color: "#7C3AED",
  },
  navNextBtn: {
    backgroundColor: "#7C3AED",
    borderRadius: 12,
    paddingVertical: 10,
    paddingHorizontal: 18,
    borderBottomWidth: 3,
    borderBottomColor: "#5B21B6",
    shadowColor: "#7C3AED",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.3,
    shadowRadius: 4,
    elevation: 4,
  },
  navNextBtnText: {
    color: "#FFFFFF",
    fontWeight: "800",
    fontSize: 14,
  },

  // ── ERROR BOX ─────────────────────────────────────────────────────────────
  errorBox: {
    marginTop: 14,
    backgroundColor: "#FFF1F2",
    borderRadius: 16,
    padding: 14,
    borderWidth: 1.5,
    borderColor: "#FECDD3",
  },
  errorBoxHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginBottom: 6,
    flexWrap: "wrap",
  },
  errorBoxIcon: {
    fontSize: 16,
  },
  errorBoxTitle: {
    fontSize: 14,
    fontWeight: "800",
    color: "#E11D48",
    flex: 1,
  },
  errorCodeChip: {
    backgroundColor: "#FECDD3",
    borderRadius: 20,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  errorCodeText: {
    fontSize: 10,
    fontWeight: "700",
    color: "#E11D48",
  },
  errorBoxMsg: {
    fontSize: 13,
    color: "#374151",
    lineHeight: 18,
    marginBottom: 8,
  },
  errorDismissBtn: {
    alignSelf: "flex-end",
    paddingVertical: 6,
    paddingHorizontal: 14,
    backgroundColor: "#FECDD3",
    borderRadius: 10,
  },
  errorDismissText: {
    fontSize: 13,
    fontWeight: "700",
    color: "#E11D48",
  },

  // ── RESULTS SCREEN ────────────────────────────────────────────────────────
  resultsSection: {
    marginTop: 4,
  },
  celebCard: {
    flexDirection: "row",
    alignItems: "center",
    marginHorizontal: 16,
    marginTop: 16,
    backgroundColor: "#FFFFFF",
    borderRadius: 24,
    padding: 18,
    gap: 12,
    borderWidth: 1.5,
    borderColor: "#FDE68A",
    shadowColor: "#D97706",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 12,
    elevation: 6,
  },
  celebLeft: {
    flex: 1,
    gap: 6,
  },
  celebBadge: {
    alignSelf: "flex-start",
    backgroundColor: "#FEF3C7",
    borderRadius: 20,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderWidth: 1,
    borderColor: "#FDE68A",
  },
  celebBadgeText: {
    fontSize: 11,
    fontWeight: "800",
    color: "#D97706",
  },
  celebHeading: {
    fontSize: 18,
    fontWeight: "900",
    color: "#1E1B4B",
    lineHeight: 24,
  },
  celebSub: {
    fontSize: 12,
    color: "#64748B",
    lineHeight: 17,
  },
  resultCtrlRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginHorizontal: 16,
    marginTop: 12,
  },
  resultTags: {
    flexDirection: "row",
    gap: 8,
    flex: 1,
  },
  resultTagPill: {
    backgroundColor: "#EDE9FE",
    borderRadius: 20,
    paddingHorizontal: 12,
    paddingVertical: 5,
  },
  resultTagText: {
    fontSize: 11,
    fontWeight: "800",
    color: "#7C3AED",
  },
  resultTagPillSecondary: {
    backgroundColor: "#E0F2FE",
    borderRadius: 20,
    paddingHorizontal: 12,
    paddingVertical: 5,
  },
  resultTagTextSecondary: {
    fontSize: 11,
    fontWeight: "700",
    color: "#0EA5E9",
  },
  resetBtn: {
    backgroundColor: "#FEF2F2",
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderWidth: 1.5,
    borderColor: "#FECDD3",
  },
  resetBtnText: {
    fontSize: 13,
    fontWeight: "700",
    color: "#E11D48",
  },

  // result view selector and reading cards
  resultViewSelector: {
    flexDirection: "row",
    marginHorizontal: 16,
    marginTop: 12,
    padding: 4,
    backgroundColor: "#EDE9FE",
    borderRadius: 18,
    gap: 4,
  },
  resultViewOption: {
    flex: 1,
    minHeight: 48,
    paddingHorizontal: 10,
    paddingVertical: 12,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
  },
  resultViewOptionSelected: {
    backgroundColor: "#FFFFFF",
    shadowColor: "#7C3AED",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.12,
    shadowRadius: 5,
    elevation: 2,
  },
  resultViewOptionText: {
    fontSize: 14,
    fontWeight: "800",
    color: "#64748B",
    textAlign: "center",
  },
  resultViewOptionTextSelected: {
    color: "#6D28D9",
  },
  highlightControls: {
    marginHorizontal: 16,
    marginTop: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  highlightSwitchRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
  },
  highlightSwitchCopy: {
    flex: 1,
  },
  highlightSwitchTitle: {
    fontSize: 14,
    fontWeight: "900",
    color: "#1E293B",
  },
  highlightSwitchHint: {
    marginTop: 2,
    fontSize: 11,
    lineHeight: 16,
    color: "#64748B",
  },
  highlightSwitch: {
    width: 52,
    height: 30,
    padding: 3,
    borderRadius: 16,
    backgroundColor: "#CBD5E1",
    justifyContent: "center",
  },
  highlightSwitchEnabled: {
    backgroundColor: "#14B8A6",
  },
  highlightSwitchThumb: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: "#FFFFFF",
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.18,
    shadowRadius: 2,
    elevation: 2,
  },
  highlightSwitchThumbEnabled: {
    alignSelf: "flex-end",
  },
  highlightLegend: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
    marginTop: 10,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: "#F1F5F9",
  },
  highlightLegendItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  highlightLegendSwatch: {
    width: 18,
    height: 12,
    borderRadius: 4,
  },
  changedLegendSwatch: {
    backgroundColor: "#FDE68A",
  },
  vocabularyLegendSwatch: {
    backgroundColor: "#BFDBFE",
  },
  highlightLegendText: {
    fontSize: 11,
    fontWeight: "700",
    color: "#475569",
  },
  textResultCard: {
    marginHorizontal: 16,
    marginTop: 12,
    backgroundColor: "#FFFFFF",
    borderRadius: 24,
    padding: 18,
    borderWidth: 1.5,
    borderColor: "#EDE9FE",
    shadowColor: "#7C3AED",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.08,
    shadowRadius: 12,
    elevation: 4,
  },
  textResultHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 12,
    paddingBottom: 10,
    borderBottomWidth: 1,
    borderBottomColor: "#EDE9FE",
  },
  textResultHeaderTitle: {
    fontSize: 12,
    fontWeight: "800",
    color: "#7C3AED",
    letterSpacing: 0.5,
  },
  textResultHeaderHint: {
    fontSize: 11,
    color: "#94A3B8",
  },
  simplifiedText: {
    fontSize: 16,
    color: "#1E293B",
    lineHeight: 26,
    fontWeight: "500",
    marginBottom: 16,
  },
  comparisonStack: {
    gap: 12,
    marginBottom: 16,
  },
  comparisonCard: {
    borderRadius: 18,
    padding: 16,
    borderWidth: 1.5,
  },
  originalTextCard: {
    backgroundColor: "#FFFBEB",
    borderColor: "#FDE68A",
  },
  simplifiedTextCard: {
    backgroundColor: "#F5F3FF",
    borderColor: "#C4B5FD",
  },
  comparisonCardHeader: {
    paddingBottom: 9,
    marginBottom: 10,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(100, 116, 139, 0.18)",
  },
  originalTextCardTitle: {
    fontSize: 12,
    fontWeight: "900",
    color: "#B45309",
    letterSpacing: 0.5,
  },
  simplifiedTextCardTitle: {
    fontSize: 12,
    fontWeight: "900",
    color: "#7C3AED",
    letterSpacing: 0.5,
  },
  comparisonText: {
    fontSize: 16,
    color: "#1E293B",
    lineHeight: 26,
    fontWeight: "500",
  },
  changedHighlight: {
    backgroundColor: "#FDE68A",
    color: "#78350F",
  },
  vocabularyHighlight: {
    backgroundColor: "#BFDBFE",
    color: "#1E40AF",
    fontWeight: "700",
  },

  // vocabulary section
  vocabSection: {
    borderTopWidth: 1,
    borderTopColor: "#EDE9FE",
    paddingTop: 14,
  },
  vocabHeader: {
    marginBottom: 12,
  },
  vocabHeaderRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: 8,
    marginBottom: 5,
  },
  vocabHeaderTitle: {
    fontSize: 15,
    fontWeight: "900",
    color: "#1E1B4B",
    flex: 1,
  },
  vocabReviewCountPill: {
    maxWidth: 132,
    backgroundColor: "#ECFDF5",
    borderRadius: 12,
    paddingHorizontal: 9,
    paddingVertical: 5,
    borderWidth: 1,
    borderColor: "#A7F3D0",
  },
  vocabReviewCountText: {
    fontSize: 10,
    lineHeight: 14,
    fontWeight: "800",
    color: "#047857",
    textAlign: "center",
  },
  vocabHeaderHint: {
    fontSize: 12,
    color: "#64748B",
    lineHeight: 17,
  },
  vocabItemWrap: {
    marginBottom: 10,
  },
  vocabCard: {
    borderRadius: 16,
    borderWidth: 1.5,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 2,
  },
  vocabLearnArea: {
    padding: 14,
    paddingBottom: 12,
  },
  vocabCardActive: {
    shadowOpacity: 0.12,
    shadowRadius: 8,
    elevation: 5,
  },
  vocabCardReviewed: {
    shadowColor: "#10B981",
    shadowOpacity: 0.15,
    shadowRadius: 8,
    elevation: 4,
  },
  vocabCardRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 6,
  },
  vocabTermRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    flex: 1,
  },
  vocabDetBadge: {
    fontSize: 14,
  },
  vocabTerm: {
    fontSize: 16,
    fontWeight: "900",
    flexShrink: 1,
  },
  vocabReviewedBadge: {
    backgroundColor: "#D1FAE5",
    borderRadius: 10,
    paddingHorizontal: 7,
    paddingVertical: 3,
    borderWidth: 1,
    borderColor: "#6EE7B7",
  },
  vocabReviewedBadgeText: {
    fontSize: 8,
    fontWeight: "900",
    color: "#047857",
    letterSpacing: 0.4,
  },
  vocabCardRight: {
    marginLeft: 8,
  },
  vocabActionPill: {
    borderRadius: 20,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  vocabActionText: {
    fontSize: 12,
    fontWeight: "700",
  },
  vocabDefinitionBox: {
    backgroundColor: "rgba(255,255,255,0.72)",
    borderRadius: 12,
    padding: 11,
    marginBottom: 8,
  },
  vocabDefinitionLabel: {
    fontSize: 9,
    fontWeight: "900",
    color: "#64748B",
    letterSpacing: 0.8,
    marginBottom: 4,
  },
  vocabDef: {
    fontSize: 13,
    color: "#374151",
    lineHeight: 18,
  },
  vocabExample: {
    backgroundColor: "rgba(255,255,255,0.6)",
    borderRadius: 10,
    padding: 10,
    marginBottom: 6,
    borderLeftWidth: 3,
    borderLeftColor: "#DDD6FE",
  },
  vocabExampleLabel: {
    fontSize: 9,
    fontWeight: "800",
    color: "#9CA3AF",
    letterSpacing: 0.8,
    marginBottom: 3,
  },
  vocabExampleText: {
    fontSize: 13,
    color: "#374151",
    fontStyle: "italic",
    lineHeight: 18,
  },
  synonymsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
    marginTop: 4,
  },
  synonymChip: {
    backgroundColor: "rgba(255,255,255,0.8)",
    borderRadius: 20,
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  synonymChipText: {
    fontSize: 12,
    fontWeight: "600",
    color: "#374151",
  },
  vocabReviewFooter: {
    minHeight: 58,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 10,
    paddingHorizontal: 14,
    paddingVertical: 10,
    backgroundColor: "rgba(255,255,255,0.72)",
    borderTopWidth: 1,
    borderTopColor: "rgba(148,163,184,0.24)",
    borderBottomLeftRadius: 14,
    borderBottomRightRadius: 14,
  },
  vocabReviewHint: {
    flex: 1,
    fontSize: 11,
    lineHeight: 15,
    fontWeight: "600",
    color: "#64748B",
  },
  vocabGotItButton: {
    minWidth: 88,
    minHeight: 40,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#7C3AED",
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 9,
  },
  vocabGotItButtonReviewed: {
    backgroundColor: "#D1FAE5",
    borderWidth: 1.5,
    borderColor: "#6EE7B7",
  },
  vocabGotItText: {
    fontSize: 13,
    fontWeight: "900",
    color: "#FFFFFF",
  },
  vocabGotItTextReviewed: {
    color: "#047857",
  },
  vocabEmptyBox: {
    alignItems: "center",
    paddingVertical: 16,
    gap: 8,
  },
  vocabEmptyIcon: {
    fontSize: 28,
  },
  vocabEmptyText: {
    fontSize: 14,
    color: "#64748B",
    textAlign: "center",
    lineHeight: 20,
  },

  // explain panel
  explainPanel: {
    backgroundColor: "#F8FAFC",
    borderRadius: 14,
    padding: 14,
    marginTop: 6,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  explainLoadingRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  explainLoadingInner: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    flex: 1,
  },
  explainLoadingText: {
    fontSize: 13,
    color: "#7C3AED",
    flex: 1,
  },
  explainCloseText: {
    fontSize: 13,
    fontWeight: "700",
    color: "#7C3AED",
    paddingHorizontal: 4,
  },
  explainErrorWrap: {
    gap: 8,
  },
  explainPanelRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  explainErrorTitle: {
    fontSize: 14,
    fontWeight: "800",
    color: "#E11D48",
    flex: 1,
  },
  explainErrorMsg: {
    fontSize: 13,
    color: "#374151",
    lineHeight: 18,
  },
  explainRetryBtn: {
    alignSelf: "flex-start",
    backgroundColor: "#EDE9FE",
    borderRadius: 10,
    paddingVertical: 7,
    paddingHorizontal: 14,
  },
  explainRetryText: {
    fontSize: 13,
    fontWeight: "700",
    color: "#7C3AED",
  },
  explainResultTerm: {
    fontSize: 16,
    fontWeight: "900",
    color: "#7C3AED",
    flex: 1,
  },
  explainDef: {
    fontSize: 14,
    color: "#374151",
    lineHeight: 20,
    marginTop: 8,
    marginBottom: 8,
  },
  explainFriendlyBox: {
    backgroundColor: "#EDE9FE",
    borderRadius: 12,
    padding: 12,
    marginBottom: 8,
  },
  explainFriendlyLabel: {
    fontSize: 9,
    fontWeight: "800",
    color: "#7C3AED",
    letterSpacing: 0.8,
    marginBottom: 4,
  },
  explainFriendlyText: {
    fontSize: 14,
    color: "#1E1B4B",
    lineHeight: 20,
  },
  explainExampleBox: {
    backgroundColor: "#F0F9FF",
    borderRadius: 12,
    padding: 12,
    marginBottom: 8,
    borderLeftWidth: 3,
    borderLeftColor: "#BAE6FD",
  },
  explainExampleLabel: {
    fontSize: 9,
    fontWeight: "800",
    color: "#0EA5E9",
    letterSpacing: 0.8,
    marginBottom: 4,
  },
  explainExampleText: {
    fontSize: 14,
    color: "#1E293B",
    fontStyle: "italic",
    lineHeight: 20,
  },
  explainSynLabel: {
    fontSize: 9,
    fontWeight: "800",
    color: "#9CA3AF",
    letterSpacing: 0.8,
    marginBottom: 6,
    marginTop: 4,
  },

  // ── FEEDBACK SECTION ──────────────────────────────────────────────────────
  // PDF learning pack
  learningPackSection: {
    marginHorizontal: 16,
    marginTop: 14,
    padding: 16,
    backgroundColor: "#FFFBEB",
    borderRadius: 22,
    borderWidth: 1.5,
    borderColor: "#FDE68A",
    shadowColor: "#92400E",
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 3,
  },
  learningPackHeaderRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    marginBottom: 14,
  },
  learningPackIcon: {
    width: 52,
    height: 52,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#F97316",
    borderBottomWidth: 4,
    borderBottomColor: "#C2410C",
  },
  learningPackIconText: {
    color: "#FFFFFF",
    fontSize: 14,
    fontWeight: "900",
    letterSpacing: 0.5,
  },
  learningPackHeaderCopy: {
    flex: 1,
  },
  learningPackTitle: {
    color: "#78350F",
    fontSize: 19,
    fontWeight: "900",
    marginBottom: 3,
  },
  learningPackSubtitle: {
    color: "#92400E",
    fontSize: 12,
    lineHeight: 17,
  },
  learningPackActions: {
    gap: 10,
  },
  learningPackButton: {
    minHeight: 50,
    borderRadius: 15,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 16,
    paddingVertical: 13,
    borderWidth: 1.5,
  },
  learningPackPreviewButton: {
    backgroundColor: "#FFFFFF",
    borderColor: "#C4B5FD",
    borderBottomWidth: 4,
    borderBottomColor: "#C4B5FD",
  },
  learningPackShareButton: {
    backgroundColor: "#6D28D9",
    borderColor: "#6D28D9",
    borderBottomWidth: 4,
    borderBottomColor: "#4C1D95",
  },
  learningPackButtonDisabled: {
    opacity: 0.55,
  },
  learningPackPreviewButtonText: {
    color: "#6D28D9",
    fontSize: 15,
    fontWeight: "900",
  },
  learningPackShareButtonText: {
    color: "#FFFFFF",
    fontSize: 15,
    fontWeight: "900",
  },
  learningPackStatus: {
    marginTop: 12,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
  },
  learningPackStatusText: {
    color: "#6D28D9",
    fontSize: 13,
    fontWeight: "700",
  },
  learningPackError: {
    marginTop: 12,
    padding: 11,
    borderRadius: 12,
    backgroundColor: "#FFF1F2",
    borderWidth: 1,
    borderColor: "#FECDD3",
  },
  learningPackErrorText: {
    color: "#BE123C",
    fontSize: 13,
    fontWeight: "700",
    lineHeight: 18,
  },
  learningPackRetryText: {
    marginTop: 3,
    color: "#9F1239",
    fontSize: 12,
    lineHeight: 17,
  },

  feedbackSection: {
    marginHorizontal: 16,
    marginTop: 14,
    backgroundColor: "#FFFFFF",
    borderRadius: 24,
    padding: 18,
    borderWidth: 1.5,
    borderColor: "#EDE9FE",
    shadowColor: "#7C3AED",
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.08,
    shadowRadius: 10,
    elevation: 4,
  },
  feedbackHeader: {
    marginBottom: 14,
  },
  feedbackTitle: {
    fontSize: 18,
    fontWeight: "900",
    color: "#1E1B4B",
    marginBottom: 4,
  },
  feedbackSub: {
    fontSize: 13,
    color: "#64748B",
    lineHeight: 18,
  },
  feedbackGrid: {
    flexDirection: "row",
    gap: 8,
  },
  feedbackCard: {
    flex: 1,
    borderRadius: 18,
    padding: 12,
    alignItems: "center",
    gap: 5,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 2,
    borderBottomWidth: 3,
  },
  feedbackEmoji: {
    fontSize: 26,
  },
  feedbackLabel: {
    fontSize: 12,
    fontWeight: "800",
    color: "#374151",
    textAlign: "center",
  },
  feedbackSubLabel: {
    fontSize: 10,
    color: "#94A3B8",
    textAlign: "center",
    fontWeight: "600",
  },
  feedbackThanksBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    backgroundColor: "#ECFDF5",
    borderRadius: 16,
    padding: 14,
    borderWidth: 1.5,
    borderColor: "#A7F3D0",
  },
  feedbackThanksIcon: {
    fontSize: 24,
  },
  feedbackThanksText: {
    flex: 1,
    fontSize: 14,
    fontWeight: "700",
    color: "#065F46",
    lineHeight: 20,
  },
  levelSuggestionCard: {
    marginTop: 12,
    padding: 15,
    backgroundColor: "#F5F3FF",
    borderRadius: 17,
    borderWidth: 1.5,
    borderColor: "#DDD6FE",
  },
  levelSuggestionEyebrow: {
    color: "#7C3AED",
    fontSize: 10,
    fontWeight: "900",
    letterSpacing: 0.8,
    marginBottom: 5,
  },
  levelSuggestionTitle: {
    color: "#1E1B4B",
    fontSize: 16,
    fontWeight: "900",
    lineHeight: 21,
    marginBottom: 5,
  },
  levelSuggestionMessage: {
    color: "#475569",
    fontSize: 13,
    lineHeight: 19,
  },
  levelSuggestionButton: {
    minHeight: 48,
    marginTop: 12,
    paddingHorizontal: 16,
    paddingVertical: 12,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#7C3AED",
    borderRadius: 14,
    borderBottomWidth: 4,
    borderBottomColor: "#5B21B6",
  },
  levelSuggestionButtonText: {
    color: "#FFFFFF",
    fontSize: 14,
    fontWeight: "900",
  },
  levelSuggestionAccepted: {
    marginTop: 12,
    paddingHorizontal: 12,
    paddingVertical: 10,
    backgroundColor: "#ECFDF5",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#A7F3D0",
  },
  levelSuggestionAcceptedText: {
    color: "#047857",
    fontSize: 13,
    fontWeight: "800",
    lineHeight: 18,
    textAlign: "center",
  },
  levelSuggestionNote: {
    marginTop: 10,
    color: "#64748B",
    fontSize: 11,
    lineHeight: 16,
  },
  feedbackErrorBox: {
    marginTop: 10,
    backgroundColor: "#FFF1F2",
    borderRadius: 12,
    padding: 12,
    borderWidth: 1.5,
    borderColor: "#FECDD3",
  },
  feedbackErrorText: {
    fontSize: 13,
    color: "#E11D48",
    lineHeight: 18,
  },

  // new reading button
  newReadingBtn: {
    marginHorizontal: 16,
    marginTop: 14,
    marginBottom: 8,
    backgroundColor: "#FFFFFF",
    borderRadius: 18,
    paddingVertical: 16,
    alignItems: "center",
    borderWidth: 2,
    borderColor: "#DDD6FE",
    borderBottomWidth: 4,
    borderBottomColor: "#DDD6FE",
  },
  newReadingBtnText: {
    fontSize: 16,
    fontWeight: "900",
    color: "#7C3AED",
  },
});
