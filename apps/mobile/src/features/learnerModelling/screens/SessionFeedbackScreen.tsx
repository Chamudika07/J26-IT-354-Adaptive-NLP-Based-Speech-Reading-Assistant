import { Pressable, StyleSheet, Text, View } from "react-native";

import { reportStyles } from "../components/LearnerReportLayout";
import { FeedbackIllustration } from "../components/FeedbackIllustration";
import { LocalPreviewLayout } from "../components/LocalPreviewLayout";
import { PreviewChoiceGroup } from "../components/PreviewChoiceGroup";
import { usePreviewSession } from "../preview/PreviewSession";
import { palette, radii, spacing } from "../theme";

const FEELINGS = [
  { value: "Happy", label: "Happy", icon: "✓" },
  { value: "Unsure", label: "Unsure", icon: "?" },
  { value: "Tired", label: "Tired", icon: "…" },
];
const DIFFICULTY = ["Easy", "Okay", "Difficult"].map((value) => ({ value, label: value }));
const CONTINUE = ["Yes", "Maybe later", "No"].map((value) => ({ value, label: value }));

export function SessionFeedbackScreen() {
  const { feedback: { feeling, difficulty, continueReading }, setFeedback, clearFeedback, storageMessage } = usePreviewSession();
  const setFeeling = (feeling: string) => setFeedback((draft) => ({ ...draft, feeling }));
  const setDifficulty = (difficulty: string) => setFeedback((draft) => ({ ...draft, difficulty }));
  const setContinueReading = (continueReading: string) => setFeedback((draft) => ({ ...draft, continueReading }));

  return (
    <LocalPreviewLayout title="Session Feedback" disclosure="NOT SUBMITTED · LOCAL PREVIEW ONLY"
      introduction="Tell us how sample reading might feel. Your demo answers stay on this device. They are not sent or saved to a real reading session.">
      <FeedbackIllustration />
      <Text accessibilityLiveRegion="polite" style={reportStyles.body}>{storageMessage}</Text>
      <View style={reportStyles.card}>
        <PreviewChoiceGroup label="How did reading feel?" choices={FEELINGS} selected={feeling} onSelect={setFeeling} />
        <PreviewChoiceGroup label="Was it easy, okay, or difficult?" choices={DIFFICULTY} selected={difficulty} onSelect={setDifficulty} />
        <PreviewChoiceGroup label="Would you like to continue reading?" choices={CONTINUE} selected={continueReading} onSelect={setContinueReading} />
      </View>
      <View style={reportStyles.card}>
        <Text accessibilityRole="header" style={reportStyles.heading}>Your preview answers — NOT SUBMITTED</Text>
        <Text accessibilityLiveRegion="polite" style={reportStyles.body}>
          Feeling: {feeling ?? "Not selected"}{"\n"}
          Difficulty: {difficulty ?? "Not selected"}{"\n"}
          Continue reading: {continueReading ?? "Not selected"}
        </Text>
        <Pressable accessibilityRole="button" onPress={clearFeedback} style={styles.clear}>
          <Text style={styles.clearLabel}>Clear preview responses</Text>
        </Pressable>
      </View>
    </LocalPreviewLayout>
  );
}

const styles = StyleSheet.create({
  clear: { minHeight: 48, justifyContent: "center", padding: spacing.md, borderRadius: radii.small, backgroundColor: palette.primary },
  clearLabel: { color: palette.surface, fontSize: 16, fontWeight: "800", textAlign: "center" },
});
