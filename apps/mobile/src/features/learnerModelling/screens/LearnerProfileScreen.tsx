import { Pressable, Text, View } from "react-native";

import { DemoLearnerCard, DemoPreferencesCard } from "../components/DemoLearnerCard";
import { LearnerReportLayout, reportStyles, type LearnerReportProps } from "../components/LearnerReportLayout";

export function LearnerProfileScreen(props: LearnerReportProps & { onOpenSettings?: () => void }) {
  const { dashboard } = props;
  const latest = dashboard.difficultyProgression.reduce<typeof dashboard.difficultyProgression[number] | undefined>(
    (current, observation) => !current || Date.parse(observation.observedAt) > Date.parse(current.observedAt) ? observation : current,
    undefined,
  );
  return (
    <LearnerReportLayout {...props} title="My Profile"
      introduction="Explore your reading results and settings.">
      {props.demoMode ? <><DemoLearnerCard editable /><DemoPreferencesCard /></> : null}
      <View style={reportStyles.card}>
        <Text style={reportStyles.period}>Learner Profile</Text>
        <Text accessibilityRole="header" style={reportStyles.heading}>Reading performance overview</Text>
        {dashboard.metrics.map((metric) => (
          <View key={metric.key} style={{ gap: 8 }}>
            <Text style={reportStyles.heading}>{metric.label}</Text>
            <Text style={reportStyles.body}>Latest observed: {metric.latestValue} {metric.unit}</Text>
            <Text style={reportStyles.body}>{metric.evidenceLabel}</Text>
          </View>
        ))}
      </View>
      <View style={reportStyles.card}>
        <Text accessibilityRole="header" style={reportStyles.heading}>Observed difficulty and support context</Text>
        <Text style={reportStyles.body}>{latest ? `Latest observed difficulty: ${latest.tier}` : "Observed difficulty unavailable."}</Text>
        {latest ? <Text style={reportStyles.body}>{latest.context}</Text> : null}
        <Text style={reportStyles.body}>This shows support used in the sample reading, not your saved preferences.</Text>
      </View>
      <View style={reportStyles.card}>
        <Text accessibilityRole="header" style={reportStyles.heading}>Choose your reading settings.</Text>
        <Text style={reportStyles.body}>Your demo choices stay on this device. They do not change reading support.</Text>
        <Text style={reportStyles.body}>Reading results do not tell us your identity or saved choices.</Text>
        {props.demoMode && props.onOpenSettings ? (
          <Pressable accessibilityRole="button" accessibilityLabel="Try local Support Settings"
            onPress={props.onOpenSettings} style={reportStyles.previewLink}>
            <Text style={reportStyles.heading}>Try local Support Settings</Text>
            <Text style={reportStyles.body}>Preview the appearance of sample text without changing account preferences.</Text>
          </Pressable>
        ) : null}
      </View>
    </LearnerReportLayout>
  );
}
