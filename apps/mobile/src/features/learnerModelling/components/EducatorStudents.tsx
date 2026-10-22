import { useState, type ReactNode } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { useSelectedScenario } from "../preview/selectedScenario";
import { educatorReportStudents, educatorClassOverview, educatorStudentNames, educatorMetrics, educatorValue, type EducatorReportSelection } from "../export/educatorReports";
import { EducatorReportButton } from "./EducatorReportButton";
import { EducatorReadingOverview } from "./EducatorReadingOverview";
import { DemoBanner } from "./DemoBanner";
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
    return <View style={{ flex: 1 }}>{back}{projection ? <EducatorReadingOverview key={student} projection={projection} studentName={students[student]} reportAction={<EducatorReportButton selection={reportSelection} />} selection={selection} onSeparate={() => setSeparate(true)} /> : <ScrollView contentContainerStyle={s.content}><DemoBanner /><Text style={s.title}>{students[student]}</Text><EducatorReportButton selection={reportSelection} unavailable /><Text accessibilityRole="alert" style={s.body}>These sample results are unavailable. Choose reading results in Learner view, then try again.</Text><Pressable accessibilityRole="button" onPress={() => setSeparate(true)} style={s.previewLink}><Text style={s.body}>View separate example</Text></Pressable></ScrollView>}</View>;
  }
  return <ScrollView style={s.scroll} contentContainerStyle={[s.content, { gap: 12, paddingBottom: 80 }]}>
    <DemoBanner /><Text accessibilityRole="header" style={s.title}>Teacher Dashboard</Text>
    <View style={[s.card, { padding: 12, gap: 8, backgroundColor: palette.tealSoft }]}>
      <Text accessibilityRole="header" style={s.heading}>Class Overview</Text>
      <Text style={s.body}>{totals.students} students · {totals.sessions} completed sessions in available records</Text>
      <Text style={s.body}>{totals.trends} with progress trends · {totals.missing} with missing measurements</Text>
      {totals.unavailable ? <Text style={s.body}>{totals.unavailable} student results unavailable. Session totals are incomplete.</Text> : null}
      <Text style={s.body}>Each student has a separate reading history. Compare results within the same activity, level and support.</Text>
      <EducatorReportButton selection={{ ...reportSelection, student: null }} />
    </View>
    <Text accessibilityRole="header" style={s.heading}>My Students</Text>
    <Text style={s.body}>Explore three fictional students. This is not a real class list.</Text>
    {students.map((name, index) => <Pressable key={name} accessibilityRole="button" accessibilityLabel={`View ${name}`} onPress={() => setStudent(index)} style={[s.card, { borderLeftWidth: 5, borderLeftColor: [palette.primary, palette.teal, palette.orange][index], minHeight: 64, padding: 12 }]}>
      <Text style={s.heading}>{name}</Text><Text style={s.body}>{index === 0 ? "Follows your selected reading results" : "A different reading history"}</Text><Text style={s.body}>{records[index]!.projection ? `${records[index]!.projection!.included_session_count} completed sessions` : "Reading results unavailable"}</Text>
      {records[index]!.projection?.partitions.length === 1 ? <Text style={s.body}>{educatorMetrics.map(d => { const m = records[index]!.projection!.partitions[0]!.metrics.find(m => m.metric_name === d.key); return `${educatorValue(m?.latest_value, d.scale)} ${d.unit}`; }).join(" · ")}</Text> : null}
      <Text style={{ color: palette.primary }}>View reading progress</Text>
    </Pressable>)}
    <Pressable accessibilityRole="button" onPress={() => setSeparate(true)} style={s.previewLink}><Text style={s.body}>View separate example</Text></Pressable>
  </ScrollView>;
}
