import type {
  ConfigureRequest,
  ConfigureResponse,
  HealthResponse,
  RulesResponse,
  StatsResponse,
  StepCompleteRequest,
  StepCompleteResponse,
  MemoryScope,
  MemorySnapshot,
} from "./types.js";

/**
 * HTTP client for the SCOPE sidecar server.
 *
 * All methods are fire-and-forget safe — they catch errors internally
 * so a SCOPE server outage never crashes the OpenClaw agent loop.
 */
export class ScopeClient {
  private baseUrl: string;
  private timeoutMs: number;

  constructor(baseUrl: string, timeoutMs = 10_000, private token?: string) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
    this.timeoutMs = timeoutMs;
  }

  async health(): Promise<HealthResponse | null> {
    return this.get<HealthResponse>("/health", 1_000);
  }

  async getStrategicRules(agentName: string, scope?: MemoryScope): Promise<RulesResponse | null> {
    const query = scope ? `?${new URLSearchParams(scope)}` : "";
    return this.get<RulesResponse>(`/rules/${encodeURIComponent(agentName)}${query}`);
  }

  async onStepComplete(req: StepCompleteRequest): Promise<StepCompleteResponse | null> {
    return this.post<StepCompleteResponse>("/step", req, 120_000);
  }

  async resetTactical(agentName: string, taskId?: string, scope?: MemoryScope): Promise<void> {
    await this.post("/reset", { agent_name: agentName, task_id: taskId, ...(scope ? { scope } : {}) });
  }

  async memory(agentName: string, scope: MemoryScope, operation: string,
    args: Record<string, unknown> = {}, expectedRevision?: number, authorizeLegacy = false): Promise<MemorySnapshot> {
    const res = await fetch(`${this.baseUrl}/memory/${expectedRevision === undefined ? "query" : "mutate"}`, {
      method: "POST", signal: AbortSignal.timeout(this.timeoutMs),
      headers: { "Content-Type": "application/json", ...this.headers() },
      body: JSON.stringify({ agent_name: agentName, scope, operation, args,
        ...(expectedRevision === undefined ? {} : { expected_revision: expectedRevision }), authorize_legacy: authorizeLegacy }),
    });
    if (!res.ok) {
      throw new Error(res.status === 409 ? "Memory changed or the requested change is not eligible. Refresh and review it again."
        : res.status === 403 ? "You do not have permission to change this memory."
          : res.status === 404 ? "That rule or change is unavailable in the selected scope." : "Memory service is unavailable. Try refreshing.");
    }
    return await res.json() as MemorySnapshot;
  }

  private headers(): Record<string, string> { return this.token ? { Authorization: `Bearer ${this.token}` } : {}; }

  async configure(req: ConfigureRequest): Promise<ConfigureResponse | null> {
    return this.post<ConfigureResponse>("/configure", req);
  }

  async getStats(agentName: string): Promise<StatsResponse | null> {
    return this.get<StatsResponse>(`/stats/${encodeURIComponent(agentName)}`);
  }

  // ── Internal helpers ──

  private async get<T>(path: string, timeoutMs = this.timeoutMs): Promise<T | null> {
    const signal = AbortSignal.timeout(timeoutMs);
    try {
      const res = await fetch(`${this.baseUrl}${path}`, {
        signal, headers: this.headers(),
      });
      if (!res.ok) return null;
      return (await res.json()) as T;
    } catch {
      return null;
    }
  }

  private async post<T>(path: string, body: unknown, timeoutMs = this.timeoutMs): Promise<T | null> {
    const signal = AbortSignal.timeout(timeoutMs);
    try {
      const res = await fetch(`${this.baseUrl}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...this.headers() },
        body: JSON.stringify(body),
        signal,
      });
      if (!res.ok) return null;
      return (await res.json()) as T;
    } catch {
      return null;
    }
  }
}
