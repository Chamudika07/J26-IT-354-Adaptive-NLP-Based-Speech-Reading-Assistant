import pin from "./educatorStudentContract.json";
import type { EducatorArtifact } from "./roleScenarioResults";

/** Integrity pins are fictional demo fixtures, never classroom authorization. */
export function selectEducatorStudent(index: number, read: () => unknown = () => require("./educatorStudentResults.json")): EducatorArtifact["projection"] | null {
  if (!__DEV__ || !Number.isInteger(index) || index < 0 || index >= pin.length) return null;
  try {
    if (JSON.stringify(read()) !== JSON.stringify(pin)) return null;
    return JSON.parse(JSON.stringify(pin[index])) as EducatorArtifact["projection"];
  } catch { return null; }
}
