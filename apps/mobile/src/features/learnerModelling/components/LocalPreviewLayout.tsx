import { developerToolsEnabled } from "../preview/developerTools";
import type { ReactNode } from "react";
import { ScrollView, Text, View } from "react-native";

import { FeatureAccent } from "./FeatureAccent";
import { ReferenceHero } from "./ReferenceHero";
import { DemoBanner } from "./DemoBanner";
import { reportStyles } from "./LearnerReportLayout";
import { palette } from "../theme";

export function LocalPreviewLayout({ title, disclosure, introduction, children, actions, homeHeader }: {
  title: string;
  disclosure: string;
  introduction: string;
  children: ReactNode;
  actions?: ReactNode;
  homeHeader?: ReactNode;
}) {
  return (
    <ScrollView style={reportStyles.scroll} contentContainerStyle={[reportStyles.content, { paddingBottom: 96 }]}
      keyboardShouldPersistTaps="handled" keyboardDismissMode="on-drag"
      stickyHeaderIndices={actions ? [0] : undefined}>
      {actions ? <View testID="local-preview-actions" style={{ backgroundColor: palette.paper }}>{actions}</View> : null}
      <DemoBanner />
      {homeHeader ?? <ReferenceHero>
        <FeatureAccent title={title} />
        <Text accessibilityRole="header" style={reportStyles.title}>{title}</Text>
        {(disclosure === "Created earlier using sample reading data." || (developerToolsEnabled() && disclosure !== "Sample Data")) ? <Text style={reportStyles.body}>{disclosure}</Text> : null}
        {introduction ? <Text style={reportStyles.body}>{introduction}</Text> : null}
      </ReferenceHero>}
      {children}
    </ScrollView>
  );
}
