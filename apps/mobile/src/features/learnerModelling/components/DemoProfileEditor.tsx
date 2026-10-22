import { useState } from "react";
import { Pressable, Text, TextInput, View } from "react-native";
import { usePreviewSession } from "../preview/PreviewSession";
import { PreviewChoiceGroup } from "./PreviewChoiceGroup";
import { reportStyles } from "./LearnerReportLayout";
import { palette } from "../theme";

export const DEMO_AVATARS = { book: { label: "Book Buddy", icon: "\uD83D\uDCD6" }, fox: { label: "Friendly Fox", icon: "\uD83E\uDD8A" }, owl: { label: "Reading Owl", icon: "\uD83E\uDD89" } } as const;
export function DemoAvatar({ avatar }: { avatar: keyof typeof DEMO_AVATARS }) {
  return <Text accessibilityRole="image" accessibilityLabel={`${DEMO_AVATARS[avatar].label} avatar`} style={{ fontSize: 38 }}>{DEMO_AVATARS[avatar].icon}</Text>;
}
export function DemoProfileEditor({ onClose }: { onClose: () => void }) {
  const { profile, setProfile, resetProfile } = usePreviewSession();
  const [name, setName] = useState(profile.name);
  const [avatar, setAvatar] = useState(profile.avatar);
  const [error, setError] = useState("");
  const save = () => {
    const clean = name.trim();
    if (!clean || clean.length > 32 || /[\u0000-\u001f\u007f]/.test(clean)) {
      setError("Choose a name with 1 to 32 letters or characters."); return;
    }
    setProfile({ name: clean, avatar }); onClose();
  };
  return <View style={{ gap: 12 }}>
    <Text style={reportStyles.heading}>Edit Profile</Text>
    <Text style={reportStyles.body}>Use a made-up name for this demo. Changes stay on this device only.</Text>
    <TextInput accessibilityLabel="Demo display name" value={name} onChangeText={setName} maxLength={32} autoCorrect={false} style={{ minHeight: 48, borderWidth: 1, borderColor: palette.outline, borderRadius: 12, padding: 12, fontSize: 18, color: palette.ink }} />
    <PreviewChoiceGroup label="Choose your avatar" choices={Object.entries(DEMO_AVATARS).map(([value, item]) => ({ value: value as keyof typeof DEMO_AVATARS, label: item.label, icon: item.icon }))} selected={avatar} onSelect={setAvatar} />
    <View testID="demo-profile-preview" style={{ padding: 12, borderRadius: 16, backgroundColor: palette.tealSoft, gap: 8 }}>
      <Text style={reportStyles.period}>Preview</Text><DemoAvatar avatar={avatar} /><Text style={reportStyles.heading}>{name.trim() || "Your name"}</Text>
    </View>
    {error ? <Text accessibilityRole="alert" style={reportStyles.body}>{error}</Text> : null}
    <Text style={reportStyles.body}>This is not a verified learner identity. Saved AI reports and PDFs stay unchanged.</Text>
    <Pressable accessibilityRole="button" onPress={save} style={reportStyles.primaryAction}><Text style={reportStyles.primaryLabel}>Save demo profile</Text></Pressable>
    <Pressable accessibilityRole="button" onPress={() => { resetProfile(); onClose(); }} style={reportStyles.previewLink}><Text style={reportStyles.body}>Reset demo profile</Text></Pressable>
    <Pressable accessibilityRole="button" onPress={onClose} style={reportStyles.previewLink}><Text style={reportStyles.body}>Cancel profile changes</Text></Pressable>
  </View>;
}
