import { execFile, spawn, type ChildProcess } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import type { OpenClawPluginApi } from "openclaw/plugin-sdk/plugin-entry";
import type { EvolveClawConfig, ConfigureRequest } from "./types.js";
import type { ScopeClient } from "./scope-client.js";

const execute = promisify(execFile);
const API_PROVIDERS: Record<string, string> = {
  "anthropic-messages": "anthropic", "openai-completions": "openai", "openai-responses": "openai",
  "openai-codex-responses": "openai",
};

export async function modelConfiguration(api: OpenClawPluginApi, config: EvolveClawConfig): Promise<ConfigureRequest | null> {
  const cfg = api.config;
  const rawModel = cfg.agents?.defaults?.model;
  const modelRef = typeof rawModel === "string" ? rawModel : rawModel?.primary;
  const slash = modelRef?.indexOf("/") ?? -1;
  let selected: { provider: string; model: string } | undefined;
  try { selected = api.runtime.modelConfig.resolveDefaultModelForAgent({ cfg }); } catch { /* Test/custom runtimes can omit this helper. */ }
  const providerName = selected?.provider ?? (slash >= 0 ? modelRef!.slice(0, slash) : "");
  const providerConfig = cfg.models?.providers?.[providerName];
  const model = config.scopeModel ?? selected?.model ?? (slash >= 0 ? modelRef!.slice(slash + 1).replace(/@[^@/]+$/, "") : undefined);
  const provider = config.scopeProvider ?? API_PROVIDERS[providerConfig?.api ?? ""] ??
    (providerName === "anthropic" ? "anthropic" : providerName === "openai" ? "openai" : "litellm");
  let key = config.scopeApiKey;
  if (!key && providerName) {
    // Use the supported auth resolver for plaintext, environment, profile and SecretRef credentials.
    try {
      const auth = await api.runtime.modelAuth.resolveApiKeyForProvider({ provider: providerName, cfg });
      // OAuth login tokens are not transferable API credentials for the sidecar adapters.
      if (auth.mode !== "oauth" && auth.mode !== "aws-sdk") key = auth.apiKey;
    } catch { /* An explicit sidecar environment or plugin override can supply credentials instead. */ }
  }
  if (!key || !model) return null;
  return { provider, model, api_key: key, base_url: config.scopeBaseUrl ?? providerConfig?.baseUrl };
}

export class Sidecar {
  private child?: ChildProcess;
  private stopping = false;
  private configuring?: Promise<void>;
  private stateDir?: string;
  private generation = 0;
  private starting?: Promise<void>;
  compatible = false;
  private warnedIncompatible = false;

  constructor(private api: OpenClawPluginApi, private client: ScopeClient, private config: EvolveClawConfig) {}

  async configureIfNeeded(force = false): Promise<void> {
    if (this.stopping) return;
    if (!this.configuring) {
      this.configuring = this.configure(force).catch(() => {
        this.api.logger.warn("evolveclaw: sidecar configuration unavailable; retrying on the next turn");
      }).finally(() => { this.configuring = undefined; });
    }
    await this.configuring;
  }

  private async configure(force: boolean): Promise<void> {
    const generation = this.generation;
    const health = await this.client.health();
    if (this.stopping || generation !== this.generation) return;
    if (!health) return;
    this.compatible = health.protocol_version === 2;
    if (!this.compatible) {
      if (!this.warnedIncompatible) this.api.logger.warn("evolveclaw: incompatible old sidecar; stop it with its own process manager and start the updated server (protocol 2 required)");
      this.warnedIncompatible = true;
      return;
    }
    this.warnedIncompatible = false;
    // Check on every turn so a restarted or previously unreachable sidecar can recover.
    if (health.configured && !force) return;
    const req = await modelConfiguration(this.api, this.config);
    if (this.stopping || generation !== this.generation) return;
    if (!req) {
      this.api.logger.warn("evolveclaw: no compatible synthesis credentials; configure the sidecar environment or SCOPE overrides");
      return;
    }
    const result = await this.client.configure(req);
    if (result?.status !== "ok" && result?.status !== "skipped") this.api.logger.warn("evolveclaw: sidecar rejected configuration; retrying on the next turn");
  }

  private pluginRoot(): string {
    if (this.api.rootDir) return this.api.rootDir;
    let directory = dirname(fileURLToPath(import.meta.url));
    for (let depth = 0; depth < 4; depth++) {
      if (existsSync(resolve(directory, "openclaw.plugin.json"))) return directory;
      directory = dirname(directory);
    }
    throw new Error("EvolveClaw package root not found");
  }

  private async python(serverDir: string): Promise<string> {
    const managedPython = resolve(this.stateDir!, "evolveclaw", "venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
    const candidates = this.config.pythonPath ? [this.config.pythonPath] : [
      managedPython, resolve(serverDir, "venv/bin/python"), resolve(serverDir, ".venv/bin/python"), "python3", "python",
    ];
    for (const candidate of candidates) {
      try {
        await execute(candidate, ["-c", "import scope, fastapi, uvicorn, anthropic, dotenv; from importlib.metadata import version; assert version('scope-optimizer') == '0.1.3'"], { timeout: 10_000 });
        return candidate;
      } catch { /* Try an existing configured environment before creating one. */ }
    }
    const base = this.config.pythonPath ?? "python3";
    const environment = resolve(this.stateDir!, "evolveclaw", "venv");
    await mkdir(dirname(environment), { recursive: true });
    await execute(base, ["-m", "venv", environment], { timeout: 30_000 });
    const python = resolve(environment, process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
    await execute(python, ["-m", "pip", "install", "-r", resolve(serverDir, "requirements.txt")], { timeout: 120_000 });
    return python;
  }

  async start(stateDir: string): Promise<void> {
    if (this.starting) return this.starting;
    const generation = ++this.generation;
    const starting = this.startOnce(stateDir, generation).finally(() => {
      if (this.starting === starting) this.starting = undefined;
    });
    this.starting = starting;
    return starting;
  }

  private async startOnce(stateDir: string, generation: number): Promise<void> {
    this.stopping = false;
    this.stateDir = stateDir;
    if (!await this.client.health() && this.config.autoStartServer) {
      try {
        const url = new URL(this.config.serverUrl);
        if (!['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname) || url.protocol !== "http:" || url.pathname !== "/") {
          this.api.logger.warn("evolveclaw: auto-start requires a local HTTP serverUrl; start the remote sidecar separately");
          return;
        }
        const serverDir = resolve(this.pluginRoot(), "server");
        const python = await this.python(serverDir);
        if (this.stopping || generation !== this.generation) return;
        const legacyData = resolve(serverDir, "scope_data");
        const dataPath = this.config.dataPath ? resolve(serverDir, this.config.dataPath) :
          (existsSync(legacyData) ? legacyData : resolve(stateDir, "evolveclaw", "scope_data"));
        await mkdir(dataPath, { recursive: true });
        if (this.stopping || generation !== this.generation) return;
        this.child = spawn(python, [resolve(serverDir, "server.py")], {
          cwd: serverDir, stdio: "ignore",
          env: { ...process.env, EVOLVECLAW_HOST: url.hostname === "[::1]" ? "::1" : url.hostname,
            EVOLVECLAW_PORT: url.port || "80", EVOLVECLAW_SCOPE_DATA_DEFAULT: dataPath,
            ...(this.config.dataPath ? { EVOLVECLAW_SCOPE_DATA: dataPath } : {}) },
        });
        this.child.on("error", () => this.api.logger.warn("evolveclaw: sidecar process failed to start"));
        const deadline = Date.now() + 15_000;
        while (!this.stopping && Date.now() < deadline) {
          if (await this.client.health()) break;
          if (this.child.exitCode !== null) break;
          await new Promise((r) => setTimeout(r, 250));
        }
        if (!await this.client.health()) this.api.logger.warn("evolveclaw: sidecar unavailable; agent continues and will retry configuration");
      } catch {
        this.api.logger.warn("evolveclaw: sidecar setup failed; run scripts/start-server.sh or configure pythonPath (Python venv support is required)");
      }
    }
    if (this.stopping || generation !== this.generation) return;
    await this.configureIfNeeded(true);
  }

  async stop(): Promise<void> {
    this.stopping = true;
    ++this.generation;
    this.starting = undefined;
    const child = this.child;
    this.child = undefined;
    if (!child || child.exitCode !== null || child.signalCode !== null) return;
    await new Promise<void>((done) => {
      const timeout = setTimeout(() => { child.kill("SIGKILL"); }, 5_000);
      child.once("exit", () => { clearTimeout(timeout); done(); });
      child.kill("SIGTERM");
    });
  }
}
