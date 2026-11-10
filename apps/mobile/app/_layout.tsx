import { Stack } from "expo-router";
import { Providers } from "../src/providers";

export default function Root() {
  return (
    <Providers>
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: "#f6f5ef" },
          headerTintColor: "#163e36",
          title: "Reading Companion",
        }}
      >
        <Stack.Screen name="login" options={{ title: "Sign in" }} />
        <Stack.Screen name="(secure)" options={{ headerShown: false }} />
      </Stack>
    </Providers>
  );
}
