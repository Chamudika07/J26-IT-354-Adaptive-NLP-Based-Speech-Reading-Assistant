import { useState, type ReactNode } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSelectedScenario } from "../preview/selectedScenario";
import { educatorReportStudents, educatorClassOverview, educatorStudentNames, educatorMetrics, educatorValue, educatorHasMissing, type EducatorReportSelection } from "../export/educatorReports";
import { EducatorReportButton } from "./EducatorReportButton";
import { EducatorReadingOverview } from "./EducatorReadingOverview";
import { reportStyles as s } from "./LearnerReportLayout";
import { palette, radii, softShadow } from "../theme";

import { ReadingBuddyIllustration } from "./ReadingBuddyIllustration";

const studentAccents = ["#3182F6", "#8B5CF6", "#22C55E"];
const studentPastels = ["#EEF5FF", "#F4EFFF", "#EAFBF1"];
const students = educatorStudentNames;
/** Display-only fictional names. No learner identities, relationships or private state. */
export function EducatorStudents({ children, enabled = true }: { children: ReactNode; enabled?: boolean }) {
  const id = useSelectedScenario();
  const [student, setStudent] = useState<number | null>(null);
  const [separate, setSeparate] = useState(false);
  if (!__DEV__ || !enabled) return <>{children}</>;
  const reportSelection: EducatorReportSelection = { development: __DEV__, demoMode: enabled, role: "educator", scenarioId: id, student };
  const records = educatorReportStudents(reportSelection);
  const totals = educatorClassOverview(records);
  const back = <Pressable accessibilityRole="button" onPress={() => { setStudent(null); setSeparate(false); }} style={s.previewLink}><Text style={s.body}>Back to My Students</Text></Pressable>;
  if (separate) return <View style={{ flex: 1 }}>{back}{children}</View>;
  if (student !== null) {
    const projection = records[student]?.projection;
    let selection = "Individual reading history";
    if (student === 0 && id) { try { const index: unknown = JSON.parse(id)[0]; selection = typeof index === "number" && index >= 0 ? `Scenario ${index}` : "Selected reading results"; } catch { /* Fail closed below. */ } }
    return <View style={{ flex: 1 }}>{back}{projection ? <EducatorReadingOverview key={student} projection={projection} studentName={students[student]} reportAction={<EducatorReportButton selection={reportSelection} />} selection={selection} onSeparate={() => setSeparate(true)} /> : <ScrollView contentContainerStyle={[s.content, { paddingBottom: 128 }]}><Text style={{ color: palette.muted, fontSize: 12 }}>{"Demo \u00b7 Fictional classroom data"}</Text><Text style={s.title}>{students[student]}</Text><EducatorReportButton selection={reportSelection} unavailable /><Text accessibilityRole="alert" style={s.body}>These sample results are unavailable. Choose reading results in Learner view, then try again.</Text><Pressable accessibilityRole="button" onPress={() => setSeparate(true)} style={s.previewLink}><Text style={s.body}>View separate example</Text></Pressable></ScrollView>}</View>;
  }
  return <ScrollView style={s.scroll} contentContainerStyle={[s.content, { gap: 12, paddingBottom: 128 }]}>
    <View testID="teacher-header" style={styles.hero}>
      <View pointerEvents="none" accessible={false} accessibilityElementsHidden importantForAccessibility="no-hide-descendants" style={styles.skyDecorations}>
        <View style={styles.cloud} /><View style={[styles.cloud, styles.secondCloud]} />
        <Text allowFontScaling={false} style={styles.star}>{"\u2605"}</Text><Text allowFontScaling={false} style={[styles.star, styles.secondStar]}>{"\u2605"}</Text>
      </View>
      <View style={styles.headerCopy}><Text accessibilityRole="header" style={[s.title, styles.title]}>Teacher Dashboard</Text><Text style={styles.disclosure}>{"Demo \u00b7 Fictional classroom data"}</Text></View>
      <TeacherArtwork />
    </View>
    <View testID="teacher-class-overview" style={styles.overview}>
    <View style={styles.overviewHeading}><Text accessibilityRole="header" style={[s.heading, styles.sectionTitle]}>Class Overview</Text><TeacherArtwork books /></View>
    <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
      {[{ key: "students", label: "Students", value: totals.students }, { key: "sessions", label: "Completed Sessions", value: totals.sessions }, { key: "trends", label: "Students with supported trends", value: totals.trends }, { key: "missing", label: "Students with missing measurements", value: totals.missing }].map(m => <View key={m.key} testID={`class-${m.key}`} accessibilityLabel={`${m.label}: ${m.value}`} style={[s.card, styles.classMetric]}><Text style={[s.heading, { fontSize: 23, color: "#115E59" }]}>{m.value}</Text><Text style={s.body}>{m.label}</Text></View>)}
    </View>
    {totals.unavailable ? <Text style={s.body}>{totals.unavailable} {totals.unavailable === 1 ? "student's results are" : "students' results are"} unavailable. Session totals are incomplete.</Text> : null}
    </View>
    <EducatorReportButton selection={{ ...reportSelection, student: null }} />
    <Text accessibilityRole="header" style={s.heading}>My Students</Text>
    <Text style={{ color: palette.muted, fontSize: 12, lineHeight: 18 }}>Separate reading histories; results are not student rankings.</Text>
    {students.map((name, index) => {
      const p = records[index]!.projection;
      const context = p?.partitions.length === 1 ? p.partitions[0] : undefined;
      const metric = (key: string) => {
        const d = educatorMetrics.find(d => d.key === key)!; const v = context?.metrics.find(m => m.metric_name === key)?.latest_value;
        return v == null ? "Unavailable" : `${educatorValue(v, d.scale)}${d.unit === "%" ? "" : " "}${d.unit}`;
      };
      return <Pressable key={name} testID={`student-card-${index}`} accessibilityRole="button" accessibilityLabel={`View ${name}`} accessibilityHint="View Reading Progress" onPress={() => setStudent(index)} style={[s.card, styles.studentCard, { borderLeftColor: studentAccents[index] }]}>
        <View style={styles.studentHeading}><Text style={[s.heading, styles.studentName]}>{name}</Text><TeacherArtwork background={studentPastels[index]} /></View>
        <Text style={s.body}>{p ? `${p.included_session_count} completed ${p.included_session_count === 1 ? "session" : "sessions"}` : "Reading results: Unavailable"}</Text>
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 12 }}><Text style={s.body}>Accuracy: {metric("reading_accuracy")}</Text><Text style={s.body}>Speed: {metric("reading_fluency_wpm")}</Text></View>
        {p && educatorHasMissing(p) ? <Text style={{ color: palette.muted, fontSize: 12 }}>Some measurements unavailable</Text> : null}
        {p && p.partitions.length > 1 ? <Text style={s.body}>Different reading contexts; view progress for each.</Text> : null}
        <Text style={{ color: palette.muted, fontSize: 12 }}>{index === 0 ? "Follows selected reading results" : "Independent reading history"}</Text>
        <Text style={styles.progressLink}>View Reading Progress</Text>
      </Pressable>;
    })}
    <Pressable accessibilityRole="button" onPress={() => setSeparate(true)} style={s.previewLink}><Text style={s.body}>View separate example</Text></Pressable>
  </ScrollView>;
}

/** Bundled, local decorations never carry learner information or capture touches. */
function TeacherArtwork({ books = false, background }: { books?: boolean; background?: string }) {
  return <View testID="teacher-artwork" pointerEvents="none" accessible={false} accessibilityElementsHidden importantForAccessibility="no-hide-descendants" style={[styles.artwork, background ? { backgroundColor: background } : undefined]}>
    {books ? <Text allowFontScaling={false} style={styles.books}>{"\uD83D\uDCDA"}</Text> : <ReadingBuddyIllustration compact />}
  </View>;
}
const styles = StyleSheet.create({
  hero: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 8, padding: 14, borderRadius: 24, backgroundColor: "#EEF5FF", borderWidth: 1, borderColor: "#D7E7FF", overflow: "hidden" },
  headerCopy: { flexGrow: 1, flexShrink: 1, flexBasis: 170, gap: 6 },
  title: { fontSize: 22, color: "#07142B" },
  disclosure: { color: "#465B73", fontSize: 12, lineHeight: 18 },
  skyDecorations: { position: "absolute", top: 0, bottom: 0, left: 0, right: 0 },
  cloud: { position: "absolute", top: 3, right: 28, width: 70, height: 24, borderRadius: 30, backgroundColor: "#FFFFFF" },
  secondCloud: { top: 65, right: 145, width: 45, height: 18 },
  star: { position: "absolute", top: 9, right: 125, fontSize: 14, color: "#FFB020" },
  secondStar: { top: 70, right: 8, fontSize: 12, color: "#8B5CF6" },
  overview: { padding: 12, gap: 10, borderRadius: 22, backgroundColor: "#EAFBF1", ...softShadow },
  overviewHeading: { flexDirection: "row", alignItems: "center", gap: 8 },
  sectionTitle: { flex: 1, fontSize: 17, color: "#07142B" },
  classMetric: { flexBasis: 130, flexGrow: 1, padding: 10, gap: 4, borderRadius: radii.medium },
  studentCard: { borderLeftWidth: 5, minHeight: 44, padding: 14, gap: 8, borderRadius: 22, backgroundColor: "#FFFFFF", ...softShadow },
  studentHeading: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 8 },
  studentName: { flexGrow: 1, flexShrink: 1, flexBasis: 150, fontSize: 18, color: "#07142B" },
  artwork: { width: 94, height: 84, borderRadius: 18, alignItems: "center", justifyContent: "center", marginLeft: "auto" },
  books: { fontSize: 34, lineHeight: 44 },
  progressLink: { color: "#153E75", fontSize: 15, fontWeight: "800" },
});
