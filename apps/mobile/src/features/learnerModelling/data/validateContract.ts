import schemas from "./component4Schemas.json";

export type ContractName = keyof typeof schemas;
type Node = {
  $ref?: string; anyOf?: Node[]; type?: string; const?: unknown; enum?: unknown[];
  properties?: Record<string, Node>; required?: string[]; additionalProperties?: boolean;
  items?: Node; minItems?: number; maxItems?: number; minLength?: number; maxLength?: number;
  minimum?: number; maximum?: number; pattern?: string; format?: string;
};
export const isUuid = (value: unknown): value is string => typeof value === "string" &&
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
export function isAwareDate(value: unknown): value is string {
  if (typeof value !== "string") return false;
  const parts = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/i.exec(value);
  if (!parts || !Number.isFinite(Date.parse(value))) return false;
  const year = Number(parts[1]), month = Number(parts[2]), day = Number(parts[3]);
  const daysInMonth = new Date(Date.UTC(year, month, 0)).getUTCDate();
  return year >= 1 && month >= 1 && month <= 12 && day >= 1 && day <= daysInMonth &&
    Number(parts[4]) < 24 && Number(parts[5]) < 60 && Number(parts[6]) < 60;
}

/** Validate only against the checked-in backend schema, without defaults or coercion. */
export function validateContract(name: ContractName, value: unknown): boolean {
  const root = schemas[name] as Node & { $defs?: Record<string, Node> };
  function valid(node: Node, data: unknown, depth: number): boolean {
    if (depth > 30) return false;
    if (node.$ref) {
      const definition = root.$defs?.[node.$ref.replace("#/$defs/", "")];
      return !!definition && valid(definition, data, depth + 1);
    }
    if (node.anyOf && !node.anyOf.some(child => valid(child, data, depth + 1))) return false;
    if ("const" in node && data !== node.const) return false;
    if (node.enum && !node.enum.includes(data)) return false;
    if (node.type === "null") return data === null;
    if (node.type === "object") {
      if (!data || typeof data !== "object" || Array.isArray(data)) return false;
      const object = data as Record<string, unknown>;
      if (node.required?.some(key => !(key in object))) return false;
      if (node.additionalProperties === false && Object.keys(object).some(key => !node.properties?.[key])) return false;
      return Object.entries(object).every(([key, v]) => !node.properties?.[key] || valid(node.properties[key], v, depth + 1));
    }
    if (node.type === "array") {
      return Array.isArray(data) && data.length >= (node.minItems ?? 0) &&
        data.length <= (node.maxItems ?? 10000) && (!node.items || data.every(v => valid(node.items!, v, depth + 1)));
    }
    if (node.type === "string") {
      if (typeof data !== "string" || data.length < (node.minLength ?? 0) || data.length > (node.maxLength ?? 10000)) return false;
      if (node.pattern && !new RegExp(node.pattern).test(data)) return false;
      if (node.format === "uuid" && !isUuid(data)) return false;
      if (node.format === "date-time" && !isAwareDate(data)) return false;
    }
    if (node.type === "number" || node.type === "integer") {
      if (typeof data !== "number" || !Number.isFinite(data)) return false;
      if (node.type === "integer" && !Number.isInteger(data)) return false;
      if (data < (node.minimum ?? -Infinity) || data > (node.maximum ?? Infinity)) return false;
    }
    if (node.type === "boolean" && typeof data !== "boolean") return false;
    return true;
  }
  return valid(root, value, 0);
}
