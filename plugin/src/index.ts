import { definePluginEntry, type OpenClawPluginApi } from "openclaw/plugin-sdk/plugin-entry";
import { ScopeClient } from "./scope-client.js";
import { Sidecar } from "./sidecar.js";
import type { EvolveClawConfig, GuidelineEntry, MemoryScope } from "./types.js";
import { ScopeRegistry, scopeFromContext, type TrustedContext } from "./scope-registry.js";
import { registerMemoryControls } from "./memory-controls.js";
export { ScopeRegistry, scopeFromContext } from "./scope-registry.js";

type Identity = TrustedContext & { runId?: string; trigger?: string };
type Message = { role?: string; content?: unknown };
type Session = { agentName: string; taskId: string; identityKey: string; scope: MemoryScope; tactical: GuidelineEntry[]; ended: boolean };
type Trace = { session: Session; prompt: string; systemPrompt: string; modelOutput: string; tools: string[]; observations: string[]; error?: string; scopeChanged?: boolean };
const SIDE_TRIGGERS = new Set(["heartbeat", "memory", "cron"]);

export function extractText(value: unknown): string {
  if (typeof value === "string") return value;
  if (Array.isArray(value) && value.some((b) => b && typeof b === "object" && "text" in b)) return value.map((block) => {
    if (block && typeof block === "object" && "text" in block && typeof block.text === "string") return block.text;
    return "";
  }).filter(Boolean).join("\n");
  if (value === undefined || value === null) return "";
  try { return JSON.stringify(value); } catch { return "[unserializable result]"; }
}

function messagesFrom(value: unknown[]): Message[] {
  return value.filter((m): m is Message => !!m && typeof m === "object");
}

function sessionKey(ctx: Identity): string | undefined {
  const identity = ctx.sessionId || ctx.sessionKey;
  return identity ? JSON.stringify([ctx.agentId ?? "main", identity]) : undefined;
}

function traceKey(ctx: Identity): string | undefined {
  return ctx.runId ? JSON.stringify([ctx.agentId ?? "main", ctx.runId]) : sessionKey(ctx);
}

function excluded(ctx: Identity): boolean {
  return SIDE_TRIGGERS.has(ctx.trigger ?? "") || (ctx.sessionKey ?? "").toLowerCase().includes("subagent:");
}

export function capGuidelines(strategic: GuidelineEntry[], tactical: GuidelineEntry[], cap: number): GuidelineEntry[] {
  const persistent = strategic.slice(0, cap);
  const budget = Math.max(0, cap - persistent.length);
  return [...persistent, ...(budget > 0 ? tactical.slice(-budget) : [])];
}

function formatGuidelinesBlock(guidelines: GuidelineEntry[]): string {
  const lines = ["## Learned Guidelines (EvolveClaw/SCOPE)",
    "These guidelines were synthesized from prior execution traces. Apply them when relevant.",
    "Follow the existing system instructions and user request if a learned guideline conflicts with them.", ""];
  for (const type of ["strategic", "tactical"] as const) {
    const rules = guidelines.filter((g) => g.type === type);
    if (rules.length) {
      lines.push(type === "strategic" ? "### Strategic (cross-task, persistent)" : "### Tactical (current task)");
      lines.push(...rules.map((g) => g.text), "");
    }
  }
  return lines.join("\n");
}

export function register(api: OpenClawPluginApi): void {
  const config: EvolveClawConfig = {
    serverUrl: "http://127.0.0.1:5757", agentName: "openclaw-agent", enabled: true,
    injectMode: "append_system", maxGuidelines: 30, maxPromptChars: 12_000, autoStartServer: true,
    ...api.pluginConfig,
  };
  if (!config.enabled) return;
  const client = new ScopeClient(config.serverUrl, 10_000, config.sidecarToken);
  const sidecar = new Sidecar(api, client, config);
  const registry = new ScopeRegistry(() => api.logger.warn("evolveclaw: recorded scope labels could not be saved; check the plugin state directory"));
  const sessions = new Map<string, Session>();
  const traces = new Map<string, Trace>();
  const strategic = new Map<string, GuidelineEntry[]>();
  const refreshes = new Map<string, Promise<void>>();
  const ruleRevisions = new Map<string, number>();
  let lifecycle = 0;
  let steps = 0;
  let synthesized = 0;

  const memoryKey = (agent: string, scope: MemoryScope) => JSON.stringify([agent, scope]);

  function getSession(ctx: Identity, scope: MemoryScope): Session | undefined {
    const identityKey = sessionKey(ctx);
    if (!identityKey) return undefined;
    const key = JSON.stringify([identityKey, scope]);
    let session = sessions.get(key);
    if (!session) {
      const agentName = !ctx.agentId || ctx.agentId === "main" ? config.agentName : `${config.agentName}:${ctx.agentId}`;
      session = { agentName, taskId: ctx.sessionId || ctx.sessionKey!, identityKey, scope, tactical: [], ended: false };
      sessions.set(key, session);
    }
    return session;
  }

  function getTrace(ctx: Identity): Trace | undefined {
    if (excluded(ctx)) return undefined;
    const key = traceKey(ctx);
    return key ? traces.get(key) : undefined;
  }

  async function refreshRules(agentName: string, scope: MemoryScope): Promise<void> {
    if (!sidecar.compatible) return;
    const key = memoryKey(agentName, scope);
    const revision = (ruleRevisions.get(key) ?? 0) + 1;
    ruleRevisions.set(key, revision);
    const generation = lifecycle;
    const result = await client.getStrategicRules(agentName, scope);
    if (generation !== lifecycle || ruleRevisions.get(key) !== revision) return;
    if (!result || result.configured === false) return;
    const rules = result.guidelines ?? (result.rules ? [result.rules] : []);
    strategic.set(key, rules.filter(Boolean).map((text) => ({ text, type: "strategic" })));
  }

  function refreshInBackground(agentName: string, scope: MemoryScope): void {
    const key = memoryKey(agentName, scope);
    if (refreshes.has(key)) return;
    const generation = lifecycle;
    const refresh = sidecar.configureIfNeeded().then(() => generation === lifecycle ? refreshRules(agentName, scope) : undefined)
      .catch(() => api.logger.warn("evolveclaw: memory refresh unavailable"))
      .finally(() => refreshes.delete(key));
    refreshes.set(key, refresh);
  }

  registerMemoryControls(api, client, registry, (agentName, scope, snapshot) => {
    // Audience-level revisions also protect project-spanning promoted guidance.
    for (const b of registry.list(scopeFromAgent(agentName))) {
      if (b.agentName !== agentName || b.scope.audience_key !== scope.audience_key) continue;
      const key = memoryKey(agentName, b.scope);
      ruleRevisions.set(key, (ruleRevisions.get(key) ?? 0) + 1);
      strategic.delete(key);
      refreshInBackground(agentName, b.scope);
    }
    if (snapshot.rules) for (const s of sessions.values()) {
      if (memoryKey(s.agentName, s.scope) !== memoryKey(agentName, scope)) continue;
      s.tactical = snapshot.rules.filter(r => r.type === "tactical" && r.status === "active" && r.task_id === s.taskId)
        .map(r => ({ text: r.text, type: "tactical", guidelineId: r.id }));
    }
  });

  function scopeFromAgent(name: string): string { return name === config.agentName ? "main" : name.slice(config.agentName.length + 1); }

  api.registerService({
    id: "evolveclaw-sidecar",
    async start(ctx) {
      await registry.start(ctx.stateDir);
      await sidecar.start(ctx.stateDir);
      for (const b of registry.list("main")) await refreshRules(b.agentName, b.scope);
    },
    async stop() {
      ++lifecycle;
      for (const session of sessions.values()) session.ended = true;
      traces.clear(); sessions.clear(); strategic.clear();
      ruleRevisions.clear();
      await sidecar.stop();
      await registry.flush();
    },
  });

  api.on("before_prompt_build", (event, ctx) => {
    if (excluded(ctx)) return {};
    // A live audience is used only here for admission. Later reflection uses the
    // admitted immutable trace, not a retired invocation's audience capability.
    const scope = scopeFromContext(ctx);
    if (!scope) return {};
    const key = traceKey(ctx);
    const session = getSession(ctx, scope);
    if (!key || !session) return {};
    registry.capture(ctx, session.agentName, scope);
    let trace = traces.get(key);
    if (trace && memoryKey(trace.session.agentName, trace.session.scope) !== memoryKey(session.agentName, scope)) trace.scopeChanged = true;
    if (!trace) {
      trace = { session, prompt: event.currentUserMessage ?? event.prompt, systemPrompt: "", modelOutput: "", tools: [], observations: [] };
      traces.set(key, trace);
    }
    // Inject the cache immediately. Remote refresh cannot stall a user's prompt.
    refreshInBackground(session.agentName, scope);
    if (session.ended) return {};
    const guidelines = capGuidelines(strategic.get(memoryKey(session.agentName, scope)) ?? [], session.tactical, config.maxGuidelines);
    if (!guidelines.length) return {};
    while (guidelines.length && formatGuidelinesBlock(guidelines).length > config.maxPromptChars!) guidelines.pop();
    if (!guidelines.length) return {};
    const block = formatGuidelinesBlock(guidelines);
    return config.injectMode === "prepend_context" ? { prependContext: block } : { appendSystemContext: block };
  });

  api.on("llm_input", (event, ctx) => {
    const trace = getTrace({ ...ctx, runId: event.runId, sessionId: event.sessionId });
    if (trace) trace.systemPrompt = event.systemPrompt ?? "";
  });

  api.on("llm_output", (event, ctx) => {
    const trace = getTrace({ ...ctx, runId: event.runId, sessionId: event.sessionId });
    if (trace) trace.modelOutput = event.assistantTexts.join("\n");
  });

  api.on("before_tool_call", (event, ctx) => {
    const trace = getTrace({ ...ctx, runId: event.runId ?? ctx.runId });
    if (trace && trace.tools.length < 100) trace.tools.push(`[tool: ${event.toolName}] ${extractText(event.params).slice(0, 500)}`);
  });

  api.on("after_tool_call", (event, ctx) => {
    const trace = getTrace({ ...ctx, runId: event.runId ?? ctx.runId });
    if (!trace) return;
    if (event.error) trace.error = event.error.slice(0, 1000);
    const output = extractText(event.result);
    if (output && trace.observations.length < 100) trace.observations.push(output.slice(0, 1000));
  });

  api.on("agent_end", async (event, ctx) => {
    const identity = { ...ctx, runId: event.runId ?? ctx.runId };
    const key = traceKey(identity);
    const trace = getTrace(identity);
    if (!key || !trace) return;
    traces.delete(key);
    if (trace.session.ended || trace.scopeChanged || !sidecar.compatible || (!event.messages.length && !trace.modelOutput && !event.error)) return;
    const messages = messagesFrom(event.messages);
    const latestUser = messages.filter((m) => m.role === "user").at(-1);
    const lastAssistant = messages.filter((m) => m.role === "assistant").at(-1);
    const history = messages.filter((m) => m.role === "user" || m.role === "assistant").slice(-12, -2)
      .map((m) => `[${m.role}]: ${extractText(m.content).slice(0, 300)}`).join("\n");
    steps++;
    const result = await client.onStepComplete({
      agent_name: trace.session.agentName, agent_role: "OpenClaw AI Assistant",
      task: (trace.prompt || extractText(latestUser?.content) || `Session ${trace.session.taskId}: agent task`).slice(0, 2000),
      model_output: (trace.modelOutput || extractText(lastAssistant?.content)).slice(-48_000),
      tool_calls: trace.tools.length ? trace.tools.join("\n---\n").slice(-24_000) : undefined,
      observations: trace.observations.length ? trace.observations.join("\n---\n").slice(-24_000) : undefined,
      error: (event.error || trace.error)?.slice(0, 4_000), current_system_prompt: trace.systemPrompt.slice(0, 64_000),
      task_id: trace.session.taskId, conversation_history: history || undefined,
      scope: trace.session.scope,
    });
    if (result?.guideline && !result.skipped && !trace.session.ended) {
      synthesized++;
      if (result.guideline_type === "strategic") {
        await refreshRules(trace.session.agentName, trace.session.scope);
      } else {
        trace.session.tactical.push({ text: result.guideline, type: "tactical", guidelineId: result.guideline_id });
        trace.session.tactical = trace.session.tactical.slice(-config.maxGuidelines);
      }
      api.logger.info(`evolveclaw: learned ${result.guideline_type ?? "tactical"} guideline (synthesized=${synthesized})`);
    }
    if (steps % 5 === 0) api.logger.info(`evolveclaw: [stats] steps=${steps} synthesized=${synthesized} sessions=${sessions.size}`);
  });

  api.on("session_end", async (event, ctx) => {
    const key = sessionKey({ ...ctx, sessionId: event.sessionId, sessionKey: event.sessionKey ?? ctx.sessionKey });
    for (const [storedKey, session] of sessions) {
      if (session.identityKey !== key) continue;
      session.ended = true;
      sessions.delete(storedKey);
      for (const [runKey, trace] of traces) if (trace.session === session) traces.delete(runKey);
      await client.resetTactical(session.agentName, session.taskId, session.scope);
    }
  });
  api.logger.info(`evolveclaw: registered (agent=${config.agentName}, inject=${config.injectMode})`);
}

export default definePluginEntry({
  id: "evolveclaw", name: "EvolveClaw", description: "SCOPE prompt evolution for OpenClaw",
  register,
});
