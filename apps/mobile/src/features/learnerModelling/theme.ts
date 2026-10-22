export const palette = {
  ink: "#142D63",
  muted: "#4D6275",
  subtle: "#7A8798",
  paper: "#F3F8FF",
  surface: "#FFFFFF",
  outline: "#E0E9F7",
  primary: "#1261D6",
  primaryDark: "#123C87",
  primarySoft: "#E7F1FF",
  heroSoft: "#E3F6FC",
  violet: "#6545C1",
  violetSoft: "#F0E9FF",
  coral: "#B73955",
  coralSoft: "#FFE5EA",
  teal: "#08796B",
  tealSoft: "#E0F6EE",
  blue: "#2768A9",
  blueSoft: "#E1F0FF",
  yellow: "#865B00",
  yellowSoft: "#FFF0BD",
  orange: "#A34A13",
  orangeSoft: "#FFE6CF",
  danger: "#A63D54",
} as const;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 28,
} as const;

export const radii = {
  small: 12,
  medium: 18,
  large: 24,
  pill: 999,
} as const;

export const softShadow = {
  shadowColor: "#27304A",
  shadowOffset: { width: 0, height: 4 },
  shadowOpacity: 0.06,
  shadowRadius: 8,
  elevation: 2,
} as const;
