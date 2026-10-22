// Offline handler/transport tests using existing TypeScript and Node dependencies.
// The hook harness exercises App callbacks; it is not a native UI renderer.
const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");

function load(file, dependencies = {}, runtimeGlobal = globalThis) {
  const source = ts.transpileModule(fs.readFileSync(file, "utf8"), {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      jsx: ts.JsxEmit.React,
      target: ts.ScriptTarget.ES2022,
      esModuleInterop: true,
    },
  }).outputText;
  const exports = {};
  vm.runInNewContext(source, {
    exports, AbortController, Error, Object, JSON, globalThis: runtimeGlobal,
    encodeURIComponent,
    require(name) {
      assert.ok(name in dependencies, `Unexpected dependency: ${name}`);
      return dependencies[name];
    },
  }, { filename: file });
  return exports;
}

const client = load(path.resolve(__dirname, "../../..", "packages/api-client/src/client.ts"));
const learnerId = "11111111-1111-4111-8111-111111111111";
const sessionId = "22222222-2222-4222-8222-222222222222";
const vocab = (term) => ({
  term, simplified_definition: `Simple ${term}`, example_sentence: "Synthetic context.",
  synonyms: [], source: "automatic",
});
const result = (
  text = "Synthetic simplified passage.",
  vocabularyItems = [vocab("habitat"), vocab("forest")],
) => ({
  learner_id: learnerId, session_id: sessionId, simplified_text: text,
  target_reading_level: "elementary", strategy_applied: "combined",
  estimated_output_difficulty: "0.25", adaptation_attempt: 1,
  vocabulary_items: vocabularyItems, warnings: [],
  created_at: "2026-01-01T00:00:00Z",
});
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
function harness(initialSession = {
  learnerId, accessToken: "synthetic-token", refreshToken: "synthetic-refresh-token",
}) {
  const slots = [];
  const cleanups = [];
  let cursor = 0, session = initialSession, tree;
  let sessionListener;
  const calls = [];
  const nativeCalls = [];
  let sharingAvailable = true;
  const api = Object.fromEntries(
    ["simplifyText", "explainWord", "submitReadingFeedback"].map((method) => [
      method, (...args) => {
        const pending = deferred();
        calls.push({ method, args, ...pending });
        return pending.promise; // Deliberately ignores abort to test late responses.
      },
    ]),
  );
  const react = {
    createElement(type, props, ...children) {
      return { type, props: props || {}, children: children.flat(Infinity) };
    },
    useState(initial) {
      const i = cursor++;
      if (!(i in slots)) slots[i] = typeof initial === "function" ? initial() : initial;
      return [slots[i], (value) => {
        slots[i] = typeof value === "function" ? value(slots[i]) : value;
      }];
    },
    useRef(initial) {
      const i = cursor++;
      if (!(i in slots)) slots[i] = { current: initial };
      return slots[i];
    },
    useEffect(effect) {
      const i = cursor++;
      if (!(i in slots)) { slots[i] = true; cleanups.push(effect()); }
    },
    useMemo(factory) {
      return factory();
    },
  };
  const native = Object.fromEntries([
    "Text", "View", "SafeAreaView", "ScrollView", "TextInput", "TouchableOpacity",
    "KeyboardAvoidingView", "ActivityIndicator",
  ].map((name) => [name, name]));
  native.StyleSheet = { create: (value) => value };
  native.Platform = { OS: "ios" };
  const print = {
    printAsync: (...args) => {
      const pending = deferred();
      nativeCalls.push({ method: "printAsync", args, ...pending });
      return pending.promise;
    },
    printToFileAsync: (...args) => {
      const pending = deferred();
      nativeCalls.push({ method: "printToFileAsync", args, ...pending });
      return pending.promise;
    },
  };
  const sharing = {
    isAvailableAsync: async () => {
      nativeCalls.push({ method: "isAvailableAsync", args: [] });
      return sharingAvailable;
    },
    shareAsync: (...args) => {
      const pending = deferred();
      nativeCalls.push({ method: "shareAsync", args, ...pending });
      return pending.promise;
    },
  };
  const appModule = load(path.resolve(__dirname, "../App.tsx"), {
    react,
    "react-native": native,
    "expo-status-bar": { StatusBar: "StatusBar" },
    "expo-print": print,
    "expo-sharing": sharing,
    "./src/config/env": { API_BASE_URL: "http://localhost:8000" },
    "./src/services/api": {
      simplificationClient: api,
      SimplificationApiError: client.SimplificationApiError,
      getAuthSession: () => session,
      setAuthSession: (next) => { session = next; },
      clearAuthSession: () => { session = {}; },
      restoreAuthSession: async () => session,
      subscribeAuthSession: (listener) => {
        sessionListener = listener;
        return () => { sessionListener = undefined; };
      },
      getEffectiveApiBaseUrl: () => "http://localhost:8000",
    },
  });
  const { default: App } = appModule;
  function render() { cursor = 0; tree = App(); return tree; }
  function nodes(node = tree) {
    return node && typeof node === "object"
      ? [node, ...node.children.flatMap((child) => nodes(child))]
      : [];
  }
  function text(node = tree) {
    return node && typeof node === "object"
      ? node.children.map((child) => text(child)).join("")
      : (node || "").toString();
  }
  function press(label) {
    render();
    const node = nodes().find((n) => n.props.onPress &&
      (n.props.accessibilityLabel === label || text(n) === label));
    assert.ok(node, `Button not found: ${label}`);
    assert.ok(!node.props.disabled, `Button disabled: ${label}`);
    const pending = node.props.onPress();
    render();
    return pending;
  }
  function enter(passage = "Synthetic passage.") {
    render();
    nodes().find((n) => n.props.accessibilityLabel === "Reading passage input")
      .props.onChangeText(passage);
    render();
  }
  async function simplify(textValue, vocabularyItems, sourceText = "Synthetic passage.") {
    enter(sourceText);
    const pending = press("Simplify my text");
    calls.at(-1).resolve(result(textValue, vocabularyItems));
    await pending;
    render();
  }
  function textByAccessibilityLabel(label) {
    render();
    const node = nodes().find((candidate) => candidate.props.accessibilityLabel === label);
    assert.ok(node, `Node not found: ${label}`);
    return text(node);
  }
  function nodeByAccessibilityLabel(label) {
    render();
    const node = nodes().find((candidate) => candidate.props.accessibilityLabel === label);
    assert.ok(node, `Node not found: ${label}`);
    return node;
  }
  function backgroundColorsByAccessibilityLabel(label) {
    const root = nodeByAccessibilityLabel(label);
    return nodes(root).flatMap((node) => {
      const styles = Array.isArray(node.props.style) ? node.props.style : [node.props.style];
      return styles.filter(Boolean).map((style) => style.backgroundColor).filter(Boolean);
    });
  }
  render();
  return { calls, nativeCalls, press, enter, render, simplify, text, textByAccessibilityLabel,
    nodeByAccessibilityLabel, backgroundColorsByAccessibilityLabel,
    calculatePassageHighlights: appModule.calculatePassageHighlights,
    buildLearningPackHtml: appModule.buildLearningPackHtml,
    escapeLearningPackHtml: appModule.escapeLearningPackHtml,
    maxDiffMatrixCells: appModule.MAX_DIFF_MATRIX_CELLS,
    setSharingAvailable: (available) => { sharingAvailable = available; },
    setSession: (next) => { session = next; sessionListener?.(next); render(); },
    unmount: () => cleanups.forEach((cleanup) => cleanup?.()) };
}

const reconstruct = (segments) => segments.map(({ text }) => text).join("");
const highlightedText = (segments, kind) =>
  segments.filter((segment) => segment.kind === kind).map(({ text }) => text).join("|");
const flushPromises = () => new Promise((resolve) => setImmediate(resolve));

const learningPackSnapshot = (overrides = {}) => ({
  originalText: "  Original <passage>.\n\nSecond paragraph.  ",
  simplifiedText: "Simplified & friendly.\nNext line.",
  readingLevel: "middle_school",
  strategy: "concept_reduction",
  vocabularyItems: [
    {
      term: "eco<script>",
      simplifiedDefinition: 'A "safe" definition & explanation.',
      exampleSentence: "An ecosystem supports life.",
      synonyms: ["environment", "habitat"],
    },
  ],
  ...overrides,
});

test("learning-pack HTML escapes dynamic content and preserves passage whitespace", () => {
  const app = harness();
  const snapshot = learningPackSnapshot();
  const html = app.buildLearningPackHtml(snapshot);

  assert.match(html, /ReadBuddy Learning Pack/);
  assert.match(html, /Reading level: Middle School/);
  assert.match(html, /Strategy: Concept Reduction/);
  assert.ok(html.includes("  Original &lt;passage&gt;.\n\nSecond paragraph.  "));
  assert.ok(html.includes("Simplified &amp; friendly.\nNext line."));
  assert.match(html, /white-space: pre-wrap/);
  assert.match(html, /eco&lt;script&gt;/);
  assert.match(html, /A &quot;safe&quot; definition &amp; explanation\./);
  assert.doesNotMatch(html, /<script>/);
});

test("learning-pack HTML includes supplied vocabulary details and omits absent fields", () => {
  const app = harness();
  const complete = app.buildLearningPackHtml(learningPackSnapshot());
  assert.match(complete, /An ecosystem supports life\./);
  assert.match(complete, /environment/);
  assert.match(complete, /habitat/);

  const minimal = app.buildLearningPackHtml(learningPackSnapshot({
    originalText: null,
    vocabularyItems: [{
      term: "plain",
      simplifiedDefinition: "Easy to understand.",
      exampleSentence: null,
      synonyms: [],
    }],
  }));
  assert.doesNotMatch(minimal, /Original Passage/);
  assert.doesNotMatch(minimal, /class="example"/);
  assert.doesNotMatch(minimal, /class="synonyms"/);
});

test("learning-pack HTML excludes internal identifiers, tokens, feedback, and review state", () => {
  const app = harness();
  const html = app.buildLearningPackHtml({
    ...learningPackSnapshot(),
    learnerId: "learner-secret-value",
    sessionId: "session-secret-value",
    accessToken: "token-secret-value",
    feedback: "too_hard",
    reviewedVocabularyItems: ["eco<script>"],
  });

  for (const forbidden of [
    "learner-secret-value", "session-secret-value", "token-secret-value",
    "too_hard", "reviewedVocabularyItems",
  ]) assert.ok(!html.includes(forbidden));
});

test("local diff leaves identical text unchanged", () => {
  const app = harness();
  const text = "  Café, 猫!\n\nSame words.  ";
  const highlights = app.calculatePassageHighlights(text, text, []);

  assert.equal(reconstruct(highlights.original), text);
  assert.equal(reconstruct(highlights.simplified), text);
  assert.equal(highlightedText(highlights.original, "changed"), "");
  assert.equal(highlightedText(highlights.simplified, "changed"), "");
  assert.equal(highlights.usedFallback, false);
});

test("local diff marks insertions, deletions, substitutions, and changed phrases", () => {
  const app = harness();
  const original = "A very, difficult task ended yesterday.";
  const simplified = "A simple task ended quickly today.";
  const highlights = app.calculatePassageHighlights(original, simplified, []);

  assert.equal(reconstruct(highlights.original), original);
  assert.equal(reconstruct(highlights.simplified), simplified);
  assert.match(highlightedText(highlights.original, "changed"), /very, difficult/);
  assert.match(highlightedText(highlights.original, "changed"), /yesterday/);
  assert.match(highlightedText(highlights.simplified, "changed"), /simple/);
  assert.match(highlightedText(highlights.simplified, "changed"), /quickly today/);
});

test("local diff preserves Unicode, punctuation, whitespace, and line breaks exactly", () => {
  const app = harness();
  const original = "  Café—猫.\n\n“Hello!”  \n";
  const simplified = "  Cafe—猫.\n\n“Hi!”  \n";
  const highlights = app.calculatePassageHighlights(original, simplified, []);

  assert.equal(reconstruct(highlights.original), original);
  assert.equal(reconstruct(highlights.simplified), simplified);
  assert.match(highlightedText(highlights.original, "changed"), /Café.*Hello/s);
  assert.match(highlightedText(highlights.simplified, "changed"), /Cafe.*Hi/s);
});

test("repeated-word alignment is deterministic", () => {
  const app = harness();
  const args = ["one two one three", "one one two three", []];
  const first = app.calculatePassageHighlights(...args);
  const second = app.calculatePassageHighlights(...args);

  assert.deepEqual(first, second);
  assert.equal(reconstruct(first.original), args[0]);
  assert.equal(reconstruct(first.simplified), args[1]);
  assert.notEqual(highlightedText(first.original, "changed"), "");
  assert.notEqual(highlightedText(first.simplified, "changed"), "");
});

test("vocabulary matches whole words and multiword phrases case-insensitively", () => {
  const app = harness();
  const text = "Cat category NEW YORK and new yorker; New York.";
  const highlights = app.calculatePassageHighlights(text, text, ["cat", "new york"]);
  const blue = highlights.simplified.filter(({ kind }) => kind === "vocabulary");

  assert.equal(reconstruct(highlights.simplified), text);
  assert.deepEqual([...blue.map(({ text: value }) => value)], ["Cat", "NEW YORK", "New York"]);
  assert.ok(!blue.some(({ text: value }) => value.includes("category") || value.includes("yorker")));
});

test("blue vocabulary has priority over overlapping yellow changes", () => {
  const app = harness();
  const highlights = app.calculatePassageHighlights(
    "A difficult habitat.",
    "A simple ecosystem.",
    ["simple ecosystem"],
  );

  assert.equal(highlightedText(highlights.simplified, "vocabulary"), "simple ecosystem");
  assert.equal(highlightedText(highlights.simplified, "changed"), "");
  assert.match(highlightedText(highlights.original, "changed"), /difficult habitat/);
});

test("large rewrites use the bounded conservative fallback", () => {
  const app = harness();
  const original = Array.from({ length: 600 }, (_, index) => `old${index}`).join(" ");
  const simplified = Array.from({ length: 600 }, (_, index) => `new${index}`).join(" ");
  assert.ok(600 * 600 > app.maxDiffMatrixCells);

  const highlights = app.calculatePassageHighlights(original, simplified, []);

  assert.equal(highlights.usedFallback, true);
  assert.equal(reconstruct(highlights.original), original);
  assert.equal(reconstruct(highlights.simplified), simplified);
  assert.equal(highlightedText(highlights.original, "changed"), original);
  assert.equal(highlightedText(highlights.simplified, "changed"), simplified);
});

test("simplification uses selected values and renders vocabulary", async () => {
  const app = harness();
  app.enter();
  app.press("Beginner level: Shortest sentences and simplest everyday words");
  app.press("Sentence Split strategy: Breaks long, winding sentences into bite-sized pieces");
  const pending = app.press("Simplify my text");
  const call = app.calls[0];
  assert.equal(call.args[0], learnerId);
  assert.equal(call.args[1].target_reading_level, "beginner");
  assert.equal(call.args[1].preferred_strategy, "sentence_split");
  call.resolve(result());
  await pending; app.render();
  assert.match(app.text(), /Synthetic simplified passage/);
  assert.match(app.text(), /Simple habitat/);
  assert.match(app.text(), /Synthetic context/);
});

test("simplified-only is the default and compare preserves exact source whitespace", async () => {
  const app = harness();
  const original = "  First line.\n\nSecond line.  \n";
  await app.simplify("A simpler version.", undefined, original);

  assert.equal(app.calls[0].args[1].source_text, "First line.\n\nSecond line.");
  assert.equal(app.textByAccessibilityLabel("Simplified passage"), "A simpler version.");
  assert.doesNotMatch(app.text(), /First line/);
  assert.equal((app.text().match(/Word Detective Helpers/g) || []).length, 1);

  await app.press("Compare");
  assert.equal(app.textByAccessibilityLabel("Original passage"), original);
  assert.equal(app.textByAccessibilityLabel("Simplified passage"), "A simpler version.");
  assert.equal((app.text().match(/Word Detective Helpers/g) || []).length, 1);
});

test("switching result views does not make another API request", async () => {
  const app = harness();
  await app.simplify("A simpler version.");
  const requestCount = app.calls.length;

  await app.press("Compare");
  assert.match(app.text(), /ORIGINAL TEXT/);
  await app.press("Simplified Only");

  assert.equal(app.calls.length, requestCount);
  assert.doesNotMatch(app.text(), /ORIGINAL TEXT/);
  assert.match(app.text(), /A simpler version/);
});

test("show highlights switch changes styling without requests or changing the view", async () => {
  const app = harness();
  await app.simplify(
    "A simple habitat.",
    [vocab("habitat")],
    "A difficult habitat.",
  );
  const requestCount = app.calls.length;
  const switchNode = app.nodeByAccessibilityLabel("Show highlights");
  assert.equal(switchNode.props.accessibilityRole, "switch");
  assert.equal(switchNode.props.accessibilityState.checked, true);
  assert.ok(app.backgroundColorsByAccessibilityLabel("Simplified passage").includes("#FDE68A"));
  assert.ok(app.backgroundColorsByAccessibilityLabel("Simplified passage").includes("#BFDBFE"));

  await app.press("Show highlights");
  assert.equal(app.nodeByAccessibilityLabel("Show highlights").props.accessibilityState.checked, false);
  assert.deepEqual(app.backgroundColorsByAccessibilityLabel("Simplified passage"), []);
  assert.equal(app.textByAccessibilityLabel("Simplified passage"), "A simple habitat.");

  await app.press("Compare");
  assert.equal(app.nodeByAccessibilityLabel("Compare").props.accessibilityState.selected, true);
  assert.deepEqual(app.backgroundColorsByAccessibilityLabel("Original passage"), []);
  assert.deepEqual(app.backgroundColorsByAccessibilityLabel("Simplified passage"), []);
  assert.equal(app.calls.length, requestCount);

  await app.press("Show highlights");
  assert.ok(app.backgroundColorsByAccessibilityLabel("Original passage").includes("#FDE68A"));
  assert.ok(app.backgroundColorsByAccessibilityLabel("Original passage").includes("#BFDBFE"));
  assert.equal(app.nodeByAccessibilityLabel("Compare").props.accessibilityState.selected, true);
  assert.equal(app.calls.length, requestCount);
});

test("a later successful simplification replaces the matching original passage", async () => {
  const app = harness();
  await app.simplify("First simpler result.", [], "  First original.  ");
  await app.press("Compare");
  assert.equal(app.textByAccessibilityLabel("Original passage"), "  First original.  ");

  await app.press("Reset");
  await app.simplify("Second simpler result.", [], "\nSecond original.\n");
  assert.doesNotMatch(app.text(), /First original|Second original/);
  await app.press("Compare");

  assert.equal(app.textByAccessibilityLabel("Original passage"), "\nSecond original.\n");
  assert.doesNotMatch(app.text(), /First original|First simpler result/);
});

test("reset and failed attempts clear comparison state", async () => {
  const app = harness();
  await app.simplify("Old simpler result.", [], "Old original passage.");
  await app.press("Compare");
  assert.match(app.text(), /Old original passage/);

  await app.press("Reset");
  assert.doesNotMatch(app.text(), /Old original passage|Old simpler result|Simplified Only/);

  app.enter("  New passage that will fail.  ");
  const pending = app.press("Simplify my text");
  app.calls.at(-1).reject(
    new client.SimplificationApiError(503, "service_unavailable", "Unavailable"),
  );
  await pending;
  app.render();

  assert.match(app.text(), /Service Unavailable/);
  assert.doesNotMatch(app.text(), /Old original passage|New passage that will fail|Simplified Only/);
});

test("vocabulary and feedback keep their request contracts after switching views", async () => {
  const app = harness();
  await app.simplify();
  await app.press("Compare");

  const explanation = app.press("Word: habitat. Tap to explain.");
  const explanationCall = app.calls.at(-1);
  assert.equal(explanationCall.method, "explainWord");
  assert.equal(explanationCall.args[0], learnerId);
  assert.equal(explanationCall.args[1].session_id, sessionId);
  assert.equal(explanationCall.args[1].context_sentence, "Synthetic context.");
  explanationCall.resolve({
    learner_id: learnerId,
    session_id: sessionId,
    language_tag: "en",
    item: vocab("habitat"),
    created_at: "2026-01-01T00:00:00Z",
  });
  await explanation;
  app.render();

  const feedback = app.press("Feedback: Just Right");
  const feedbackCall = app.calls.at(-1);
  assert.equal(feedbackCall.method, "submitReadingFeedback");
  assert.equal(feedbackCall.args[0], learnerId);
  assert.equal(feedbackCall.args[1], sessionId);
  assert.equal(feedbackCall.args[2].feedback_signal, "just_right");
  assert.equal(feedbackCall.args[2].completed_reading, true);
  feedbackCall.resolve({ feedback_recorded: true });
  await feedback;
});

test("empty vocabulary response shows a friendly state without internal session ID", async () => {
  const app = harness();
  await app.simplify("Hello everyone!", []);
  assert.match(app.text(), /No tricky words this time/);
  assert.match(app.text(), /no extra vocabulary help is needed/i);
  assert.doesNotMatch(app.text(), new RegExp(sessionId.slice(0, 8)));
});

test("learning-pack preview prints one immutable result snapshot without API calls", async () => {
  const app = harness();
  const original = "  Exact original.\n\nAnother paragraph.  ";
  await app.simplify("A simpler result.", [vocab("habitat")], original);
  const apiCallCount = app.calls.length;

  const pending = app.press("Preview and print learning pack");
  const printCall = app.nativeCalls.find(({ method }) => method === "printAsync");
  assert.ok(printCall);
  assert.ok(printCall.args[0].html.includes(original));
  assert.match(printCall.args[0].html, /A simpler result\./);
  assert.match(app.text(), /Preparing your learning pack/);
  assert.equal(app.calls.length, apiCallCount);

  printCall.resolve();
  await pending;
  app.render();
  assert.doesNotMatch(app.text(), /Preparing your learning pack/);
  assert.equal(app.calls.length, apiCallCount);
});

test("learning-pack sharing generates a PDF URI and opens the native share sheet", async () => {
  const app = harness();
  await app.simplify("A simpler result.");
  const apiCallCount = app.calls.length;

  const pending = app.press("Share or save PDF learning pack");
  await flushPromises();
  const fileCall = app.nativeCalls.find(({ method }) => method === "printToFileAsync");
  assert.ok(fileCall);
  fileCall.resolve({ uri: "file:///synthetic-learning-pack.pdf" });
  await flushPromises();

  const shareCall = app.nativeCalls.find(({ method }) => method === "shareAsync");
  assert.ok(shareCall);
  assert.equal(shareCall.args[0], "file:///synthetic-learning-pack.pdf");
  assert.equal(shareCall.args[1].mimeType, "application/pdf");
  assert.equal(shareCall.args[1].UTI, "com.adobe.pdf");
  shareCall.resolve();
  await pending;
  assert.equal(app.calls.length, apiCallCount);
});

test("unavailable sharing shows a retryable message after generating the local PDF", async () => {
  const app = harness();
  await app.simplify("A simpler result.");
  app.setSharingAvailable(false);

  const pending = app.press("Share or save PDF learning pack");
  const fileCall = app.nativeCalls.find(({ method }) => method === "printToFileAsync");
  assert.ok(fileCall);
  fileCall.resolve({ uri: "file:///synthetic-unshared-pack.pdf" });
  await pending;
  app.render();
  assert.match(app.text(), /Sharing is not available on this device/);
  assert.match(app.text(), /try again/i);
  assert.ok(app.nativeCalls.some(({ method }) => method === "isAvailableAsync"));
  assert.ok(!app.nativeCalls.some(({ method }) => method === "shareAsync"));
});

test("learning-pack failures clear loading and allow a retry", async () => {
  const app = harness();
  await app.simplify("A simpler result.");

  const failed = app.press("Preview and print learning pack");
  const firstPrint = app.nativeCalls.find(({ method }) => method === "printAsync");
  firstPrint.reject(new Error("Synthetic native print failure"));
  await failed;
  app.render();
  assert.match(app.text(), /could not prepare your learning pack/i);
  assert.match(app.text(), /try again/i);

  const retried = app.press("Preview and print learning pack");
  const printCalls = app.nativeCalls.filter(({ method }) => method === "printAsync");
  assert.equal(printCalls.length, 2);
  printCalls[1].resolve();
  await retried;
  app.render();
  assert.doesNotMatch(app.text(), /could not prepare your learning pack/i);
});

test("learning-pack actions ignore duplicate taps while export is active", async () => {
  const app = harness();
  await app.simplify("A simpler result.");
  const button = app.nodeByAccessibilityLabel("Preview and print learning pack");

  const first = button.props.onPress();
  const duplicate = button.props.onPress();
  app.render();
  assert.equal(app.nativeCalls.filter(({ method }) => method === "printAsync").length, 1);
  assert.equal(app.nodeByAccessibilityLabel("Preview and print learning pack").props.disabled, true);

  app.nativeCalls.find(({ method }) => method === "printAsync").resolve();
  await Promise.all([first, duplicate]);
});

test("resetting a result prevents a generated stale PDF from being shared", async () => {
  const app = harness();
  await app.simplify("A result that will be reset.");

  const pending = app.press("Share or save PDF learning pack");
  await flushPromises();
  const fileCall = app.nativeCalls.find(({ method }) => method === "printToFileAsync");
  assert.ok(fileCall);
  app.press("Reset");
  fileCall.resolve({ uri: "file:///stale-learning-pack.pdf" });
  await pending;

  assert.ok(!app.nativeCalls.some(({ method }) => method === "shareAsync"));
  assert.doesNotMatch(app.text(), /PDF Learning Pack/);
});

test("vocabulary learning cards show supplied content and omit missing examples", async () => {
  const app = harness();
  const withExample = {
    ...vocab("ecosystem"),
    simplified_definition: "Living things working together in one place.",
    example_sentence: "A pond is an ecosystem.",
    synonyms: ["natural community"],
  };
  const withoutExample = {
    ...vocab("habitat"),
    simplified_definition: "A home for a plant or animal.",
    example_sentence: null,
  };
  await app.simplify("Simple result.", [withExample, withoutExample]);

  const ecosystemCard = app.textByAccessibilityLabel("Word: ecosystem. Tap to explain.");
  assert.match(ecosystemCard, /ecosystem/);
  assert.match(ecosystemCard, /Living things working together in one place/);
  assert.match(ecosystemCard, /A pond is an ecosystem/);
  assert.match(ecosystemCard, /natural community/);

  const habitatCard = app.textByAccessibilityLabel("Word: habitat. Tap to explain.");
  assert.match(habitatCard, /A home for a plant or animal/);
  assert.doesNotMatch(habitatCard, /TRY IT IN A SENTENCE/);
});

test("Got it acknowledges one card locally and updates the reviewed count", async () => {
  const app = harness();
  await app.simplify();
  const requestCount = app.calls.length;
  assert.match(app.text(), /0 of 2 reviewed this time/);

  await app.press("Got it: habitat, card 1");

  assert.equal(app.calls.length, requestCount);
  assert.match(app.text(), /1 of 2 reviewed this time/);
  assert.match(app.text(), /Nice work — reviewed for this reading/);
  assert.equal(
    app.nodeByAccessibilityLabel("Got it: habitat, card 1").props.accessibilityState.selected,
    true,
  );
  assert.equal(
    app.nodeByAccessibilityLabel("Got it: forest, card 2").props.accessibilityState.selected,
    false,
  );
});

test("duplicate vocabulary terms are acknowledged as separate cards", async () => {
  const app = harness();
  await app.simplify("Simple result.", [vocab("habitat"), vocab("habitat")]);

  await app.press("Got it: habitat, card 1");
  assert.match(app.text(), /1 of 2 reviewed this time/);
  assert.equal(
    app.nodeByAccessibilityLabel("Got it: habitat, card 1").props.accessibilityState.selected,
    true,
  );
  assert.equal(
    app.nodeByAccessibilityLabel("Got it: habitat, card 2").props.accessibilityState.selected,
    false,
  );

  await app.press("Got it: habitat, card 2");
  assert.match(app.text(), /2 of 2 reviewed this time/);

  const explanation = app.press("Word: habitat. Tap to explain.");
  assert.equal(
    (app.text().match(/Asking ReadBuddy AI for a helpful explanation/g) || []).length,
    1,
  );
  app.calls.at(-1).reject(
    new client.SimplificationApiError(503, "service_unavailable", "Unavailable"),
  );
  await explanation;
});

test("Got it remains available while an explanation loads or fails", async () => {
  const app = harness();
  await app.simplify();
  const explanation = app.press("Word: habitat. Tap to explain.");
  const explanationCall = app.calls.at(-1);
  assert.equal(explanationCall.method, "explainWord");

  await app.press("Got it: habitat, card 1");
  assert.equal(explanationCall.args[2].signal.aborted, false);
  assert.equal(app.calls.filter(({ method }) => method === "explainWord").length, 1);
  assert.match(app.text(), /1 of 2 reviewed this time/);

  explanationCall.reject(
    new client.SimplificationApiError(503, "service_unavailable", "Unavailable"),
  );
  await explanation;
  app.render();
  assert.match(app.text(), /AI vocabulary engine is currently unavailable/);
  assert.equal(
    app.nodeByAccessibilityLabel("Got it: habitat, card 1").props.accessibilityState.selected,
    true,
  );
});

test("Got it preserves comparison and highlight selections without requests", async () => {
  const app = harness();
  await app.simplify();
  await app.press("Compare");
  await app.press("Show highlights");
  const requestCount = app.calls.length;

  await app.press("Got it: habitat, card 1");

  assert.equal(app.calls.length, requestCount);
  assert.equal(app.nodeByAccessibilityLabel("Compare").props.accessibilityState.selected, true);
  assert.equal(
    app.nodeByAccessibilityLabel("Show highlights").props.accessibilityState.checked,
    false,
  );
});

test("vocabulary acknowledgments reset with result lifecycle changes", async () => {
  const app = harness();
  await app.simplify("First result.");
  await app.press("Got it: habitat, card 1");
  assert.match(app.text(), /1 of 2 reviewed this time/);

  await app.press("Reset");
  await app.simplify("Second result.");
  assert.match(app.text(), /0 of 2 reviewed this time/);

  await app.press("Got it: habitat, card 1");
  app.enter("Changed passage.");
  assert.match(app.text(), /0 of 2 reviewed this time/);

  const pending = app.press("Simplify my text");
  app.calls.at(-1).reject(
    new client.SimplificationApiError(503, "service_unavailable", "Unavailable"),
  );
  await pending;
  app.render();
  assert.doesNotMatch(app.text(), /reviewed this time|✓ REVIEWED/);
});

test("vocabulary explanation failure can retry without duplicate in-flight requests", async () => {
  const app = harness();
  await app.simplify();

  const first = app.press("Word: habitat. Tap to explain.");
  assert.equal(app.calls.filter(({ method }) => method === "explainWord").length, 1);
  await app.press("Word: habitat. Tap to explain.");
  assert.equal(app.calls.filter(({ method }) => method === "explainWord").length, 1);

  app.calls.at(-1).reject(
    new client.SimplificationApiError(503, "service_unavailable", "Unavailable"),
  );
  await first;
  app.render();
  assert.match(app.text(), /AI vocabulary engine is currently unavailable/);

  const retry = app.press("Retry explanation for habitat");
  const retryCall = app.calls.at(-1);
  assert.equal(retryCall.method, "explainWord");
  assert.equal(app.calls.filter(({ method }) => method === "explainWord").length, 2);
  retryCall.resolve({
    learner_id: learnerId,
    session_id: sessionId,
    language_tag: "en",
    item: {
      ...vocab("habitat"),
      simplified_definition: "A natural home for an animal.",
    },
    created_at: "2026-01-01T00:00:00Z",
  });
  await retry;
  app.render();
  assert.match(app.text(), /A natural home for an animal/);
  assert.doesNotMatch(app.text(), /AI vocabulary engine is currently unavailable/);
});

test("missing tokens block vocabulary explanation before API transport", async () => {
  const app = harness();
  await app.simplify();
  app.setSession({ learnerId, accessToken: null, refreshToken: null });

  await app.press("Word: habitat. Tap to explain.");

  assert.equal(app.calls.filter(({ method }) => method === "explainWord").length, 0);
  assert.match(app.text(), /Authentication Required/);
});

test("explanation switch and close ignore late successes and failures", async () => {
  const app = harness();
  await app.simplify();
  const first = app.press("Word: habitat. Tap to explain.");
  const a = app.calls.at(-1);
  assert.equal(a.args[1].session_id, sessionId);
  assert.equal(a.args[1].context_sentence, "Synthetic context.");
  const second = app.press("Word: forest. Tap to explain.");
  const b = app.calls.at(-1);
  assert.equal(a.args[2].signal.aborted, true);
  a.resolve({ item: { ...vocab("habitat"), simplified_definition: "STALE EXPLANATION" } });
  await first; app.render();
  assert.doesNotMatch(app.text(), /STALE EXPLANATION/);
  app.press("Cancel");
  assert.equal(b.args[2].signal.aborted, true);
  b.reject(new client.SimplificationApiError(503, "service_unavailable", "Late failure"));
  await second; app.render();
  assert.doesNotMatch(app.text(), /Late failure|Explanation Failed/);
});

for (const [signal, label] of [
  ["too_hard", "Too Hard"], ["just_right", "Just Right"],
  ["too_easy", "Too Easy"], ["skipped", "Skipped"],
]) {
  test(`feedback ${signal} sends consistent identifiers and completion`, async () => {
    const app = harness();
    await app.simplify();
    const pending = app.press(`Feedback: ${label}`);
    const call = app.calls.at(-1);
    assert.equal(call.args[0], learnerId);
    assert.equal(call.args[1], sessionId);
    assert.equal(call.args[2].feedback_signal, signal);
    assert.equal(call.args[2].completed_reading, signal !== "skipped");
    call.resolve({
      feedback_id: "33333333-3333-4333-8333-333333333333",
      session_id: sessionId, feedback_recorded: true, created_at: "2026-01-01T00:00:00Z",
    });
    await pending; app.render();
    assert.match(app.text(), /Thanks for your feedback/);
  });
}

for (const reject of [false, true]) {
  test(`reset/new simplification ignores pending feedback ${reject ? "failure" : "success"}`, async () => {
    const app = harness();
    await app.simplify();
    const pending = app.press("Feedback: Too Hard");
    const old = app.calls.at(-1);
    app.press("Reset");
    assert.equal(old.args[3].signal.aborted, true);
    await app.simplify("New synthetic result.");
    if (reject) old.reject(new Error("STALE FEEDBACK ERROR"));
    else old.resolve({ feedback_recorded: true });
    await pending; app.render();
    assert.doesNotMatch(app.text(), /Thanks for your feedback|STALE FEEDBACK ERROR/);
    assert.match(app.text(), /New synthetic result/);
  });
}

test("new simplification removes old result even when new request fails", async () => {
  const app = harness();
  await app.simplify("OLD RESULT");
  const pending = app.press("Simplify my text");
  assert.doesNotMatch(app.text(), /OLD RESULT|Simple habitat/);
  app.calls.at(-1).reject(new client.SimplificationApiError(503, "service_unavailable", "Unavailable"));
  await pending; app.render();
  assert.doesNotMatch(app.text(), /OLD RESULT/);
  assert.match(app.text(), /Service Unavailable/);
});

for (const action of ["Apply Session", "Clear"]) {
  test(`${action} clears data and cancels pending simplification`, async () => {
    const app = harness();
    app.enter();
    const pending = app.press("Simplify my text");
    const old = app.calls.at(-1);
    app.press("Toggle test session settings");
    app.press(action);
    assert.equal(old.args[2].signal.aborted, true);
    old.resolve(result("OLD LEARNER RESULT"));
    await pending; app.render();
    assert.doesNotMatch(app.text(), /OLD LEARNER RESULT|Simplifying passage/);
  });
}

test("missing token blocks submission and unmount cancels requests", async () => {
  const missing = harness({ learnerId, accessToken: null, refreshToken: null });
  missing.enter();
  await missing.press("Simplify my text");
  assert.equal(missing.calls.length, 0);
  const app = harness();
  app.enter();
  const pending = app.press("Simplify my text");
  const call = app.calls.at(-1);
  app.unmount();
  assert.equal(call.args[2].signal.aborted, true);
  call.resolve(result());
  await pending;
});

for (const status of [401, 403, 404, 422, 429, 503]) {
  test(`transport preserves sanitized ${status} envelope and UI handles it`, async () => {
    const api = client.createSimplificationClient({
      baseUrl: "http://localhost:8000/api/v1/",
      getAccessToken: () => "synthetic-token",
      fetch: async (url, options) => {
        assert.equal(url, `http://localhost:8000/api/v1/simplification/${learnerId}/simplify`);
        assert.equal(options.headers.Authorization, "Bearer synthetic-token");
        return new Response(JSON.stringify({ error: { code: "synthetic_error", message: "Safe failure" } }), {
          status, headers: { "content-type": "application/json", "Retry-After": "7" },
        });
      },
    });
    let error;
    try { await api.simplifyText(learnerId, { source_text: "Synthetic." }); }
    catch (caught) { error = caught; }
    assert.equal(error.status, status);
    assert.equal(error.retryAfter, 7);
    const app = harness();
    app.enter();
    const pending = app.press("Simplify my text");
    app.calls.at(-1).reject(error);
    await pending; app.render();
    assert.match(app.text(), new RegExp(String(status)));
  });
}

test("network failure and AbortError remain distinguishable", async () => {
  for (const abort of [false, true]) {
    const error = new Error("Synthetic network failure");
    if (abort) error.name = "AbortError";
    const api = client.createSimplificationClient({
      baseUrl: "http://localhost:8000", fetch: async () => { throw error; },
    });
    await assert.rejects(api.explainWord(learnerId, { term: "habitat" }), (caught) => {
      assert.equal(abort ? caught.name : caught.status, abort ? "AbortError" : 0);
      return true;
    });
  }
});

test("simplification transport preserves backend vocabulary response fields", async () => {
  const backendItem = {
    term: "ecosystem",
    simplified_definition: "Living things and their environment working together.",
    example_sentence: "A pond is a small ecosystem.",
    synonyms: ["natural community"],
    source: "automatic",
  };
  const api = client.createSimplificationClient({
    baseUrl: "http://localhost:8000",
    fetch: async () => new Response(
      JSON.stringify(result("A pond supports many living things.", [backendItem])),
      { headers: { "content-type": "application/json" } },
    ),
  });

  const response = await api.simplifyText(learnerId, {
    source_text: "Synthetic ecosystem passage.",
  });
  assert.deepEqual(response.vocabulary_items[0], backendItem);
});

test("successful word explanation is displayed for the active term", async () => {
  const app = harness();
  await app.simplify();
  const pending = app.press("Word: habitat. Tap to explain.");
  app.calls.at(-1).resolve({
    learner_id: learnerId, session_id: sessionId, language_tag: "en",
    item: { ...vocab("habitat"), simplified_definition: "An animal's natural home." },
    created_at: "2026-01-01T00:00:00Z",
  });
  await pending; app.render();
  assert.match(app.text(), /An animal's natural home/);
});

test("blank and oversized passages do not reach transport", async () => {
  const app = harness();
  for (const passage of ["  ", "x".repeat(50001)]) {
    app.enter(passage);
    await app.press("Simplify my text");
    assert.equal(app.calls.length, 0);
  }
});

test("network error is displayed and a subsequent request can succeed", async () => {
  const app = harness();
  app.enter();
  const pending = app.press("Simplify my text");
  app.calls.at(-1).reject(new client.SimplificationApiError(0, "network_error", "Offline"));
  await pending; app.render();
  assert.match(app.text(), /Network Connection Error/);
  await app.simplify();
  assert.doesNotMatch(app.text(), /Network Connection Error/);
});

test("explanation and feedback transport use simplification session contracts", async () => {
  const requests = [];
  const api = client.createSimplificationClient({
    baseUrl: "http://localhost:8000",
    fetch: async (url, options) => {
      requests.push({ url, body: JSON.parse(options.body) });
      return new Response(JSON.stringify({ session_id: sessionId }), {
        headers: { "content-type": "application/json" },
      });
    },
  });
  await api.explainWord(learnerId, { term: "habitat", session_id: sessionId });
  await api.submitReadingFeedback(learnerId, sessionId, { feedback_signal: "skipped" });
  assert.equal(requests[0].url, `http://localhost:8000/api/v1/simplification/${learnerId}/vocabulary/explain`);
  assert.equal(requests[0].body.session_id, sessionId);
  assert.equal(requests[1].url, `http://localhost:8000/api/v1/simplification/${learnerId}/sessions/${sessionId}/feedback`);
  assert.deepEqual(requests[1].body, { feedback_signal: "skipped" });
});

function authenticationError() {
  return new Response(JSON.stringify({
    error: { code: "authentication_required", message: "Authentication required" },
  }), { status: 401, headers: { "content-type": "application/json" } });
}

function loadMobileService(fetch, secureValues = new Map()) {
  const runtimeGlobal = { fetch };
  const runtimeClient = load(
    path.resolve(__dirname, "../../..", "packages/api-client/src/client.ts"),
    {},
    runtimeGlobal,
  );
  const secureStore = {
    WHEN_UNLOCKED_THIS_DEVICE_ONLY: "device-only",
    isAvailableAsync: async () => true,
    getItemAsync: async (key) => secureValues.get(key) ?? null,
    setItemAsync: async (key, value) => { secureValues.set(key, value); },
    deleteItemAsync: async (key) => { secureValues.delete(key); },
  };
  const service = load(path.resolve(__dirname, "../src/services/api.ts"), {
    "@readbuddy/api-client": runtimeClient,
    "expo-secure-store": secureStore,
    "../config/env": { API_BASE_URL: "http://localhost:8000" },
  }, runtimeGlobal);
  return { service, secureValues };
}

test("valid access token succeeds without refresh", async () => {
  let refreshCalls = 0;
  const api = client.createSimplificationClient({
    baseUrl: "http://localhost:8000",
    getAccessToken: () => "valid-access",
    refreshAccessToken: async () => { refreshCalls += 1; return "unexpected"; },
    fetch: async (_url, options) => {
      assert.equal(options.headers.Authorization, "Bearer valid-access");
      return new Response(JSON.stringify(result()), {
        headers: { "content-type": "application/json" },
      });
    },
  });
  await api.simplifyText(learnerId, { source_text: "Synthetic." });
  assert.equal(refreshCalls, 0);
});

test("expired concurrent vocabulary and feedback requests share refresh and retain rotation", async () => {
  let refreshCalls = 0;
  let forceSecondExpiry = false;
  const refreshBodies = [];
  const componentAuthorizations = [];
  const { service, secureValues } = loadMobileService(async (url, options) => {
    if (url.endsWith("/api/v1/auth/refresh")) {
      refreshCalls += 1;
      refreshBodies.push(JSON.parse(options.body));
      const suffix = refreshCalls === 1 ? "new" : "newer";
      return new Response(JSON.stringify({
        access_token: `access-${suffix}`,
        refresh_token: `refresh-${suffix}`,
        token_type: "bearer",
        expires_in: 300,
      }), { headers: { "content-type": "application/json" } });
    }

    const authorization = options.headers.Authorization;
    componentAuthorizations.push({ url, authorization });
    if (authorization === "Bearer access-old") return authenticationError();
    if (forceSecondExpiry && authorization === "Bearer access-new") {
      forceSecondExpiry = false;
      return authenticationError();
    }
    return new Response(JSON.stringify({ ok: true }), {
      headers: { "content-type": "application/json" },
    });
  });

  await service.setAuthSession({
    learnerId,
    accessToken: "access-old",
    refreshToken: "refresh-old",
    apiBaseUrl: "http://localhost:8000",
  });
  await Promise.all([
    service.simplificationClient.explainWord(learnerId, { term: "habitat" }),
    service.simplificationClient.submitReadingFeedback(
      learnerId, sessionId, { feedback_signal: "just_right" },
    ),
  ]);

  assert.equal(refreshCalls, 1);
  assert.deepEqual(refreshBodies[0], { refresh_token: "refresh-old" });
  assert.equal(service.getAuthSession().accessToken, "access-new");
  assert.equal(service.getAuthSession().refreshToken, "refresh-new");
  assert.ok(componentAuthorizations.some(({ url, authorization }) =>
    url.includes("/vocabulary/explain") && authorization === "Bearer access-new"));
  assert.ok(componentAuthorizations.some(({ url, authorization }) =>
    url.includes("/feedback") && authorization === "Bearer access-new"));

  const stored = JSON.parse([...secureValues.values()][0]);
  assert.equal(stored.refreshToken, "refresh-new");
  assert.equal("accessToken" in stored, false);

  await service.simplificationClient.submitReadingFeedback(
    learnerId, sessionId, { feedback_signal: "skipped" },
  );
  assert.equal(componentAuthorizations.at(-1).authorization, "Bearer access-new");
  assert.equal(refreshCalls, 1);

  forceSecondExpiry = true;
  await service.simplificationClient.simplifyText(learnerId, {
    source_text: "Synthetic.",
  });
  assert.equal(refreshCalls, 2);
  assert.deepEqual(refreshBodies[1], { refresh_token: "refresh-new" });
  assert.equal(service.getAuthSession().refreshToken, "refresh-newer");
  assert.equal(componentAuthorizations.at(-1).authorization, "Bearer access-newer");
});

test("stored refresh session survives reload without persisting access token", async () => {
  const secureValues = new Map();
  const first = loadMobileService(async () => {
    throw new Error("No request expected");
  }, secureValues).service;
  await first.setAuthSession({
    learnerId,
    accessToken: "memory-only-access",
    refreshToken: "persisted-refresh",
    apiBaseUrl: "http://localhost:8000",
  });

  const reloaded = loadMobileService(async () => {
    throw new Error("No request expected");
  }, secureValues).service;
  await reloaded.restoreAuthSession();
  assert.equal(reloaded.getAuthSession().accessToken, null);
  assert.equal(reloaded.getAuthSession().refreshToken, "persisted-refresh");
  assert.equal(reloaded.getAuthSession().learnerId, learnerId);
});

test("invalid refresh clears the session and asks for sign-in", async () => {
  let componentCalls = 0;
  let refreshCalls = 0;
  const { service, secureValues } = loadMobileService(async (url) => {
    if (url.endsWith("/api/v1/auth/refresh")) {
      refreshCalls += 1;
      return authenticationError();
    }
    componentCalls += 1;
    return authenticationError();
  });
  await service.setAuthSession({
    learnerId, accessToken: "expired", refreshToken: "invalid-refresh",
  });

  await assert.rejects(
    service.simplificationClient.explainWord(learnerId, { term: "habitat" }),
    (error) => error.status === 401,
  );
  assert.equal(refreshCalls, 1);
  assert.equal(componentCalls, 1);
  const cleared = service.getAuthSession();
  assert.equal(cleared.accessToken, null);
  assert.equal(cleared.refreshToken, null);
  assert.equal(cleared.learnerId, null);
  assert.equal(cleared.apiBaseUrl, null);
  assert.equal(secureValues.size, 0);
});

test("failed retry clears the session and never loops", async () => {
  let componentCalls = 0;
  let refreshCalls = 0;
  const { service } = loadMobileService(async (url) => {
    if (url.endsWith("/api/v1/auth/refresh")) {
      refreshCalls += 1;
      return new Response(JSON.stringify({
        access_token: "replacement-access",
        refresh_token: "replacement-refresh",
        token_type: "bearer",
        expires_in: 300,
      }), { headers: { "content-type": "application/json" } });
    }
    componentCalls += 1;
    return authenticationError();
  });
  await service.setAuthSession({
    learnerId, accessToken: "expired", refreshToken: "valid-refresh",
  });

  await assert.rejects(
    service.simplificationClient.submitReadingFeedback(
      learnerId, sessionId, { feedback_signal: "too_hard" },
    ),
    (error) => error.status === 401,
  );
  assert.equal(refreshCalls, 1);
  assert.equal(componentCalls, 2);
  assert.equal(service.getAuthSession().refreshToken, null);
});

test("unrelated 401 responses do not trigger token refresh", async () => {
  let refreshCalls = 0;
  const api = client.createSimplificationClient({
    baseUrl: "http://localhost:8000",
    getAccessToken: () => "current-access",
    refreshAccessToken: async () => { refreshCalls += 1; return "replacement"; },
    fetch: async () => new Response(JSON.stringify({
      error: { code: "invalid_credentials", message: "Invalid credentials" },
    }), { status: 401, headers: { "content-type": "application/json" } }),
  });
  await assert.rejects(
    api.simplifyText(learnerId, { source_text: "Synthetic." }),
    (error) => error.code === "invalid_credentials",
  );
  assert.equal(refreshCalls, 0);
});
