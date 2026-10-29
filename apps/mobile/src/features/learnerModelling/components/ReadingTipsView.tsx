import { useState, type ReactNode } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { palette, radii } from "../theme";
import { ReadingBuddyIllustration } from "./ReadingBuddyIllustration";

export interface TipEvidenceMetric { label: string; value: string; evidence?: string; explanation?: string; observations?: string }
/** Presentation only: decision reasons and evidence come from the selected source. */
export function ReadingTipsView({ disclosure, title, metrics, reasons, nextSteps, reasonCodes = [], evidenceState, current, limitations = [], unavailableReason, onReport, developerAction, periodLabel, currentLabel = "Current support" }: {
  disclosure: string; title: string; metrics: readonly TipEvidenceMetric[]; reasons: readonly string[];
  nextSteps: readonly string[]; reasonCodes?: readonly string[]; evidenceState?: string;
  current?: string; limitations?: readonly string[]; unavailableReason?: string; onReport?: () => void; developerAction?: ReactNode; periodLabel?: string; currentLabel?: string;
}) {
  const [details, setDetails] = useState(false);
  const uniqueReasons = [...new Set(reasons)];
  return <ScrollView style={styles.scroll} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
    <View style={styles.header}>
      <Text accessibilityRole="header" style={[styles.title, styles.headerTitle]}>My Reading Tips</Text>
      <View testID="tips-reading-illustration" pointerEvents="none" accessible={false} accessibilityElementsHidden importantForAccessibility="no-hide-descendants" style={styles.illustration}><ReadingBuddyIllustration compact /></View>
    </View>
    <Text style={styles.disclosure}>{disclosure}</Text>
    {developerAction}
    <View style={styles.recommendation}>
      <Text style={styles.advisory}>ADVISORY ONLY</Text>
      <View style={styles.sectionHeading}><TipPicture symbol={"\uD83D\uDCA1"} background="#EEF5FF" /><Text accessibilityRole="header" style={[styles.recommendationTitle, styles.headingText]}>{title}</Text></View>
      <Text style={styles.body}>No settings or reading level were changed automatically.</Text>
    </View>
    <View style={styles.card}>
      <Text accessibilityRole="header" style={styles.heading}>Reading evidence</Text>
      <View style={styles.metrics}>
        {metrics.map(metric => <View key={metric.label} testID={`tip-${metric.label}`} style={styles.metric}>
          <Text style={styles.value}>{metric.value}</Text><Text style={styles.metricLabel}>{metric.label}</Text>
        </View>)}
      </View>
    </View>
    <View style={styles.card}>
      <View style={styles.sectionHeading}><TipPicture symbol={"\uD83D\uDD0D"} background="#F4EFFF" /><Text accessibilityRole="header" style={[styles.heading, styles.headingText]}>Why this recommendation?</Text></View>
      {unavailableReason ? <Text style={styles.body}>{unavailableReason}</Text> : null}
      {uniqueReasons.length ? uniqueReasons.map((reason, index) => <View key={reason} style={styles.reason}>
        <Text accessible={false} style={styles.reasonNumber}>{index + 1}</Text><Text style={[styles.body, { flex: 1 }]}>{reason}</Text>
      </View>) : <Text style={styles.body}>Decision explanation unavailable.</Text>}
      <Pressable accessibilityRole="button" accessibilityLabel="Why This Tip?" accessibilityState={{ expanded: details }} onPress={() => setDetails(!details)} style={styles.secondary}>
        <Text style={styles.actionText}>{details ? "Hide evidence details" : "See evidence details"}</Text>
      </Pressable>
      {details ? <View style={styles.details}>
        <Text style={styles.body}>Exact rule conditions: Unavailable.</Text>
        <Text style={styles.body}>Decision evidence: {evidenceState ?? "Unavailable"}</Text>
        {evidenceState ? <Text style={styles.disclosure}>Evidence status is not a confidence score.</Text> : null}
        {periodLabel ? <Text style={styles.body}>{periodLabel}</Text> : null}
        {current ? <Text style={styles.body}>{currentLabel}: {current}</Text> : null}
        {reasonCodes.map(code => <Text key={code} style={styles.body}>Reason code: {code}</Text>)}
        {metrics.filter(metric => metric.evidence || metric.explanation || metric.observations).map(metric => <View key={metric.label} testID={`tip-evidence-${metric.label}`} style={styles.details}>
          <Text style={styles.heading}>{metric.label}</Text>
          {metric.observations ? <Text style={styles.body}>{metric.observations}</Text> : null}
          {metric.evidence ? <Text style={styles.body}>Progress evidence: {metric.evidence}</Text> : null}
          {metric.explanation ? <Text style={styles.body}>{metric.explanation}</Text> : null}
        </View>)}
        {[...new Set(limitations)].map(text => <Text key={text} style={styles.body}>{text}</Text>)}
      </View> : null}
    </View>
    <View style={styles.card}>
      <View style={styles.sectionHeading}><TipPicture symbol={"\uD83D\uDCD6"} background="#EAFBF1" /><Text accessibilityRole="header" style={[styles.heading, styles.headingText]}>What should I do next?</Text></View>
      {nextSteps.map(text => <Text key={text} style={styles.body}>{text}</Text>)}
      {onReport ? <Pressable accessibilityRole="button" onPress={onReport} style={styles.primary}><Text style={styles.primaryText}>Next: My Reading Report</Text></Pressable> : null}
    </View>
  </ScrollView>;
}
function TipPicture({ symbol, background }: { symbol: string; background: string }) {
  return <View testID="tips-pictorial-icon" pointerEvents="none" accessible={false} accessibilityElementsHidden importantForAccessibility="no-hide-descendants" style={[styles.iconBadge, { backgroundColor: background }]}><Text allowFontScaling={false} style={styles.icon}>{symbol}</Text></View>;
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 8 },
  headerTitle: { flexGrow: 1, flexShrink: 1, flexBasis: 180 },
  illustration: { width: 94, height: 84 },
  sectionHeading: { flexDirection: "row", alignItems: "center", gap: 8 },
  headingText: { flex: 1 },
  iconBadge: { width: 32, height: 32, borderRadius: 10, alignItems: "center", justifyContent: "center" },
  icon: { fontSize: 20, lineHeight: 26 },
  scroll: { backgroundColor: palette.paper }, content: { paddingHorizontal: 16, paddingTop: 8, paddingBottom: 96, gap: 12 },
  title: { fontSize: 22, color: palette.primaryDark, fontWeight: "900" }, disclosure: { fontSize: 12, lineHeight: 18, color: palette.muted },
  card: { padding: 12, gap: 10, borderRadius: radii.medium, backgroundColor: palette.surface },
  recommendation: { padding: 14, gap: 8, borderRadius: radii.medium, backgroundColor: palette.tealSoft },
  advisory: { color: palette.primaryDark, fontSize: 12, fontWeight: "800" }, recommendationTitle: { color: palette.primaryDark, fontSize: 22, fontWeight: "900" },
  heading: { color: palette.primaryDark, fontSize: 17, fontWeight: "800" }, body: { color: palette.ink, fontSize: 15, lineHeight: 22 },
  metrics: { flexDirection: "row", flexWrap: "wrap", gap: 6 }, metric: { flexGrow: 1, flexBasis: 110, minWidth: 110, padding: 10, gap: 6, backgroundColor: palette.primarySoft, borderRadius: radii.small },
  value: { color: palette.primaryDark, fontWeight: "900", fontSize: 22 }, metricLabel: { color: palette.ink, fontSize: 12, lineHeight: 18 },
  reason: { flexDirection: "row", gap: 10 }, reasonNumber: { fontSize: 15, fontWeight: "800", color: palette.primaryDark, paddingTop: 2 }, details: { gap: 8 },
  secondary: { minHeight: 44, justifyContent: "center", alignItems: "center", padding: 10, backgroundColor: palette.primarySoft, borderRadius: radii.small }, actionText: { color: palette.primaryDark, fontWeight: "700", fontSize: 14 },
  primary: { minHeight: 48, padding: 12, alignItems: "center", justifyContent: "center", backgroundColor: palette.primary, borderRadius: radii.small }, primaryText: { color: palette.surface, fontSize: 16, fontWeight: "800" },
});
