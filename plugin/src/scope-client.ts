import type {
  ConfigureRequest,
  ConfigureResponse,
  HealthResponse,
  RulesResponse,
  StatsResponse,
  StepCompleteRequest,
  StepCompleteResponse,
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

  constructor(baseUrl: string, timeoutMs = 10_000) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
    this.timeoutMs = timeoutMs;
  }

  async health(): Promise<HealthResponse | null> {
    return this.get<HealthResponse>("/health", 1_000);
  }

  async getStrategicRules(agentName: string): Promise<RulesResponse | null> {
    return this.get<RulesResponse>(`/rules/${encodeURIComponent(agentName)}`);
  }

  async onStepComplete(req: StepCompleteRequest): Promise<StepCompleteResponse | null> {
    return this.post<StepCompleteResponse>("/step", req, 120_000);
  }

  async resetTactical(agentName: string, taskId?: string): Promise<void> {
    await this.post("/reset", { agent_name: agentName, task_id: taskId });
  }

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
        signal,
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
        headers: { "Content-Type": "application/json" },
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
