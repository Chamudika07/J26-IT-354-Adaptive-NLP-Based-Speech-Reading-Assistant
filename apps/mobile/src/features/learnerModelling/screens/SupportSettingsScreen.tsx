import { useState } from "react";
import { developerToolsEnabled } from "../preview/developerTools";
import { Alert, Pressable, StyleSheet, Switch, Text, View } from "react-native";

import { reportStyles } from "../components/LearnerReportLayout";
import { LocalPreviewLayout } from "../components/LocalPreviewLayout";
import { PreviewChoiceGroup } from "../components/PreviewChoiceGroup";
import { usePreviewSession } from "../preview/PreviewSession";
import { palette, radii, spacing } from "../theme";

const FONT_SIZES = { comfortable: 18, large: 22, extraLarge: 28 } as const;
const FONT_CHOICES = [
  { value: "comfortable", label: "Comfortable" },
  { value: "large", label: "Large" },
  { value: "extraLarge", label: "Extra large" },
] as const;

export function SupportSettingsScreen() {
  const { settings: { font, spacing: lineSpacing, highlight, audio }, setSettings, resetSettings, saveSettings, resetDemo, storageMessage, storageReady } = usePreviewSession();
  const [details, setDetails] = useState(false);
  const setFont = (font: keyof typeof FONT_SIZES) => setSettings((draft) => ({ ...draft, font }));
  const setHighlight = (highlight: boolean) => setSettings((draft) => ({ ...draft, highlight }));
  const setAudio = (audio: boolean) => setSettings((draft) => ({ ...draft, audio }));

  return (
    <LocalPreviewLayout title="Support Settings" disclosure="LOCAL PREVIEW ONLY"
      introduction="Try the settings below. They change this sample only and are not saved to your learner profile.">
      <View style={reportStyles.card}>
        <PreviewChoiceGroup label="Reading font size" choices={FONT_CHOICES} selected={font} onSelect={setFont} />
        <PreviewChoiceGroup label="Line spacing" choices={[{ value: "comfortable", label: "Comfortable" }, { value: "wide", label: "Wide" }]} selected={lineSpacing} onSelect={(value) => setSettings((draft) => ({ ...draft, spacing: value }))} />
        <Text style={reportStyles.body}>Demo choices stay on this device. They do not change a real learner profile.</Text>
        <View style={styles.toggleRow}>
          <Text style={styles.toggleLabel}>Text highlighting preference</Text>
          <Switch accessibilityLabel="Text highlighting preference" value={highlight} onValueChange={setHighlight}
            trackColor={{ false: palette.outline, true: palette.primary }} />
        </View>
        <View style={styles.toggleRow}>
          <Text style={styles.toggleLabel}>Audio-support preference</Text>
          <Switch accessibilityLabel="Audio-support preference" value={audio} onValueChange={setAudio}
            trackColor={{ false: palette.outline, true: palette.primary }} />
        </View>
      </View>
      <View style={reportStyles.card}>
        <Text accessibilityRole="header" style={reportStyles.heading}>Sample appearance</Text>
        <Text style={reportStyles.body}>Sample text only. This is not a reading session or player.</Text>
        <View style={styles.sample}>
          <Text testID="support-sample-text" style={{ fontSize: FONT_SIZES[font], lineHeight: FONT_SIZES[font] * (lineSpacing === "wide" ? 2 : 1.6), color: palette.ink }}>
            <Text style={highlight && styles.highlight}>The kind fox shares a book.</Text>
          </Text>
        </View>
        <Text accessibilityLiveRegion="polite" style={reportStyles.body}>
          {highlight ? "Highlighting is on in this sample." : "Highlighting is off in this sample."}
        </Text>
        <Text accessibilityLiveRegion="polite" style={reportStyles.body}>
          {audio ? "Audio support preferred in this local preview. Audio playback is not connected." : "Audio support not preferred in this local preview. No audio will play."}
        </Text>
      </View>
      <View style={reportStyles.card}>
        <Text accessibilityRole="header" style={reportStyles.heading}>Your reading support</Text>
        <Text style={reportStyles.body}>Fixed support stays the same. Adaptive support offers ideas based on reading results.</Text>
        <Text style={reportStyles.body}>Manual support uses a chosen setting. These sample choices do not change reading support.</Text>
      </View>
      {developerToolsEnabled() ? <View style={reportStyles.card}>
        <Pressable accessibilityRole="button" accessibilityState={{ expanded: details }} onPress={() => setDetails(!details)} style={reportStyles.previewLink}><Text style={reportStyles.body}>Developer Details</Text></Pressable>
        {details ? <Text style={reportStyles.body}>Spacing is a device-local demo appearance preference only. Authoritative support modes, manual overrides and locks are unchanged.</Text> : null}
      </View> : null}
      <Text accessibilityLiveRegion="polite" style={reportStyles.body}>{storageMessage}</Text>
      <Pressable accessibilityRole="button" disabled={!storageReady} accessibilityState={{ disabled: !storageReady }} onPress={() => void saveSettings()} style={reportStyles.primaryAction}><Text style={reportStyles.primaryLabel}>Save My Settings</Text></Pressable>
      <Pressable accessibilityRole="button" onPress={() => Alert.alert("Reset Demo Data?", "Reset this device's demo profile, settings, answers and journey? Saved AI reports and custom session files stay unchanged.", [{ text: "Cancel", style: "cancel" }, { text: "Reset Demo Data", style: "destructive", onPress: resetDemo }])} style={reportStyles.previewLink}><Text style={reportStyles.body}>Reset Demo Data</Text></Pressable>
      <Pressable accessibilityRole="button" onPress={resetSettings} style={reportStyles.previewLink}>
        <Text style={reportStyles.body}>Reset Settings</Text>
      </Pressable>
    </LocalPreviewLayout>
  );
}

const styles = StyleSheet.create({
  toggleRow: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: spacing.md, minHeight: 56 },
  toggleLabel: { flexGrow: 1, flexBasis: 160, color: palette.ink, fontSize: 16, fontWeight: "700" },
  sample: { padding: spacing.lg, backgroundColor: palette.paper, borderRadius: radii.medium },
  highlight: { backgroundColor: palette.yellowSoft },
});
