import { Pressable, StyleSheet, Text, View } from "react-native";

import { palette, radii, spacing } from "../theme";

export function PreviewChoiceGroup<T extends string>({ label, choices, selected, onSelect }: {
  label: string;
  choices: readonly { value: T; label: string; icon?: string }[];
  selected: T | undefined;
  onSelect: (value: T) => void;
}) {
  return (
    <View accessibilityRole="radiogroup" accessibilityLabel={label} style={styles.group}>
      <Text accessibilityRole="header" style={styles.heading}>{label}</Text>
      <View style={styles.choices}>
        {choices.map((choice) => (
          <Pressable key={choice.value} accessibilityRole="radio"
            accessibilityLabel={`${label}: ${choice.label}`}
            accessibilityState={{ checked: selected === choice.value }}
            onPress={() => onSelect(choice.value)}
            style={({ pressed }) => [styles.choice, selected === choice.value && styles.selected, pressed && styles.pressed]}>
            {choice.icon ? <Text accessible={false} style={[styles.choiceIcon, selected === choice.value && styles.selectedLabel]}>{choice.icon}</Text> : null}
            <Text style={[styles.label, selected === choice.value && styles.selectedLabel]}>{selected === choice.value ? "● " : "○ "}{choice.label}</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  choiceIcon: { fontSize: 28, fontWeight: "800", color: palette.primary, marginBottom: spacing.sm },
  group: { gap: spacing.md },
  heading: { color: palette.ink, fontSize: 18, fontWeight: "800" },
  choices: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  choice: { minHeight: 48, flexGrow: 1, flexBasis: 100, padding: spacing.md, justifyContent: "center", borderRadius: radii.small, borderWidth: 1, borderColor: palette.outline, backgroundColor: palette.primarySoft },
  selected: { borderColor: palette.primary, backgroundColor: palette.primary },
  selectedLabel: { color: palette.surface },
  label: { color: palette.primaryDark, fontSize: 16, fontWeight: "700", flexShrink: 1 },
  pressed: { opacity: 0.8 },
});
