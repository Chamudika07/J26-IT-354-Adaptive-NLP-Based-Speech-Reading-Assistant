import type { ReactNode } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  type TextInputProps,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { errorMessage } from "./api/errors";
import type { ErrorContext } from "./api/errors";

export function Screen({ children }: { children: ReactNode }) {
  return (
    <SafeAreaView style={styles.safe} edges={["bottom", "left", "right"]}>
      <KeyboardAvoidingView
        style={styles.safe}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={styles.content}
        >
          {children}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
export const Title = ({ children }: { children: ReactNode }) => (
  <Text accessibilityRole="header" style={styles.title}>
    {children}
  </Text>
);
export const Message = ({ children }: { children: ReactNode }) => (
  <Text style={styles.body}>{children}</Text>
);
export const Card = ({ children }: { children: ReactNode }) => (
  <View style={styles.card}>{children}</View>
);
export function Button({
  title,
  onPress,
  disabled = false,
  secondary = false,
}: {
  title: string;
  onPress(): void;
  disabled?: boolean;
  secondary?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={title}
      accessibilityState={{ disabled }}
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        secondary && styles.secondary,
        (disabled || pressed) && { opacity: 0.55 },
      ]}
    >
      <Text style={[styles.buttonText, secondary && { color: "#173f3a" }]}>
        {title}
      </Text>
    </Pressable>
  );
}
export function Field({
  label,
  error,
  ...props
}: TextInputProps & { label: string; error?: string }) {
  return (
    <View style={styles.field}>
      <Text style={styles.label}>{label}</Text>
      <TextInput
        accessibilityLabel={label}
        placeholderTextColor="#52615f"
        style={[
          styles.input,
          props.multiline && { minHeight: 180, textAlignVertical: "top" },
        ]}
        {...props}
      />
      {error && (
        <Text accessibilityRole="alert" style={styles.error}>
          {error}
        </Text>
      )}
    </View>
  );
}
export function ErrorNotice({
  error,
  context = "reading",
}: {
  error: unknown;
  context?: ErrorContext;
}) {
  return error ? (
    <Text
      accessibilityRole="alert"
      accessibilityLiveRegion="polite"
      style={styles.error}
    >
      {errorMessage(error, context)}
    </Text>
  ) : null;
}
export const Loading = () => (
  <ActivityIndicator
    size="large"
    color="#176a58"
    accessibilityLabel="Loading"
  />
);
const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: "#f6f5ef" },
  content: {
    padding: 22,
    gap: 18,
    width: "100%",
    maxWidth: 760,
    alignSelf: "center",
    paddingBottom: 48,
  },
  title: { fontSize: 30, fontWeight: "700", color: "#163e36", lineHeight: 40 },
  body: { fontSize: 18, lineHeight: 29, color: "#263d38" },
  card: {
    backgroundColor: "#fff",
    borderWidth: 1,
    borderColor: "#d5dfd7",
    borderRadius: 16,
    padding: 20,
    gap: 14,
  },
  button: {
    minHeight: 52,
    padding: 14,
    borderRadius: 12,
    backgroundColor: "#176a58",
    justifyContent: "center",
  },
  secondary: { backgroundColor: "#e1ede6" },
  buttonText: {
    color: "#fff",
    fontSize: 18,
    fontWeight: "600",
    textAlign: "center",
  },
  field: { gap: 8 },
  label: { fontSize: 18, fontWeight: "600", color: "#263d38" },
  input: {
    borderWidth: 1,
    borderColor: "#6c8279",
    borderRadius: 10,
    padding: 14,
    fontSize: 18,
    lineHeight: 28,
    minHeight: 52,
    backgroundColor: "#fff",
    color: "#20372e",
  },
  error: { color: "#902d25", fontSize: 17, lineHeight: 26 },
});
