import { Redirect, Stack } from "expo-router";
import { useApp } from "../../src/providers";

export default function AuthenticatedLayout() {
  const { active } = useApp();
  if (!active) return <Redirect href="/login" />;
  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: "#f6f5ef" },
        headerTintColor: "#163e36",
        title: "Reading Companion",
      }}
    />
  );
}
