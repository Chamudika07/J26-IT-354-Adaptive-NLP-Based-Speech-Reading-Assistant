import { BrowserReportError } from "../export/browserAiPdf";
import { useLayoutEffect, useRef, useState } from "react";
import { Platform, Pressable, Text, View } from "react-native";
import { buildEducatorReport, exportEducatorReport, type EducatorReportSelection } from "../export/educatorReports";
import { reportStyles as s } from "./LearnerReportLayout";

export function EducatorReportButton({ selection, unavailable = false }: { selection: EducatorReportSelection; unavailable?: boolean }) {
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState({ revision: "", text: "" });
  const running = useRef(false);
  const revision = JSON.stringify(selection);
  const generation = useRef(0);
  const mounted = useRef(false);
  useLayoutEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useLayoutEffect(() => { generation.current += 1; }, [revision]);
  const message = notice.revision === revision ? notice.text : "";
  const native = Platform.OS === "ios" || Platform.OS === "android";
  const web = Platform.OS === "web";
  let validWebReport = false;
  if (web) { try { buildEducatorReport(selection); validWebReport = true; } catch { /* Invalid or unavailable selections fail closed. */ } }
  const disabled = unavailable || busy || (!native && !web) || (web && !validWebReport) || !__DEV__ || !selection.development || !selection.demoMode || selection.role !== "educator";
  const label = web ? selection.student === null ? "Print / Save Class Report as PDF" : "Print / Save Student Report as PDF" : selection.student === null ? "Download Class Analytics Report" : "Download Student Analytics Report";
  async function download() {
    if (disabled || running.current) return;
    running.current = true; setBusy(true); setNotice({ revision, text: "" });
    const token = generation.current;
    const isCurrent = () => mounted.current && generation.current === token;
    try {
      await exportEducatorReport({ selection, platform: Platform.OS, isCurrent });
      if (isCurrent()) setNotice({ revision, text: web ? "Report opened. Select Print / Save as PDF, then choose Save as PDF in the browser dialog. No saved copy is confirmed." : "Share sheet closed. Choose Save to Files or a sharing app to keep a copy; saving is not confirmed here." });
    } catch (error) {
      if (isCurrent()) setNotice({ revision, text: web ? error instanceof BrowserReportError && error.reason === "popup" ? "Your browser blocked the report window. Allow popups for ReadBuddy and try again." : selection.student === null ? "Could not open the class report. Please try again. No saved copy is confirmed." : "Could not open the student report. Please try again. No saved copy is confirmed." : "Could not share this PDF. Please try again. No saved copy is confirmed." });
    } finally {
      running.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  return <View style={{ gap: 6 }}>
    <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ disabled, busy }} disabled={disabled} onPress={download} style={[s.primaryAction, selection.student === null && { backgroundColor: "#1D4ED8", borderRadius: 18, flexDirection: "row", gap: 8, minHeight: 48 }, { opacity: disabled ? 0.6 : 1 }]}>{selection.student === null ? <View pointerEvents="none" accessible={false} accessibilityElementsHidden importantForAccessibility="no-hide-descendants"><Text allowFontScaling={false} style={{ fontSize: 20 }}>{"\uD83D\uDCC4"}</Text></View> : null}<Text style={[s.primaryLabel, { flexShrink: 1, textAlign: "center" }]}>{busy ? "Preparing PDF…" : label}</Text></Pressable>
    {unavailable || (web && !validWebReport) ? <Text style={s.body}>Reading results are unavailable for this report.</Text> : !native && !web ? <Text style={s.body}>Open the iPhone or Android app to share a PDF.</Text> : null}
    {web && validWebReport ? <Text style={s.body}>Choose Save as PDF in the browser print dialog. This is a descriptive analytics report, not AI-generated.</Text> : null}
    {message ? <Text accessibilityRole="alert" style={s.body}>{message}</Text> : null}
  </View>;
}
