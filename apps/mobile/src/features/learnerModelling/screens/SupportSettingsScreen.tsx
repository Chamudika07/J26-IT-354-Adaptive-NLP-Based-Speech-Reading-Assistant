import { useState } from "react";
import { developerToolsEnabled } from "../preview/developerTools";
import { Alert, Pressable, ScrollView, StyleSheet, Switch, Text, useWindowDimensions, View } from "react-native";
import { usePreviewSession } from "../preview/PreviewSession";
import { palette, radii } from "../theme";

const FONT_SIZES = { comfortable: 18, large: 22, extraLarge: 28 } as const;
const FONT_CHOICES = [
  { value: "comfortable", label: "Normal" },
  { value: "large", label: "Large" },
  { value: "extraLarge", label: "XL" },
] as const;

export function SupportSettingsScreen() {
  const { fontScale } = useWindowDimensions();
  const { settings: { font, spacing: lineSpacing, highlight, audio }, setSettings, resetSettings, saveSettings, resetDemo, storageMessage, storageReady } = usePreviewSession();
  const [details, setDetails] = useState(false);
  return <ScrollView style={styles.scroll} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled" keyboardDismissMode="on-drag">
    <View style={styles.header}>
      <Text accessibilityRole="header" style={styles.title}>Reading Settings</Text>
      <Text style={styles.body}>Make reading feel comfortable.</Text>
      <Text style={styles.disclosure}>{"Demo \u00b7 Fictional data"}</Text>
    </View>
    <View style={styles.card}>
      <View accessibilityRole="radiogroup" accessibilityLabel="Reading font size" style={styles.group}>
        <Text accessibilityRole="header" style={styles.heading}>Font size</Text>
        <View style={styles.choices}>
          {FONT_CHOICES.map(item => <Pressable key={item.value} accessibilityRole="radio" accessibilityLabel={`Reading font size: ${item.label}`} accessibilityState={{ checked: font === item.value }}
            onPress={() => setSettings(draft => ({ ...draft, font: item.value }))}
            style={({ pressed }) => [styles.choice, fontScale > 1.3 && styles.largeChoice, font === item.value && styles.selected, pressed && styles.pressed]}>
            <Text style={[styles.choiceText, font === item.value && styles.selectedText]}>{item.label}</Text>
          </Pressable>)}
        </View>
      </View>
      <View accessibilityRole="radiogroup" accessibilityLabel="Line spacing" style={styles.group}>
        <Text accessibilityRole="header" style={styles.heading}>Line spacing</Text>
        <View style={styles.choices}>
          {([{ value: "comfortable", label: "Normal" }, { value: "wide", label: "Wide" }] as const).map(item => <Pressable key={item.value} accessibilityRole="radio" accessibilityLabel={`Line spacing: ${item.label}`} accessibilityState={{ checked: lineSpacing === item.value }}
            onPress={() => setSettings(draft => ({ ...draft, spacing: item.value }))}
            style={({ pressed }) => [styles.choice, fontScale > 1.3 && styles.largeChoice, lineSpacing === item.value && styles.selected, pressed && styles.pressed]}>
            <Text style={[styles.choiceText, lineSpacing === item.value && styles.selectedText]}>{item.label}</Text>
          </Pressable>)}
        </View>
      </View>
      <View style={styles.toggleRow}>
        <Text style={styles.toggleLabel}>Highlighting</Text>
        <Switch accessibilityLabel="Text highlighting preference" value={highlight} onValueChange={value => setSettings(draft => ({ ...draft, highlight: value }))}
          hitSlop={8} trackColor={{ false: palette.outline, true: palette.primary }} />
      </View>
      <View style={styles.toggleRow}>
        <Text style={styles.toggleLabel}>Audio preference</Text>
        <Switch accessibilityLabel="Audio-support preference" value={audio} onValueChange={value => setSettings(draft => ({ ...draft, audio: value }))}
          hitSlop={8} trackColor={{ false: palette.outline, true: palette.primary }} />
      </View>
      <Text style={styles.body}>Audio playback is not connected.</Text>
    </View>
    <View style={styles.card}>
      <Text accessibilityRole="header" style={styles.heading}>Try your settings</Text>
      <View style={styles.sample}>
        <Text testID="support-sample-text" style={{ fontSize: FONT_SIZES[font], lineHeight: FONT_SIZES[font] * (lineSpacing === "wide" ? 2 : 1.6), color: palette.ink }}>
          <Text style={highlight && styles.highlight}>The kind fox shares a book.</Text>{"\nReading together can be fun."}
        </Text>
      </View>
      <Text accessibilityLiveRegion="polite" style={styles.disclosure}>{highlight ? "Highlighting is on in this sample." : "Highlighting is off in this sample."}</Text>
    </View>
    <View style={styles.card}>
      <Text accessibilityRole="header" style={styles.heading}>Reading support</Text>
      <Text style={styles.body}>Try the appearance of sample text here. Reading support and suggestions stay unchanged.</Text>
    </View>
    <View style={styles.card}>
      <Text style={styles.body}>Save these choices on this device.</Text>
      <Pressable accessibilityRole="button" disabled={!storageReady} accessibilityState={{ disabled: !storageReady }} onPress={() => void saveSettings()} style={[styles.primary, !storageReady && styles.disabled]}><Text style={styles.primaryText}>Save My Settings</Text></Pressable>
      <Pressable accessibilityRole="button" onPress={resetSettings} style={styles.secondary}><Text style={styles.actionText}>Reset Settings</Text></Pressable>
      <Text accessibilityLiveRegion="polite" style={styles.disclosure}>{storageMessage}</Text>
    </View>
    <Pressable accessibilityRole="button" onPress={() => Alert.alert("Reset Demo Data?", "Reset this device's demo profile, settings, answers and journey? Saved AI reports and custom session files stay unchanged.", [{ text: "Cancel", style: "cancel" }, { text: "Reset Demo Data", style: "destructive", onPress: resetDemo }])} style={styles.secondary}><Text style={styles.actionText}>Reset Demo Data</Text></Pressable>
    {developerToolsEnabled() ? <View style={styles.card}>
      <Pressable accessibilityRole="button" accessibilityState={{ expanded: details }} onPress={() => setDetails(!details)} style={styles.secondary}><Text style={styles.actionText}>Developer Details</Text></Pressable>
      {details ? <Text style={styles.body}>Spacing is a device-local demo appearance preference only. Authoritative support modes, manual overrides and locks are unchanged.</Text> : null}
    </View> : null}
  </ScrollView>;
}
const styles = StyleSheet.create({
  scroll: { backgroundColor: palette.paper }, content: { paddingHorizontal: 16, paddingTop: 8, paddingBottom: 128, gap: 12 },
  header: { gap: 4, paddingRight: 48 }, title: { color: palette.primaryDark, fontSize: 22, fontWeight: "900" },
  body: { color: palette.ink, fontSize: 14, lineHeight: 20 }, disclosure: { color: palette.muted, fontSize: 12, lineHeight: 18 },
  card: { backgroundColor: palette.surface, borderRadius: radii.medium, padding: 12, gap: 12 },
  group: { gap: 8 }, heading: { color: palette.primaryDark, fontSize: 16, fontWeight: "800" }, choices: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  choice: { flexGrow: 1, flexBasis: 64, minWidth: 64, minHeight: 44, paddingHorizontal: 10, paddingVertical: 8, alignItems: "center", justifyContent: "center", borderRadius: radii.small, borderWidth: 1, borderColor: palette.outline, backgroundColor: palette.primarySoft },
  largeChoice: { flexBasis: "100%" },
  choiceText: { fontSize: 15, fontWeight: "700", color: palette.primaryDark }, selected: { backgroundColor: palette.primary, borderColor: palette.primary }, selectedText: { color: palette.surface }, pressed: { opacity: 0.8 },
  toggleRow: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 8, minHeight: 48, paddingVertical: 4 },
  toggleLabel: { flexGrow: 1, flexBasis: 140, color: palette.ink, fontSize: 15, fontWeight: "700" },
  sample: { padding: 14, backgroundColor: palette.paper, borderRadius: radii.small, borderWidth: 1, borderColor: palette.outline }, highlight: { backgroundColor: palette.yellowSoft },
  primary: { minHeight: 48, padding: 12, borderRadius: radii.small, backgroundColor: palette.primary, alignItems: "center", justifyContent: "center" }, primaryText: { color: palette.surface, fontSize: 16, fontWeight: "800" },
  secondary: { minHeight: 44, padding: 10, borderRadius: radii.small, backgroundColor: palette.primarySoft, alignItems: "center", justifyContent: "center" }, actionText: { color: palette.primaryDark, fontSize: 14, fontWeight: "700" }, disabled: { opacity: 0.55 },
});
