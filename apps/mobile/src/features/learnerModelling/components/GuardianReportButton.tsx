import { useLayoutEffect, useRef, useState } from "react";
import { Platform, Pressable, Text, View } from "react-native";
import { exportGuardianReport, type GuardianReportData } from "../export/guardianReport";
import { reportStyles as s } from "./LearnerReportLayout";
export function GuardianReportButton({ data }: { data: GuardianReportData }) {
  const [busy, setBusy] = useState(false); const [notice, setNotice] = useState({ revision: "", text: "" });
  const running = useRef(false); const mounted = useRef(false); const generation = useRef(0); const revision = JSON.stringify(data);
  useLayoutEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useLayoutEffect(() => { generation.current += 1; }, [revision]);
  const native = Platform.OS === "ios" || Platform.OS === "android";
  const disabled = busy || !native || !__DEV__;
  async function download() {
    if (disabled || running.current) return;
    running.current = true; setBusy(true); setNotice({ revision, text: "" });
    const token = generation.current; const isCurrent = () => mounted.current && generation.current === token;
    try { await exportGuardianReport({ data, platform: Platform.OS, isCurrent });
      if (isCurrent()) setNotice({ revision, text: "Share sheet closed. Choose Save to Files to keep a copy; saving is not confirmed here." });
    } catch { if (isCurrent()) setNotice({ revision, text: "Could not share your progress report. Please try again." }); }
    finally { running.current = false; if (mounted.current) setBusy(false); }
  }
  return <View style={{ gap: 6 }}><Pressable accessibilityRole="button" accessibilityLabel="Download Progress Report" accessibilityState={{ disabled, busy }} disabled={disabled} onPress={download} style={[s.primaryAction, { minHeight: 44, opacity: disabled ? 0.6 : 1 }]}><Text style={s.primaryLabel}>{busy ? "Preparing PDF..." : "Download Progress Report"}</Text></Pressable>
    {!native ? <Text style={s.body}>Open the iPhone or Android app to share a PDF.</Text> : null}
    {notice.revision === revision && notice.text ? <Text accessibilityRole="alert" style={s.body}>{notice.text}</Text> : null}</View>;
}
