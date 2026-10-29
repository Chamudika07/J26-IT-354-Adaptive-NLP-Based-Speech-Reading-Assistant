import { BrowserReportError } from "../export/browserAiPdf";
import { useLayoutEffect, useRef, useState } from "react";
import { Platform, Pressable, Text, View } from "react-native";
import { buildGuardianWebReport, exportGuardianReport, type GuardianWebSelection, type GuardianReportData } from "../export/guardianReport";
import { reportStyles as s } from "./LearnerReportLayout";
export function GuardianReportButton({ data, selection }: { data: GuardianReportData; selection?: GuardianWebSelection }) {
  const [busy, setBusy] = useState(false); const [notice, setNotice] = useState({ revision: "", text: "" });
  const running = useRef(false); const mounted = useRef(false); const generation = useRef(0); const revision = JSON.stringify({ data, selection });
  useLayoutEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useLayoutEffect(() => { generation.current += 1; }, [revision]);
  const native = Platform.OS === "ios" || Platform.OS === "android";
  const web = Platform.OS === "web";
  let validWeb = false;
  if (web) { try { buildGuardianWebReport(data, selection); validWeb = true; } catch { /* Fail closed. */ } }
  const disabled = busy || (!native && !web) || (web && !validWeb) || !__DEV__;
  const label = web ? "Print / Save Guardian Report as PDF" : "Download Progress Report";
  async function download() {
    if (disabled || running.current) return;
    running.current = true; setBusy(true); setNotice({ revision, text: "" });
    const token = generation.current; const isCurrent = () => mounted.current && generation.current === token;
    try { await exportGuardianReport({ data, platform: Platform.OS, isCurrent, selection });
      if (isCurrent()) setNotice({ revision, text: web ? "Report opened. Select Print / Save as PDF, then choose Save as PDF in the browser dialog. No saved copy is confirmed." : "Share sheet closed. Choose Save to Files to keep a copy; saving is not confirmed here." });
    } catch (error) { if (isCurrent()) setNotice({ revision, text: web ? error instanceof BrowserReportError && error.reason === "popup" ? "Your browser blocked the report window. Allow popups for ReadBuddy and try again." : "Could not open your progress report. Please try again. No saved copy is confirmed." : "Could not share your progress report. Please try again." }); }
    finally { running.current = false; if (mounted.current) setBusy(false); }
  }
  return <View style={{ gap: 6 }}><Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ disabled, busy }} disabled={disabled} onPress={download} style={[s.primaryAction, { minHeight: 48, borderRadius: 18, backgroundColor: "#1D4ED8", flexDirection: "row", gap: 8, opacity: disabled ? 0.6 : 1 }]}><View pointerEvents="none" accessible={false} accessibilityElementsHidden importantForAccessibility="no-hide-descendants"><Text allowFontScaling={false} style={{ fontSize: 20 }}>{"\uD83D\uDCC4"}</Text></View><Text style={[s.primaryLabel, { color: "#FFFFFF", flexShrink: 1, textAlign: "center" }]}>{busy ? "Preparing PDF..." : label}</Text></Pressable>
    {!native && !web ? <Text style={s.body}>Open the iPhone or Android app to share a PDF.</Text> : null}
    {web ? <Text style={s.body}>{validWeb ? "Choose Save as PDF in the browser print dialog. No saved copy is confirmed." : "A valid Guardian demo report is unavailable."}</Text> : null}
    {notice.revision === revision && notice.text ? <Text accessibilityRole="alert" style={s.body}>{notice.text}</Text> : null}</View>;
}
