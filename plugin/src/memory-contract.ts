import { Type } from "typebox";
import { defineFeatureContract } from "openclaw/plugin-sdk/feature-contract";

const text = Type.String({ maxLength: 256 });
const binding = Type.Optional(text);
// JSON is bounded at the transport. Scope authority is never an input field.
export const memoryContract = defineFeatureContract({
  pluginId: "evolveclaw",
  operations: {
    query: { kind: "query", description: "Inspect recorded memory scopes, rules, evidence, history, and usage.",
      input: Type.Object({ operation: Type.Union([Type.Literal("scopes"), Type.Literal("list"), Type.Literal("history"), Type.Literal("detail"), Type.Literal("usage"), Type.Literal("status")]),
        bindingId: binding, ruleId: Type.Optional(text), limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 200 })),
        includeLegacy: Type.Optional(Type.Boolean()) }, { additionalProperties: false }),
      output: Type.Object({ data: Type.String({ maxLength: 1_000_000 }) }, { additionalProperties: false }) },
    mutate: { kind: "action", description: "Change learning or undo a recorded memory change at a checked revision.",
      input: Type.Object({ operation: Type.Union([Type.Literal("disable"), Type.Literal("restore"), Type.Literal("assign_scope"), Type.Literal("pause"), Type.Literal("resume"), Type.Literal("promote")]),
        bindingId: binding, ruleId: Type.Optional(text), historyId: Type.Optional(text),
        expectedRevision: Type.Integer({ minimum: 0 }) }, { additionalProperties: false }),
      output: Type.Object({ data: Type.String({ maxLength: 1_000_000 }) }, { additionalProperties: false }) },
  },
  events: {},
});
