import { Pressable, StyleSheet, Text, View } from "react-native";

import type { ReportingPeriodDays } from "../types";

interface PeriodSelectorProps {
  selectedDays: ReportingPeriodDays;
  onSelectDays: (days: ReportingPeriodDays) => void;
}

const PERIODS: readonly ReportingPeriodDays[] = [7, 30, 90];

export function PeriodSelector({ selectedDays, onSelectDays }: PeriodSelectorProps) {
  return (
    <View style={styles.row}>
      <Text style={styles.prompt}>Reporting period</Text>
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
              style={[styles.button, selected && styles.selectedButton]}
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
  },
  prompt: {
    color: "#40596B",
    fontSize: 13,
    fontWeight: "600",
  },
  group: {
    flexDirection: "row",
    gap: 6,
  },
  button: {
    minWidth: 48,
    minHeight: 40,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 20,
    backgroundColor: "#E4EBF1",
  },
  selectedButton: {
    backgroundColor: "#CDECE5",
  },
  label: {
    color: "#526A7B",
    fontWeight: "700",
  },
  selectedLabel: {
    color: "#0E5B4E",
  },
});
