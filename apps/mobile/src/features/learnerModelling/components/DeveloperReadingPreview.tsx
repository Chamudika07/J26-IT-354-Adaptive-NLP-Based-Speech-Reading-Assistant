import { developerToolsEnabled } from "../preview/developerTools";
import type { ReactNode } from "react";
import { Pressable, Text, View } from "react-native";
import { ConnectedSessionGate } from "./ConnectedSessionPreview";
import { LocalPreviewLayout } from "./LocalPreviewLayout";
import { reportStyles, type LearnerReportProps } from "./LearnerReportLayout";
import { useDeveloperTest } from "../preview/DeveloperTestSession";
import type { LearnerDestination } from "../navigation/learnerDestinations";
import { eligibleTestSessions } from "../preview/developerSessions";

export function DeveloperTestControls({ onOpen }: { onOpen: () => void }) {
  const session = useDeveloperTest();
  if (!session || !__DEV__) return null;
  if (!developerToolsEnabled()) return <View style={{ paddingHorizontal: 16 }}>
    <Pressable accessibilityRole="button" onPress={onOpen} style={reportStyles.primaryAction}><Text style={reportStyles.primaryLabel}>Reading Session</Text></Pressable>
  </View>;
  return <View style={{ paddingHorizontal: 16 }}>
    <Pressable accessibilityRole="button" accessibilityLabel="Open Reading Session Test" onPress={onOpen} style={reportStyles.previewLink}><Text style={reportStyles.body}>Try a Reading Session (demo)</Text></Pressable>
    {session.connected.attempted ? <Text style={reportStyles.body}>Demo Reading Journey selected. Sample results stay together across screens. Saved AI reports and temporary choices remain separate.</Text> : null}
    {session.selected ? <Text style={reportStyles.body}>Custom sample inputs selected. Calculations still need a computer; saved reports remain separate.</Text> : null}
  </View>;
}
function LocalDeveloperReadingGate({ destination, days, children }: { destination: string; days: number; children: ReactNode }) {
  const session = useDeveloperTest();
  if (!session?.selected || !__DEV__ || !["home", "progress", "suggestions", "profile", "report"].includes(destination)) return <>{children}</>;
  const records = eligibleTestSessions(session.records, days, session.asOf);
  return <LocalPreviewLayout title={destination === "home" ? "Developer Home Dashboard" : destination === "progress" ? "Developer Progress Analytics" : destination === "profile" ? "Sample profile - calculation pending" : destination === "report" ? "Sample report - calculation pending" : "Developer recommendations unavailable"}
    disclosure="Sample Data"
    introduction="Saved custom inputs only. Backend calculations are pending export/import. This view does not use unrelated dashboard or report fixtures.">
    <View style={reportStyles.card}>
      <Text style={reportStyles.body}>{days}-day window: {new Date(session.asOf-days*86400000).toLocaleDateString("en-GB", { timeZone: "UTC" })} to {new Date(session.asOf).toLocaleDateString("en-GB", { timeZone: "UTC" })} (UTC, end exclusive). Based on load/save time.</Text>
      <Text accessibilityLiveRegion="polite" style={reportStyles.body}>{session.message}</Text>
      <Text style={reportStyles.heading}>{records.length} saved sample inputs in this time window</Text>
      <Text style={reportStyles.body}>Recommendations unavailable: these manual test records have not passed the backend recommendation evidence pipeline. No settings are applied. Saved AI reports remain unchanged.</Text>
    </View>
    {destination !== "suggestions" ? records.map((record) => {
      return <View key={record.id} style={reportStyles.card}>
        <Text style={reportStyles.heading}>Saved sample input</Text>
        <Text style={reportStyles.body}>Context: {record.task.replaceAll("_", " ")} / {record.tier} / {record.mode.replaceAll("_", " ")}</Text>
        <Text style={reportStyles.body}>Words attempted: {record.attempted}. Words correct: {record.correct}. Active reading: {record.activeMs} ms.</Text>
        <Text style={reportStyles.body}>Analytics pending offline backend calculation. Export, calculate on computer, reload, then select the result.</Text>
        <Text style={reportStyles.body}>Completion: {record.completion}. Pauses: {record.pauseCount ?? "Missing"}. Total pause duration: {record.pauseMs === null ? "Missing" : `${record.pauseMs} ms`}. Replays: {record.replayCount ?? "Missing"}.</Text>
      </View>;
    }) : null}
    <Pressable accessibilityRole="button" onPress={session.returnToDemo} style={reportStyles.previewLink}><Text style={reportStyles.body}>Return to dashboard demo</Text></Pressable>
  </LocalPreviewLayout>;
}

export function DeveloperReadingGate(props: { destination: string; days: number; children: ReactNode; onNavigate?: (destination: LearnerDestination) => void; reportProps?: LearnerReportProps }) {
  return <ConnectedSessionGate destination={props.destination} onNavigate={props.onNavigate} reportProps={props.reportProps}><LocalDeveloperReadingGate {...props} /></ConnectedSessionGate>;
}
