import { Pressable, StyleSheet, Text, View } from "react-native";

import { palette, radii, spacing } from "../theme";
import type { ReportingPeriodDays } from "../types";

interface PeriodSelectorProps {
  compact?: boolean;
  selectedDays: ReportingPeriodDays;
  onSelectDays: (days: ReportingPeriodDays) => void;
}

const PERIODS: readonly ReportingPeriodDays[] = [7, 30, 90];

export function PeriodSelector({ selectedDays, onSelectDays, compact = false }: PeriodSelectorProps) {
  return (
    <View accessibilityLabel="Choose a reporting period" style={styles.row}>
      <Text style={styles.prompt}>{compact ? "Period" : "Show progress from"}</Text>
      <View accessibilityRole="radiogroup" style={styles.group}>
        {PERIODS.map((days) => {
          const selected = days === selectedDays;
          return (
            <Pressable
              accessibilityRole="radio"
              accessibilityLabel={`${days} day reporting period`}
              accessibilityState={{ checked: selected }}
              key={days}
              onPress={() => onSelectDays(days)}
              style={({ pressed }) => [
                styles.button,
                compact && styles.homeButton,
                selected && styles.selectedButton,
                pressed && styles.pressedButton,
              ]}
            >
              <Text style={[styles.label, selected && styles.selectedLabel]}>{days}d</Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    flexWrap: "wrap",
    gap: spacing.xs,
  },
  prompt: {
    flexShrink: 1,
    color: palette.ink,
    fontSize: 13,
    fontWeight: "800",
  },
  group: {
    flexDirection: "row",
    gap: spacing.xs,
  },
  button: {
    minWidth: 48,
    paddingHorizontal: 8,
    minHeight: 48,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: palette.outline,
    backgroundColor: palette.surface,
  },
  homeButton: { minWidth: 44, minHeight: 44, paddingHorizontal: 8, borderRadius: radii.small },
  selectedButton: {
    borderColor: palette.teal,
    backgroundColor: palette.tealSoft,
  },
  pressedButton: {
    opacity: 0.78,
  },
  label: {
    color: palette.muted,
    fontWeight: "800",
  },
  selectedLabel: {
    color: palette.teal,
  },
});
