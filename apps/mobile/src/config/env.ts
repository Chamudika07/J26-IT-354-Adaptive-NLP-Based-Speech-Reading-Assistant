import { Platform } from "react-native";

/**
 * Environment configuration for the mobile client.
 *
 * Only public configuration belongs in the mobile bundle.
 * Never hardcode secrets, tokens, or production credentials here.
 *
 * For physical iPhone testing over local Wi-Fi:
 * Configure EXPO_PUBLIC_API_BASE_URL in `apps/mobile/.env` to point to your Mac's LAN IP,
 * e.g. `EXPO_PUBLIC_API_BASE_URL=http://172.20.10.3:8001`.
 *
 * Note: `10.0.2.2` is Android-emulator-specific and is never used on iOS.
 * When `.env` is updated, the Expo CLI process must be restarted (`expo start --clear`)
 * so Metro inlines the updated environment variable into the bundle.
 */
declare const process: {
  env: {
    EXPO_PUBLIC_API_BASE_URL?: string;
    [key: string]: string | undefined;
  };
};

const rawEnvUrl = process.env.EXPO_PUBLIC_API_BASE_URL?.trim();

export const API_BASE_URL: string =
  rawEnvUrl && rawEnvUrl.length > 0
    ? rawEnvUrl
    : Platform.OS === "android"
    ? "http://10.0.2.2:8001"
    : "http://localhost:8001";
