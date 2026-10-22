import { ConnectedLearnerJourney } from "./ConnectedLearnerJourney";
import type { LearnerReportProps } from "./LearnerReportLayout";
import { developerToolsEnabled } from "../preview/developerTools";
import { useState, type ReactNode } from "react";
import { Pressable, Text, View } from "react-native";
import { ReadingProgress } from "./ReadingProgress";
import { HomeHero } from "./HomeHero";
import { MetricChart } from "./MetricChart";
import { LocalPreviewLayout } from "./LocalPreviewLayout";
import { DemoLearnerCard, DemoPreferencesCard } from "./DemoLearnerCard";
import { reportStyles } from "./LearnerReportLayout";
import type { LearnerDestination } from "../navigation/learnerDestinations";
import { palette } from "../theme";
import { useDeveloperTest } from "../preview/DeveloperTestSession";

export function ConnectedSessionGate({ destination, children, onNavigate, reportProps }: { destination: string; children: ReactNode; onNavigate?: (destination: LearnerDestination) => void; reportProps?: LearnerReportProps }) {
  const [details, setDetails] = useState(false);
  const [evidence, setEvidence] = useState(false);
  const [summary, setSummary] = useState(false);
  const [savedReport, setSavedReport] = useState(false);
  const session = useDeveloperTest();
  if (!__DEV__ || !session?.connected.attempted || !["home", "progress", "suggestions", "profile", "report"].includes(destination)) return <>{children}</>;
  const artifact = session.connected.artifact;
  if (artifact && !developerToolsEnabled()) return <ConnectedLearnerJourney artifact={artifact} destination={destination} onNavigate={onNavigate} reportProps={reportProps} />;
  if (destination === "report" && savedReport) return <View style={{ flex: 1 }}>
    <Text style={reportStyles.body}>This saved AI report is separate from your current reading journey.</Text>
    <Pressable accessibilityRole="button" onPress={() => setSavedReport(false)} style={reportStyles.previewLink}><Text style={reportStyles.body}>Back to Reading Summary</Text></Pressable>
    {children}
  </View>;
  if (destination === "progress" && artifact) {
    const number = (v: string | null | undefined, scale = 1) => v == null ? null : Number(v) * scale;
    const rows = artifact.history.map(item => ({ label: `S${item.sequence}`, accuracy: number(item.accuracy, 100), speed: number(item.wpm), hesitation: number(item.hesitation, 100) }));
    const metric = (key: string, scale = 1) => number(artifact.metrics.find(m => m.metric_name === key)?.latest_value, scale);
    return <ReadingProgress insufficientHistory={artifact.metrics.some(m => m.change_direction === "insufficient_evidence")} completedCount={artifact.includedSessionCount} engagement={artifact.history.at(-1)?.experimentalEngagement} rows={rows} latest={{ label: "Latest", accuracy: metric("reading_accuracy", 100), speed: metric("reading_fluency_wpm"), hesitation: metric("hesitation_rate_per_word", 100) }}
      period={`${session.replayIndex === null ? "Imported sample results" : "Applied scenario: Sample " + session.replayIndex} - ${artifact.includedSessionCount} completed sample sessions - ${artifact.reportingStartUtc.slice(0, 10)} to ${artifact.reportingEndUtc.slice(0, 10)} (end not included)`}
      onTips={onNavigate ? () => onNavigate("suggestions") : undefined}
      details={["History shows completed sessions only. Reading time, pause totals and replays are not provided in these results.", ...artifact.metrics.map(m => m.explanation), artifact.disclaimer, `Reading activity indicator: ${artifact.history.at(-1)?.experimentalEngagement ?? "Not measured"}. Unvalidated research estimate; not attention or ability.`, "Missing measurements are not zero. These results use only the selected sample sessions."]}
      actions={<>
        {developerToolsEnabled() ? <View style={reportStyles.card}><Pressable accessibilityRole="button" onPress={() => setDetails(!details)} style={reportStyles.previewLink}><Text style={reportStyles.body}>Developer Details</Text></Pressable>{details ? <><Text style={reportStyles.body}>Generated: {artifact.generatedAt}</Text><Text style={reportStyles.body}>Reporting period: {artifact.reportingStartUtc} to {artifact.reportingEndUtc} (UTC, end exclusive).</Text></> : null}</View> : null}
        {session.replayIndex !== null ? <View style={reportStyles.card}>
          <Text style={reportStyles.body}>{artifact.includedSessionCount} completed sample sessions</Text>
          <Pressable accessibilityRole="button" disabled={session.replayIndex + 1 >= session.replayLength} accessibilityState={{ disabled: session.replayIndex + 1 >= session.replayLength }} onPress={() => session.replay(session.replayIndex! + 1)} style={[reportStyles.primaryAction, session.replayIndex + 1 >= session.replayLength && { opacity: 0.5 }]}><Text style={reportStyles.primaryLabel}>Add Next Sample</Text></Pressable>
          <Pressable accessibilityRole="button" onPress={() => session.replay(0)} style={reportStyles.previewLink}><Text style={reportStyles.body}>Reset Journey</Text></Pressable>
        </View> : null}
        {onNavigate ? <Pressable accessibilityRole="button" onPress={() => onNavigate("report")} style={reportStyles.previewLink}><Text style={reportStyles.body}>Go to: Report</Text></Pressable> : null}
        <Pressable accessibilityRole="button" onPress={session.returnToDemo} style={reportStyles.previewLink}><Text style={reportStyles.body}>Back to Reading Home</Text></Pressable>
      </>} />;
  }
  const date = (value: string) => new Date(value).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
  const titles: Record<string, string> = { home: "Your Reading Journey", progress: "Your Sample Progress", suggestions: "Reading Tips", profile: "My Profile", report: "My Reading Report" };
  const display = (value: string | null, unit: string) => value === null ? "Unavailable" : unit === "proportion" ? `${Number((Number(value)*100).toFixed(2))}%` : unit === "words_per_minute" ? `${Number(value)} words/minute` : `${Number((Number(value) * 100).toFixed(2))} hesitations per 100 attempted words`;
  const suggestionCard = artifact ? (
<View testID="connected-suggestion" style={reportStyles.card}>
        <Text accessibilityRole="header" style={reportStyles.heading}>Your next step</Text>
        <Text style={reportStyles.period}>ADVISORY ONLY</Text>

        <Text style={reportStyles.body}>Current sample support: {artifact.recommendation?.current ?? artifact.context.tier + " / " + artifact.context.mode}</Text>
        <Text style={reportStyles.heading}>{artifact.recommendation?.action ?? "Recommendation unavailable"}</Text>
        {artifact.recommendation ? <>
          <Text style={reportStyles.body}>{artifact.recommendation.manual_control_prevents_adjustment ? "Manual control keeps your support unchanged." : "This idea uses the selected reading results. Open Why This Tip? to see the evidence."}</Text>
          <Text style={reportStyles.body}>Proposed changes: {artifact.recommendation.proposed.join(" ") || "None proposed."}</Text>
          {developerToolsEnabled() && details ? <Text style={reportStyles.body}>Fixed baseline: {String(artifact.recommendation.fixed_baseline)}. Manual override: {String(artifact.recommendation.manual_override_active)}. Global lock: {String(artifact.recommendation.global_lock)}. Manual control prevents adjustment: {String(artifact.recommendation.manual_control_prevents_adjustment)}.</Text> : null}
          <Text style={reportStyles.body}>{artifact.recommendation.manual_control_prevents_adjustment ? "Your sample support is protected by manual control. Suggestions cannot change it." : "Suggestions are for review only. They never change support automatically."}</Text>
          {artifact.recommendation.limitations.map((text) => <Text key={text} style={reportStyles.body}>{text}</Text>)}
        </> : null}
        <Text style={reportStyles.body}>{artifact.recommendation ? "Review this reading idea with a parent or teacher. It uses these sample sessions, not a measure of your ability." : "A suggestion is not available for these samples yet. Keep reading to discover more about your progress."}</Text>
        <Pressable accessibilityRole="button" accessibilityState={{ expanded: evidence }} onPress={() => setEvidence(!evidence)} style={reportStyles.previewLink}><Text style={reportStyles.body}>{evidence ? "Hide suggestion evidence" : "Why This Tip?"}</Text></Pressable>
        {evidence ? <>
        {artifact.recommendationExplanation.map((text) => <Text key={text} style={reportStyles.body}>{text}</Text>)}
        </> : null}
        <Text style={reportStyles.body}>No reading support was changed.</Text>
        <Text style={reportStyles.body}>{artifact.disclaimer}</Text>
      </View>
  ) : null;
  const homeAccuracy = artifact?.metrics.find((m) => m.metric_name === "reading_accuracy");
  const homeSpeed = artifact?.metrics.find((m) => m.metric_name === "reading_fluency_wpm");
  return <LocalPreviewLayout homeHeader={destination === "home" && artifact ? <HomeHero sessions={artifact.includedSessionCount}
    accuracy={homeAccuracy?.latest_value == null ? "Unavailable" : `${Number((Number(homeAccuracy.latest_value) * 100).toFixed(2))}%`}
    speed={homeSpeed?.latest_value == null ? "Unavailable" : String(Number(homeSpeed.latest_value))}
    onStart={() => onNavigate?.("test")} /> : undefined} title={titles[destination]!} disclosure="Sample Data"
    introduction="Explore your selected reading results. Tips never change your settings.">
    {!artifact ? <Text accessibilityRole="alert" style={reportStyles.body}>These reading results could not be opened. Please return Home and try again. No other results have been substituted.</Text> : <>
      <View style={reportStyles.card}>
        <Text accessibilityLiveRegion="polite" style={reportStyles.period}>{session.replayIndex === null ? "Applied: imported sample results" : `Applied scenario: Sample ${session.replayIndex}`}</Text>
        <Text style={reportStyles.body}>{artifact.includedSessionCount} completed sample sessions. All results below use this selection.</Text>
        {artifact.history.at(-1)?.experimentalEngagement != null ? <>
          <Text style={reportStyles.body}>Reading activity indicator: {artifact.history.at(-1)!.experimentalEngagement}</Text>
          <Text style={reportStyles.body}>An unvalidated research estimate, not a measure of attention or ability.</Text>
        </> : <Text style={reportStyles.body}>Reading activity indicator: not enough measurements yet.</Text>}
      </View>
      {destination === "suggestions" ? suggestionCard : null}
      {destination === "home" && onNavigate ? <Pressable accessibilityRole="button" onPress={() => onNavigate("profile")} style={reportStyles.primaryAction}><Text style={reportStyles.primaryLabel}>View Learner Profile</Text></Pressable> : null}
      {destination === "profile" ? <DemoLearnerCard editable /> : null}
      {destination === "profile" ? <>
        <DemoPreferencesCard />
        <View style={reportStyles.card}>
          <Text accessibilityRole="header" style={reportStyles.heading}>Reading activity</Text>
          <Text style={reportStyles.body}>{artifact.includedSessionCount} completed sample sessions.</Text>
          <Text style={reportStyles.body}>Reading time, pause totals and replays are not provided in these results.</Text>
        </View>
        {onNavigate ? <Pressable accessibilityRole="button" onPress={() => onNavigate("settings")} style={reportStyles.primaryAction}><Text style={reportStyles.primaryLabel}>Choose your reading settings.</Text></Pressable> : null}
        <View style={reportStyles.card}>
          <Text accessibilityRole="header" style={reportStyles.heading}>Reading activity</Text>
          <Text style={reportStyles.body}>Demonstrated difficulty: {artifact.context.tier}. Support context: {artifact.context.mode.replaceAll("_", " ")}.</Text>
          <Text style={reportStyles.body}>These examples are not a reading age or diagnosis. Your profile name is separate.</Text>
        </View>
      </> : null}
      <View style={reportStyles.card}>
        {destination !== "home" ? <Text style={reportStyles.heading}>Reading Results</Text> : null}
        {destination !== "home" ? <Text style={reportStyles.body}>{session.replayIndex === null ? "Selected sample results" : "Explore one sample session at a time."}</Text> : null}
        <Text style={reportStyles.body}>Period: {date(artifact.reportingStartUtc)} to {date(artifact.reportingEndUtc)}.</Text>
        {destination !== "home" ? <Text style={reportStyles.body}>Reading: {artifact.context.task.replaceAll("_", " ")} / {artifact.context.tier} / {artifact.context.mode.replaceAll("_", " ")}</Text> : null}
        {developerToolsEnabled() ? <Pressable accessibilityRole="button" accessibilityState={{ expanded: details }} onPress={() => setDetails(!details)} style={reportStyles.previewLink}><Text style={reportStyles.body}>{details ? "Hide Developer Details" : "Developer Details"}</Text></Pressable> : null}
        {developerToolsEnabled() && details ? <>
          <Text style={reportStyles.body}>Source: {artifact.source}</Text>
          <Text style={reportStyles.body}>Generated: {artifact.generatedAt}</Text>
          <Text style={reportStyles.body}>Reporting period: {artifact.reportingStartUtc} to {artifact.reportingEndUtc} (UTC, end exclusive).</Text>
          <Text style={reportStyles.body}>Source digest: {artifact.sourceDigest}</Text>
        </> : null}
        <Text style={reportStyles.body}>{artifact.includedSessionCount} eligible completed sessions; {artifact.excludedSessionCount} excluded (outside period/context or incomplete).</Text>
        {destination !== "home" ? <Text style={reportStyles.body}>Support shown here belongs to this sample, not your learner profile.</Text> : null}
        {developerToolsEnabled() && details ? <Text style={reportStyles.body}>These sample results use the period shown above. Custom form inputs and dashboard filters do not update them.</Text> : null}
        <Text style={reportStyles.body}>The saved Qwen3 AI report is independent and is not derived from these sessions.</Text>
      </View>
      {destination === "home" && homeAccuracy?.first_value != null && homeAccuracy.latest_value != null ? <MetricChart collapsibleDetails metric={{ key: "reading_accuracy", label: "Reading progress", unit: "%", firstValue: Number(homeAccuracy.first_value) * 100, latestValue: Number(homeAccuracy.latest_value) * 100, changeDirection: homeAccuracy.change_direction as "increased" | "decreased" | "no_observed_change" | "insufficient_evidence", evidenceLabel: homeAccuracy.evidence_state, explanation: homeAccuracy.explanation }} /> : null}
      <View style={reportStyles.card}>
        <Text style={reportStyles.heading}>Your reading results</Text>
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 12 }}>
        {artifact.metrics.length === 0 ? <Text style={reportStyles.body}>Measurements unavailable: no eligible completed sessions.</Text> : artifact.metrics.map((metric, index) => <View key={metric.metric_name} style={{ flexGrow: 1, flexBasis: 170, borderLeftWidth: 4, borderLeftColor: [palette.primary, palette.teal, palette.orange][index % 3], padding: 12, gap: 8, borderRadius: 12, backgroundColor: palette.paper }}>
          <Text style={reportStyles.heading}>{metric.display_label}</Text>
          <Text style={reportStyles.period}>Latest sample result</Text>
          <Text style={[reportStyles.heading, { fontSize: 24 }]}>{display(metric.latest_value, metric.unit)}</Text>
          <Text style={reportStyles.body}>First sample: {display(metric.first_value, metric.unit)}.</Text>
          <Text style={reportStyles.body}>{metric.explanation}{details ? ` Evidence state: ${metric.evidence_state}.` : ""}</Text>
        </View>)}
        </View>
      </View>
      {destination === "progress" || destination === "profile" ? <View style={reportStyles.card}>
        <Text style={reportStyles.heading}>Your sample session history</Text>
        {artifact.history.length === 0 ? <Text style={reportStyles.body}>No eligible completed sample sessions.</Text> : artifact.history.map((item) => <View key={item.sequence}>
          <Text style={reportStyles.heading}>Sample {item.sequence} - {date(item.recordedAt)}</Text>
          <Text style={reportStyles.body}>Accuracy: {display(item.accuracy, "proportion")}. Reading pace: {display(item.wpm, "words_per_minute")}. Hesitation: {display(item.hesitation, "hesitations_per_attempted_word")}.</Text>
          {developerToolsEnabled() && details ? <Text style={reportStyles.body}>Developer-only experimental engagement: {item.experimentalEngagement ?? "Unavailable"}. Unvalidated research heuristic; not attention, ability, health or learning effectiveness.</Text> : null}
        </View>)}
      </View> : null}
      {destination === "progress" ? <View style={reportStyles.card}>
        <Text accessibilityRole="header" style={reportStyles.heading}>Reading behaviour research preview</Text>
        <Text style={reportStyles.body}>Latest experimental engagement: {artifact.history.at(-1)?.experimentalEngagement ?? "Unavailable"}.</Text>
        <Text style={reportStyles.body}>Unvalidated research heuristic from the prepared samples. It does not measure attention, ability or learning effectiveness. Missing evidence stays unavailable.</Text>
      </View> : null}
      {destination === "report" ? <View style={reportStyles.card}>
        <Text style={reportStyles.heading}>Reading Progress Summary</Text>
        <Text style={reportStyles.body}>This summary uses the same selected sample sessions as your reading results. It is not AI-generated and has no PDF export.</Text>
        <Pressable accessibilityRole="button" accessibilityState={{ expanded: summary }} onPress={() => setSummary(!summary)} style={reportStyles.previewLink}><Text style={reportStyles.body}>{summary ? "Close reading summary" : "Read reading summary"}</Text></Pressable>
        {summary || (developerToolsEnabled() && details) ? artifact.reportStatements.map((text) => <Text key={text} style={reportStyles.body}>{text}</Text>) : <Text style={reportStyles.body}>Choose Read reading summary to explore the available facts.</Text>}
        <Pressable accessibilityRole="button" onPress={() => setSavedReport(true)} style={reportStyles.previewLink}><Text style={reportStyles.body}>Open Saved AI Report</Text></Pressable>
      </View> : null}
      {destination !== "suggestions" ? suggestionCard : null}
    </>}
    {session.replayIndex !== null ? <View style={reportStyles.card}>
      <Text accessibilityLiveRegion="polite" style={reportStyles.heading}>{artifact?.includedSessionCount ?? 0} completed sample sessions</Text>
      <Text style={reportStyles.body}>{session.replayIndex + 1 >= session.replayLength ? "Journey complete! Explore your results or reset to begin again." : session.replayIndex === 0 ? "Ready to begin? Add your first sample session." : "Keep exploring: add the next sample session."}</Text>
      <Pressable accessibilityRole="button" disabled={session.replayIndex + 1 >= session.replayLength} accessibilityState={{ disabled: session.replayIndex + 1 >= session.replayLength }} onPress={() => session.replay(session.replayIndex! + 1)} style={[reportStyles.primaryAction, session.replayIndex + 1 >= session.replayLength && { opacity: 0.5 }]}><Text style={reportStyles.primaryLabel}>Add Next Sample</Text></Pressable>
      <Pressable accessibilityRole="button" onPress={() => session.replay(0)} style={reportStyles.previewLink}><Text style={reportStyles.body}>Reset Journey</Text></Pressable>
    </View> : null}
    {onNavigate ? <View style={reportStyles.card}>{([["test", "Reading Results"], ["home", "Analytics"], ["profile", "Learner Profile"], ["progress", "Analytics"], ["suggestions", "Suggestions"], ["report", "Report"]] as const).map(([target, label]) => <Pressable key={target} accessibilityRole="button" onPress={() => onNavigate(target)} style={reportStyles.previewLink}><Text style={reportStyles.body}>{({ home: "progress", progress: "suggestions", suggestions: "report", profile: "progress", report: "test" } as Record<string, string>)[destination] === target ? "Next" : "Go to"}: {label}</Text></Pressable>)}</View> : null}
    {onNavigate ? <View style={reportStyles.card}>
      <Text style={reportStyles.heading}>Your choices</Text>
      <Text style={reportStyles.body}>Your choices do not change the sample results.</Text>
      <Pressable accessibilityRole="button" onPress={() => onNavigate("settings")} style={reportStyles.previewLink}><Text style={reportStyles.body}>Reading Settings</Text></Pressable>
      <Pressable accessibilityRole="button" onPress={() => onNavigate("feedback")} style={reportStyles.previewLink}><Text style={reportStyles.body}>Reading Feedback</Text></Pressable>
    </View> : null}
    {developerToolsEnabled() ? <Pressable accessibilityRole="button" disabled={session.busy} onPress={() => void session.run("clear")} style={reportStyles.previewLink}><Text style={reportStyles.body}>Reset connected demo</Text></Pressable> : null}
    <Pressable accessibilityRole="button" onPress={session.returnToDemo} style={reportStyles.previewLink}><Text style={reportStyles.body}>Back to Reading Home</Text></Pressable>
  </LocalPreviewLayout>;
}
