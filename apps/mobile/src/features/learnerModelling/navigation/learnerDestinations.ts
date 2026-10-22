export type LearnerDestination = "home" | "progress" | "suggestions" | "profile" | "settings" | "feedback" | "report" | "test";

export const LEARNER_DESTINATIONS = [
  { key: "home", label: "Home", icon: "⌂", title: "Reading Home", description: "Explore your sample reading results." },
  { key: "progress", label: "Analytics", icon: "↗", title: "My Analytics", description: "See your reading results over time." },
  { key: "suggestions", label: "Suggestions", icon: "✦", title: "My Reading Tips", description: "Suggestions to review with a parent or teacher." },
  { key: "profile", label: "Profile", icon: "Aa", title: "My Profile", description: "Your reading results and settings." },
] as const;

// Secondary areas stay in the feature menu, not in the compact bottom tab bar.
export const SECONDARY_DESTINATIONS = [
  { key: "settings", title: "Support Settings", description: "Choose how the sample text looks." },
  { key: "feedback", title: "Session Feedback", description: "Share how sample reading might feel. Answers stay on this device." },
  { key: "report", title: "My Reading Report", description: "View your demo reading report or a saved local AI-generated preview." },
] as const;
