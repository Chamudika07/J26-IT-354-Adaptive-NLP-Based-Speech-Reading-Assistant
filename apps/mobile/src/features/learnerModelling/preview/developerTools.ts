/** Build-time opt-in only; never authentication, persistence or a production route. */
export function developerToolsEnabled(): boolean {
  return __DEV__ === true && process.env.EXPO_PUBLIC_COMPONENT4_DEVELOPER_TOOLS === "1";
}
