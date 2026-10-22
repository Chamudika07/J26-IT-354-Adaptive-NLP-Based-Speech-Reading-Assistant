import { createPp1Client } from "../data/pp1Client";
import replay from "../preview/connectedSessionReplay.json";
const session = { scopeKey: "test", getAccessToken: async () => "test-token" };
it("requires HTTPS before sending credentials", () => {
  expect(() => createPp1Client({ baseUrl: "http://example.test/api/v1", session })).toThrow();
});
it("accepts only the selected validated prefix", async () => {
  const result = replay[3]!;
  const body = { schemaVersion: "pp1-demo-result-v1", synthetic: true, verifiedTelemetry: false,
    source: "postgresql-backed-python", datasetKey: "pp1-six-session-journey", fixtureVersion: 1,
    sourceDigest: "33659d1c6947d7687a7d74e00f4540da065a2450b357805c90566ec71fda0ad7", selectedSessionCount: 3, role: "learner", generatedAt: result.generatedAt, result };
  const transport = jest.fn().mockResolvedValue({ status: 200, headers: { get: () => null }, text: async () => JSON.stringify(body) });
  const client = createPp1Client({ baseUrl: "https://example.test/api/v1", session }, transport);
  expect((await client(3)).result).toEqual(result);
  body.result = replay[2]!;
  await expect(client(3)).rejects.toThrow("unavailable");
});
it("never falls back after a server failure", async () => {
  const transport = jest.fn().mockResolvedValue({ status: 503 });
  await expect(createPp1Client({ baseUrl: "https://example.test/api/v1", session }, transport)(1)).rejects.toThrow("offline examples explicitly");
});
it("saves without telemetry body, validates receipt and refreshes saved evidence", async () => {
  const data = { schemaVersion: "pp1-demo-result-v1", synthetic: true, verifiedTelemetry: false,
    source: "postgresql-backed-python", datasetKey: "pp1-six-session-journey", fixtureVersion: 1,
    sourceDigest: "33659d1c6947d7687a7d74e00f4540da065a2450b357805c90566ec71fda0ad7",
    selectedSessionCount: 3, role: "learner", generatedAt: replay[3]!.generatedAt, result: replay[3] };
  const receipt = { synthetic: true, sourceDigest: data.sourceDigest, savedSessionCount: 3, createdSessionCount: 1 };
  const transport = jest.fn().mockImplementation(async (url: string) => ({ status: 200, headers: { get: () => null }, text: async () => JSON.stringify(url.endsWith("/3") ? receipt : data) }));
  const client = createPp1Client({ baseUrl: "https://example.test/api/v1", session }, transport);
  expect((await client.save(3)).selectedSessionCount).toBe(3);
  expect(transport.mock.calls[0][1].method).toBe("POST");
  expect(transport.mock.calls[0][1].body).toBeUndefined();
  expect(transport.mock.calls[1][0]).toMatch(/saved-progress$/);
  expect((await client.readSaved()).selectedSessionCount).toBe(3);
  receipt.savedSessionCount = 2;
  await expect(client.save(3)).rejects.toThrow("not confirmed");
});
