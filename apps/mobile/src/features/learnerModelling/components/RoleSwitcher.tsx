import { Pressable, StyleSheet, Text, View } from "react-native";

import type { PreviewRole } from "../types";

interface RoleSwitcherProps {
  selectedRole: PreviewRole;
  onSelectRole: (role: PreviewRole) => void;
}

const ROLES: readonly { value: PreviewRole; label: string }[] = [
  { value: "learner", label: "Learner" },
  { value: "guardian", label: "Guardian" },
  { value: "educator", label: "Educator" },
];

export function RoleSwitcher({ selectedRole, onSelectRole }: RoleSwitcherProps) {
  return (
    <View accessibilityRole="tablist" style={styles.group}>
      {ROLES.map(({ value, label }) => {
        const selected = value === selectedRole;
        return (
          <Pressable
            accessibilityRole="tab"
            accessibilityLabel={`${label} synthetic preview`}
            accessibilityState={{ selected }}
            key={value}
            onPress={() => onSelectRole(value)}
            style={[styles.button, selected && styles.selectedButton]}
          >
            <Text style={[styles.label, selected && styles.selectedLabel]}>{label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  group: {
    flexDirection: "row",
    gap: 8,
  },
  button: {
    flex: 1,
    minHeight: 44,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#B9C8D5",
    backgroundColor: "#FFFFFF",
  },
  selectedButton: {
    borderColor: "#176B5B",
    backgroundColor: "#176B5B",
  },
  label: {
    color: "#274154",
    fontSize: 14,
    fontWeight: "700",
  },
  selectedLabel: {
    color: "#FFFFFF",
  },
});
