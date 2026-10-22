import { Pressable, StyleSheet, Text, View } from "react-native";

import { palette, radii, softShadow, spacing } from "../theme";
import type { PreviewRole } from "../types";

interface RoleSwitcherProps {
  selectedRole: PreviewRole;
  onSelectRole: (role: PreviewRole) => void;
}

const ROLES: readonly { value: PreviewRole; label: string; icon: string }[] = [
  { value: "learner", label: "Learner", icon: "Aa" },
  { value: "guardian", label: "Guardian", icon: "♡" },
  { value: "educator", label: "Educator", icon: "✓" },
];

export function RoleSwitcher({ selectedRole, onSelectRole }: RoleSwitcherProps) {
  return (
    <View style={[styles.container, selectedRole === "educator" && __DEV__ && { paddingRight: 40 }]}>
      {selectedRole !== "educator" ? <Text style={styles.demoLabel}>Demo views only: choose your view</Text> : null}
      <View accessibilityRole="tablist" style={styles.group}>
        {ROLES.map(({ value, label, icon }) => {
          const selected = value === selectedRole;
          return (
            <Pressable
              accessibilityRole="tab"
              accessibilityLabel={`${label} sample preview`}
              accessibilityState={{ selected }}
              key={value}
              onPress={() => onSelectRole(value)}
              style={({ pressed }) => [
                styles.button,
                selectedRole === "educator" && styles.compactButton,
                selected && styles.selectedButton,
                pressed && styles.pressedButton,
              ]}
            >
              <Text style={[styles.icon, selected && styles.selectedLabel]}>{icon}</Text>
              <Text style={[styles.label, selected && styles.selectedLabel]}>{label}</Text>
            </Pressable>
          );
        })}
        </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: spacing.sm,
  },
  demoLabel: {
    color: palette.primaryDark,
    fontSize: 12,
    fontWeight: "800",
  },
  group: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  button: {
    flex: 1,
    minHeight: 56,
    paddingVertical: 8,
    paddingHorizontal: 4,
    alignItems: "center",
    justifyContent: "center",
    gap: 2,
    borderRadius: radii.medium,
    borderWidth: 1,
    borderColor: palette.outline,
    backgroundColor: palette.surface,
    ...softShadow,
  },
  compactButton: { minHeight: 48, flexDirection: "row", flexWrap: "wrap", gap: 6 },
  selectedButton: {
    borderColor: palette.primary,
    backgroundColor: palette.primary,
  },
  pressedButton: {
    opacity: 0.82,
  },
  icon: {
    color: palette.primary,
    fontSize: 15,
    fontWeight: "900",
  },
  label: {
    color: palette.ink,
    fontSize: 13,
    textAlign: "center",
    fontWeight: "800",
  },
  selectedLabel: {
    color: "#FFFFFF",
  },
});
