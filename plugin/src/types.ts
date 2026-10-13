// ── Plugin configuration ──

export type InjectMode = "append_system" | "prepend_context";

export type EvolveClawConfig = {
  serverUrl: string;
  agentName: string;
  enabled: boolean;
  injectMode: InjectMode;
  maxGuidelines: number;
  maxPromptChars?: number;
  sidecarToken?: string;
  scopeModel?: string;
  scopeProvider?: string;
  scopeApiKey?: string;
  scopeBaseUrl?: string;
  autoStartServer: boolean;
  pythonPath?: string;
  dataPath?: string;
};

// ── Guideline with metadata ──

export type GuidelineEntry = {
  text: string;
  type: "tactical" | "strategic";
  guidelineId?: string;
};

export type MemoryScope = { audience_key: string; project_key: string };
export type RuleRecord = { id: string; text: string; type: string; domain: string; status: string;
  confidence: number; revision: number; evidence_ids: string[]; created_at: string; updated_at: string;
  audience_key: string; project_key: string; task_id?: string };
export type HistoryRecord = { id: string; revision: number; operation: string; rule_ids: string[];
  created_at: string; summary: string; reversible?: boolean };
export type MemorySnapshot = { revision: number; paused: boolean; rules?: RuleRecord[];
  history?: HistoryRecord[]; usage?: Record<string, unknown>; detail?: unknown; evidence?: unknown; outcomes?: unknown };

// ── SCOPE sidecar API types ──

export type StepCompleteRequest = {
  agent_name: string;
  agent_role: string;
  task: string;
  model_output?: string;
  tool_calls?: string;
  observations?: string;
  error?: string;
  current_system_prompt: string;
  task_id?: string;
  conversation_history?: string;
  scope?: MemoryScope;
};

export type StepCompleteResponse = {
  guideline?: string;
  guideline_type?: "tactical" | "strategic";
  guideline_id?: string;
  skipped: boolean;
  reason?: string;
  revision?: number;
};

export type RulesResponse = {
  rules: string;
  rule_count: number;
  guidelines?: string[];
  configured?: boolean;
  revision?: number;
  paused?: boolean;
};

export type HealthResponse = {
  status: "ok" | "error";
  version: string;
  configured?: boolean;
  protocol_version?: number;
};

export type StatsResponse = {
  strategic_count: number;
  total_steps_analyzed: number;
  guidelines_synthesized: number;
  recent_synthesis_rate: number;
  uptime_seconds: number;
};

// ── SCOPE server configuration (forwarded from OpenClaw) ──

export type ConfigureRequest = {
  provider: string;
  model: string;
  api_key: string;
  base_url?: string;
};

export type ConfigureResponse = {
  status: "ok" | "skipped" | "error";
  reason?: string;
};
