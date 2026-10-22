import { useLayoutEffect, useRef, useState } from "react";
import { Platform, Pressable, Text, View } from "react-native";
import { exportEducatorReport, type EducatorReportSelection } from "../export/educatorReports";
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
  const disabled = unavailable || busy || !native || !__DEV__ || !selection.development || !selection.demoMode || selection.role !== "educator";
  const label = selection.student === null ? "Download Class Analytics Report" : "Download Student Analytics Report";
  async function download() {
    if (disabled || running.current) return;
    running.current = true; setBusy(true); setNotice({ revision, text: "" });
    const token = generation.current;
    const isCurrent = () => mounted.current && generation.current === token;
    try {
      await exportEducatorReport({ selection, platform: Platform.OS, isCurrent });
      if (isCurrent()) setNotice({ revision, text: "Share sheet closed. Choose Save to Files or a sharing app to keep a copy; saving is not confirmed here." });
    } catch {
      if (isCurrent()) setNotice({ revision, text: "Could not share this PDF. Please try again. No saved copy is confirmed." });
    } finally {
      running.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  return <View style={{ gap: 6 }}>
    <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ disabled, busy }} disabled={disabled} onPress={download} style={[s.primaryAction, { opacity: disabled ? 0.6 : 1 }]}><Text style={s.primaryLabel}>{busy ? "Preparing PDF…" : label}</Text></Pressable>
    {unavailable ? <Text style={s.body}>Reading results are unavailable for this report.</Text> : !native ? <Text style={s.body}>Open the iPhone or Android app to share a PDF.</Text> : null}
    {message ? <Text accessibilityRole="alert" style={s.body}>{message}</Text> : null}
  </View>;
}
