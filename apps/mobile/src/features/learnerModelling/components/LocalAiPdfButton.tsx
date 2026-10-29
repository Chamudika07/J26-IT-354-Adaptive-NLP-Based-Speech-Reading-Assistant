import { BrowserReportError } from "../export/browserAiPdf";
import { useEffect, useRef, useState } from "react";
import { Platform, Pressable, Text, View } from "react-native";

import { reportStyles } from "./LearnerReportLayout";
import { exportLocalAiPdf, installedPdfModules, ReportPdfError, type PdfSelection } from "../export/localAiPdf";
import { selectLocalReportSnapshot } from "../preview/localReportSnapshot";

export function LocalAiPdfButton({ snapshot, selection, compact = false }: {
  snapshot: unknown; selection: PdfSelection; compact?: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const generation = useRef(0);
  const running = useRef(false);
  useEffect(() => {
    generation.current += 1;
    return () => { generation.current += 1; };
  }, [snapshot, selection.enabled, selection.development, selection.demoMode, selection.role]);

  // Never expose a learner snapshot action in live or other-role screens. In a
  // learner demo, unavailable capabilities stay visible with a disabled action.
  if (!selection.demoMode || selection.role !== "learner") return null;
  const development = __DEV__ && selection.development;
  const report = selectLocalReportSnapshot({ ...selection, development, read: () => snapshot });
  const web = Platform.OS === "web";
  const label = web ? "Print / Save as PDF" : "Download AI Report PDF";
  let modules: ReturnType<typeof installedPdfModules> = null;
  try { if (!web) modules = installedPdfModules(); } catch { /* Visible disabled state below. */ }
  const native = Platform.OS === "ios" || Platform.OS === "android";
  const disabled = !report || (!web && (!modules || !native)) || busy;

  async function download() {
    if (disabled || running.current) return;
    running.current = true;
    setBusy(true);
    setMessage("");
    const token = generation.current;
    const isCurrent = () => generation.current === token;
    try {
      await exportLocalAiPdf({ snapshot, selection, platform: Platform.OS, modules, isCurrent });
      if (isCurrent()) setMessage(web ? 'Report opened. Select Print / Save as PDF, then choose Save as PDF in the print dialog. No saved copy is confirmed.' : "Share sheet closed. Saving or cancelling is handled by your device; no saved copy is confirmed.");
    } catch (error) {
      if (isCurrent()) setMessage(web ? error instanceof BrowserReportError && error.reason === "popup"
        ? "Your browser blocked the report window. Allow popups for ReadBuddy and try again."
        : "Could not open the printable report. Please try again. No saved copy is confirmed."
        : error instanceof ReportPdfError && error.reason === "sharing"
        ? "File sharing is unavailable on this device. No saved copy is confirmed."
        : "PDF export unavailable. No saved copy is confirmed. Please try again later.");
    } finally {
      running.current = false;
      if (isCurrent()) setBusy(false);
    }
  }

  return (
    <View style={reportStyles.card}>
      {!compact ? <>
        <Text accessibilityRole="header" style={reportStyles.heading}>Download PDF</Text>
        <Text style={reportStyles.body}>Download the saved sample report. No new report is created.</Text>
      </> : null}
      <Pressable accessibilityRole="button" accessibilityLabel={label}
        accessibilityState={{ disabled, busy }} disabled={disabled} onPress={download}
        style={[reportStyles.primaryAction, { opacity: disabled ? 0.6 : 1 }]}>
        <Text style={reportStyles.primaryLabel}>{busy ? "Preparing PDF…" : label}</Text>
      </Pressable>
      {!development ? <Text style={reportStyles.body}>This sample PDF is available only in the demo development build.</Text>
        : !report ? <Text style={reportStyles.body}>Open a saved AI report first.</Text> : null}
      {!web && !modules ? <Text style={reportStyles.body}>PDF download is not available in this build.</Text> : null}
      {!web && !native ? <Text style={reportStyles.body}>PDF export requires the Android or iOS app.</Text> : null}
      {web ? <Text style={reportStyles.body}>Choose Save as PDF in the browser print dialog. No new AI report is generated.</Text> : null}
      {message ? <Text accessibilityRole="alert" accessibilityLiveRegion="polite" style={reportStyles.body}>{message}</Text> : null}
    </View>
  );
}
