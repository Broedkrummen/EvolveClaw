import type { OpenClawPluginApi } from "openclaw/plugin-sdk/plugin-entry";
import { defineFeaturePlugin, type FeatureInvocationContext } from "openclaw/plugin-sdk/feature-plugin";
import { memoryContract } from "./memory-contract.js";
import type { ScopeClient } from "./scope-client.js";
import type { MemoryScope, MemorySnapshot } from "./types.js";
import type { ScopeRegistry, ScopeBinding } from "./scope-registry.js";

export function registerMemoryControls(api: OpenClawPluginApi, client: ScopeClient, registry: ScopeRegistry,
  invalidate: (agent: string, scope: MemoryScope, snapshot: MemorySnapshot) => void): void {
  function authority(ctx: FeatureInvocationContext) {
    if (ctx.source === "tool") throw new Error("Memory management requires an owner command or Gateway operator connection.");
    const agentId = (ctx.source === "command" ? ctx.command.agentId : ctx.action.agentId) ?? "main";
    const scopes = ctx.source === "command" ? ctx.command.gatewayClientScopes ?? [] : ctx.action.client?.scopes ?? [];
    const owner = ctx.source === "command" && ctx.command.senderIsOwner === true;
    const canAdmin = owner || scopes.includes("operator.admin");
    const assert = (write: boolean) => {
      if (ctx.source === "command" && owner) ctx.command.assertOwnerCurrent?.();
      if (!owner && !canAdmin && !scopes.includes(write ? "operator.write" : "operator.read")) throw new Error("Memory permission is unavailable.");
    };
    return { agentId, canAdmin, assert };
  }
  function selected(bindingId: string | undefined, ctx: FeatureInvocationContext): ScopeBinding {
    const auth = authority(ctx);
    const scope = bindingId ? registry.get(bindingId, auth.agentId)
      : ctx.source === "command" ? registry.forSession(auth.agentId, ctx.command.sessionKey, ctx.command.sessionId)
        : registry.forSession(auth.agentId, ctx.source === "session-action" ? ctx.action.sessionKey : undefined);
    if (!scope) throw new Error("No recorded memory scope is selected. Run a normal task, then choose its scope.");
    return scope;
  }
  const handlers = {
    async query(input: { operation: string; bindingId?: string; ruleId?: string; limit?: number; includeLegacy?: boolean }, ctx: FeatureInvocationContext) {
      const auth = authority(ctx); auth.assert(false);
      if (input.operation === "scopes") return { data: JSON.stringify({ scopes: registry.list(auth.agentId).slice(-(input.limit ?? 100)).map(b => ({ id: b.id, label: b.label })) }) };
      if (input.includeLegacy && !auth.canAdmin) throw new Error("Only an owner or administrator can inspect unscoped legacy rules.");
      const b = selected(input.bindingId, ctx);
      const snapshot = await client.memory(b.agentName, b.scope, input.operation,
        { rule_id: input.ruleId, limit: input.limit ?? 100, include_legacy: input.includeLegacy ?? false }, undefined, auth.canAdmin);
      auth.assert(false);
      return { data: JSON.stringify(snapshot) };
    },
    async mutate(input: { operation: string; bindingId?: string; ruleId?: string; historyId?: string; expectedRevision: number }, ctx: FeatureInvocationContext) {
      const auth = authority(ctx); auth.assert(true);
      if (input.operation === "assign_scope" && !auth.canAdmin) throw new Error("Only an owner or administrator can assign legacy rules.");
      const b = selected(input.bindingId, ctx);
      auth.assert(true);
      const snapshot = await client.memory(b.agentName, b.scope, input.operation,
        { rule_id: input.ruleId, history_id: input.historyId, ...(input.operation === "assign_scope" ? { target_scope: b.scope } : {}) }, input.expectedRevision, auth.canAdmin);
      invalidate(b.agentName, b.scope, snapshot);
      return { data: JSON.stringify(snapshot) };
    },
  };
  defineFeaturePlugin({ contract: memoryContract, name: "EvolveClaw memory", description: "Scoped automatic learning with history and rollback.", setup: () => handlers }).register(api);

  // Read and mutation commands use the exact same handlers as the dashboard.
  api.registerCommand({ name: "evolveclaw", description: "Inspect learning: list, history, detail ID, usage, status, scopes.", acceptsArgs: true,
    requireAuth: true, requiredScopes: ["operator.read"], async handler(command) {
      const [operation = "list", id] = (command.args ?? "").trim().split(/\s+/);
      if (!["list", "history", "detail", "usage", "status", "scopes", "legacy"].includes(operation)) return { text: "Use /evolveclaw list | history | detail ID | usage | status | scopes | legacy." };
      try {
        const output = await handlers.query({ operation: operation === "legacy" ? "list" : operation, ruleId: id, includeLegacy: operation === "legacy" }, { source: "command", command, api });
        return { text: formatSnapshot(JSON.parse(output.data)) };
      } catch (error) { return { text: (error as Error).message }; }
    } });
  api.registerCommand({ name: "evolveclaw-change", description: "Change learning: pause, resume, disable ID, restore ID, undo CHANGE_ID, assign ID, promote ID.", acceptsArgs: true,
    requireAuth: true, requiredScopes: ["operator.write"], async handler(command) {
      const [op, id] = (command.args ?? "").trim().split(/\s+/);
      const operation = op === "undo" ? "restore" : op === "assign" ? "assign_scope" : op;
      if (!["pause", "resume", "disable", "restore", "assign_scope", "promote"].includes(operation)) return { text: "Use /evolveclaw-change pause | resume | disable ID | restore ID | undo CHANGE_ID | assign ID | promote ID." };
      try {
        const ctx: FeatureInvocationContext = { source: "command", command, api };
        const before = JSON.parse((await handlers.query({ operation: "status" }, ctx)).data) as MemorySnapshot;
        const output = await handlers.mutate({ operation, ...(op === "undo" ? { historyId: id } : { ruleId: id }), expectedRevision: before.revision }, ctx);
        return { text: `Memory change saved. ${formatSnapshot(JSON.parse(output.data))}` };
      } catch (error) { return { text: (error as Error).message }; }
    } });
}

function formatSnapshot(snapshot: MemorySnapshot & { scopes?: { id: string; label: string }[] }): string {
  if (snapshot.scopes) return snapshot.scopes.map(s => `${s.id}: ${s.label}`).join("\n") || "No recorded scopes yet. Run a normal task first.";
  const lines = [`Learning ${snapshot.paused ? "paused" : "active"} · revision ${snapshot.revision}`];
  if (snapshot.rules) lines.push(...snapshot.rules.map(r => `${r.id} [${r.status}] ${r.text}`), snapshot.rules.length ? "" : "No rules in this scope yet.");
  if (snapshot.history) lines.push(...snapshot.history.map(h => `${h.id} · ${h.operation} · ${h.summary}`));
  if (snapshot.detail) lines.push(JSON.stringify(snapshot.detail, null, 2));
  if (snapshot.usage) lines.push(JSON.stringify(snapshot.usage, null, 2));
  return lines.join("\n");
}
