import { useState, type ReactNode } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { useSelectedScenario } from "../preview/selectedScenario";
import { educatorReportStudents, educatorClassOverview, educatorStudentNames, educatorMetrics, educatorValue, educatorHasMissing, type EducatorReportSelection } from "../export/educatorReports";
import { EducatorReportButton } from "./EducatorReportButton";
import { EducatorReadingOverview } from "./EducatorReadingOverview";
import { reportStyles as s } from "./LearnerReportLayout";
import { palette } from "../theme";

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
    <Text accessibilityRole="header" style={[s.title, { fontSize: 22 }]}>Teacher Dashboard</Text>
    <Text style={{ color: palette.muted, fontSize: 12, lineHeight: 18 }}>{"Demo \u00b7 Fictional classroom data"}</Text>
    <Text accessibilityRole="header" style={[s.heading, { fontSize: 17 }]}>Class Overview</Text>
    <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
      {[{ key: "students", label: "Students", value: totals.students }, { key: "sessions", label: "Completed Sessions", value: totals.sessions }, { key: "trends", label: "Students with supported trends", value: totals.trends }, { key: "missing", label: "Students with missing measurements", value: totals.missing }].map(m => <View key={m.key} testID={`class-${m.key}`} accessibilityLabel={`${m.label}: ${m.value}`} style={[s.card, { flexBasis: 130, flexGrow: 1, padding: 10, gap: 4 }]}><Text style={[s.heading, { fontSize: 23 }]}>{m.value}</Text><Text style={s.body}>{m.label}</Text></View>)}
    </View>
    {totals.unavailable ? <Text style={s.body}>{totals.unavailable} {totals.unavailable === 1 ? "student's results are" : "students' results are"} unavailable. Session totals are incomplete.</Text> : null}
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
      return <Pressable key={name} testID={`student-card-${index}`} accessibilityRole="button" accessibilityLabel={`View ${name}`} accessibilityHint="View Reading Progress" onPress={() => setStudent(index)} style={[s.card, { borderLeftWidth: 4, borderLeftColor: [palette.primary, palette.teal, palette.orange][index], minHeight: 44, padding: 12, gap: 6 }]}>
        <Text style={[s.heading, { fontSize: 18 }]}>{name}</Text>
        <Text style={s.body}>{p ? `${p.included_session_count} completed ${p.included_session_count === 1 ? "session" : "sessions"}` : "Reading results: Unavailable"}</Text>
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 12 }}><Text style={s.body}>Accuracy: {metric("reading_accuracy")}</Text><Text style={s.body}>Speed: {metric("reading_fluency_wpm")}</Text></View>
        {p && educatorHasMissing(p) ? <Text style={{ color: palette.muted, fontSize: 12 }}>Some measurements unavailable</Text> : null}
        {p && p.partitions.length > 1 ? <Text style={s.body}>Different reading contexts; view progress for each.</Text> : null}
        <Text style={{ color: palette.muted, fontSize: 12 }}>{index === 0 ? "Follows selected reading results" : "Independent reading history"}</Text>
        <Text style={{ color: palette.primary, fontSize: 15, fontWeight: "700" }}>View Reading Progress</Text>
      </Pressable>;
    })}
    <Pressable accessibilityRole="button" onPress={() => setSeparate(true)} style={s.previewLink}><Text style={s.body}>View separate example</Text></Pressable>
  </ScrollView>;
}
