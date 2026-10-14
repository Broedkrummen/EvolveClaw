import { createHash } from "node:crypto";
import { readFile, mkdir, writeFile, rename } from "node:fs/promises";
import { resolve } from "node:path";
import type { MemoryScope } from "./types.js";

export type TrustedContext = {
  agentId?: string; sessionId?: string; sessionKey?: string;
  memoryAudience?: { kind: "owner-private"; agentId: string } |
    { kind: "conversation"; agentId: string; sessionKey: string; sessionId: string };
  activeProjectKeys?: readonly string[];
  assertMemoryAudienceCurrent?: () => void;
};
export type ScopeBinding = { id: string; agentName: string; agentId: string; sessionKey?: string;
  sessionId?: string; scope: MemoryScope; label: string };

export function scopeFromContext(ctx: TrustedContext): MemoryScope | undefined {
  const audience = ctx.memoryAudience;
  if (!audience || audience.agentId !== (ctx.agentId ?? "main")) return undefined;
  ctx.assertMemoryAudienceCurrent?.();
  // These are host-prepared identities, never inferred from a path or user text.
  const audience_key = audience.kind === "owner-private"
    ? JSON.stringify([audience.kind, audience.agentId])
    : JSON.stringify([audience.kind, audience.agentId, audience.sessionKey, audience.sessionId]);
  const projects = [...new Set(ctx.activeProjectKeys ?? [])].sort();
  const bounded = (value: string) => value.length <= 256 ? value : `sha256:${createHash("sha256").update(value).digest("hex")}`;
  return { audience_key: bounded(audience_key), project_key: projects.length ? bounded(JSON.stringify(projects)) : "@no-project" };
}

/** Stored labels for owner/operator management, not live memory authorization. */
export class ScopeRegistry {
  private bindings = new Map<string, ScopeBinding>();
  private sessions = new Map<string, string>();
  private path?: string;
  private writes = Promise.resolve();
  private saveError?: Error;

  constructor(private onSaveError?: () => void) {}

  async start(stateDir: string): Promise<void> {
    this.path = resolve(stateDir, "evolveclaw", "scopes.json");
    try {
      const data: unknown = JSON.parse(await readFile(this.path, "utf8"));
      const rows = Array.isArray(data) ? data : (data as { bindings?: unknown[] })?.bindings;
      if (Array.isArray(rows)) for (const b of rows) {
        if (b && typeof b.id === "string" && typeof b.agentName === "string" && typeof b.agentId === "string"
          && typeof b.scope?.audience_key === "string" && typeof b.scope?.project_key === "string") this.bindings.set(b.id, b);
      }
      const associations = !Array.isArray(data) && (data as { sessions?: unknown })?.sessions;
      if (Array.isArray(associations)) for (const pair of associations) {
        if (Array.isArray(pair) && pair.length === 2 && pair.every(v => typeof v === "string") && this.bindings.has(pair[1])) this.sessions.set(pair[0], pair[1]);
      }
      for (const b of this.bindings.values()) this.rememberSession(b.agentId, b.sessionKey, b.sessionId, b.id);
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw new Error("Recorded memory scopes could not be read.");
    }
  }

  capture(ctx: TrustedContext, agentName: string, scope: MemoryScope): ScopeBinding {
    const id = createHash("sha256").update(JSON.stringify([agentName, scope])).digest("hex").slice(0, 24);
    const b: ScopeBinding = { id, agentName, agentId: ctx.agentId ?? "main", sessionId: ctx.sessionId,
      sessionKey: ctx.sessionKey, scope,
      label: `${scope.project_key === "@no-project" ? "Everyday tasks" : (ctx.activeProjectKeys ?? []).join(", ")} · ${ctx.memoryAudience?.kind === "conversation" ? "This conversation" : "Owner private"}` };
    const unchanged = JSON.stringify(this.bindings.get(id)) === JSON.stringify(b);
    const changedSession = this.rememberSession(b.agentId, b.sessionKey, b.sessionId, id);
    if (unchanged && !changedSession) return b;
    this.bindings.delete(id); // Revisit of a scope becomes the latest recorded label.
    this.bindings.set(id, b);
    this.persist();
    return b;
  }

  list(agentId: string): ScopeBinding[] { return [...this.bindings.values()].filter(b => b.agentId === agentId); }
  get(id: string, agentId: string): ScopeBinding | undefined { const b = this.bindings.get(id); return b?.agentId === agentId ? b : undefined; }
  forSession(agentId: string, sessionKey?: string, sessionId?: string): ScopeBinding | undefined {
    const key = sessionId ? JSON.stringify([agentId, "id", sessionId]) : sessionKey ? JSON.stringify([agentId, "key", sessionKey]) : undefined;
    const id = key ? this.sessions.get(key) : undefined;
    return id ? this.get(id, agentId) : undefined;
  }
  private rememberSession(agentId: string, sessionKey: string | undefined, sessionId: string | undefined, id: string): boolean {
    let changed = false;
    for (const [kind, value] of [["id", sessionId], ["key", sessionKey]]) {
      if (!value) continue;
      const key = JSON.stringify([agentId, kind, value]);
      if (this.sessions.get(key) !== id) { this.sessions.set(key, id); changed = true; }
    }
    return changed;
  }
  private persist(): void {
    if (!this.path) return;
    const path = this.path, body = JSON.stringify({ bindings: [...this.bindings.values()], sessions: [...this.sessions.entries()] });
    this.writes = this.writes.then(async () => {
      await mkdir(resolve(path, ".."), { recursive: true });
      await writeFile(`${path}.tmp`, body, { mode: 0o600 });
      await rename(`${path}.tmp`, path);
      this.saveError = undefined;
    }).catch(error => { this.saveError = error as Error; this.onSaveError?.(); });
  }
  async flush(): Promise<void> { await this.writes; if (this.saveError) throw this.saveError; }
}
