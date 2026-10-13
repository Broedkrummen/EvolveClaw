// Sequential warm host for the exact installed agent-exec pipeline. This is an
// internal entry adapter, not a replacement agent loop or provider HTTP client.
import { createHash } from "node:crypto";
import { readFile, realpath } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

const VERSION = "2026.10.2";
const ENTRY = "agent-exec-DcSrtj25.mjs";
const ENTRY_SHA256 = "a638bf91efbd775ab4b2d66fd0d6e124074b6edcbad8f85a487e07dab25b8504";
const LIMIT = 4_000_000;
const protocolWrite = process.stdout.write.bind(process.stdout);
const emit = (value) => protocolWrite(JSON.stringify(value) + "\n");
// Native diagnostics can include private config/auth context. The protocol is
// the only stdout writer; no raw runtime diagnostic is forwarded to the host.
process.stdout.write = (_chunk, encoding, callback) => {
  const done = typeof encoding === "function" ? encoding : callback;
  done?.();
  return true;
};
process.stderr.write = (_chunk, encoding, callback) => {
  const done = typeof encoding === "function" ? encoding : callback;
  done?.();
  return true;
};
for (const method of ["log", "error", "warn", "info", "debug"]) console[method] = () => {};

let agentExecCommand;
let metadata;
let requestIndex = 0;
const resourceTypes = new Set(["Timeout", "Immediate", "FSReqCallback", "FileHandle",
  "PipeWrap", "TCPSocketWrap", "TCPServerWrap", "TTYWrap", "SignalWrap",
  "ProcessWrap", "MessagePort", "UDPWrap", "ConnectWrap", "WriteWrap"]);
function telemetry() {
  const memory = process.memoryUsage();
  const usage = process.resourceUsage();
  const active = {};
  for (const value of process.getActiveResourcesInfo()) {
    const kind = resourceTypes.has(value) ? value : "other";
    active[kind] = (active[kind] ?? 0) + 1;
  }
  return { pid: process.pid, parent_pid: process.ppid, request_index: requestIndex,
    rss_bytes: memory.rss, rss_high_water_bytes: usage.maxRSS * 1024,
    heap_total_bytes: memory.heapTotal, heap_used_bytes: memory.heapUsed,
    external_bytes: memory.external, array_buffers_bytes: memory.arrayBuffers,
    user_cpu_us: usage.userCPUTime, system_cpu_us: usage.systemCPUTime,
    voluntary_context_switches: usage.voluntaryContextSwitches,
    involuntary_context_switches: usage.involuntaryContextSwitches,
    active_resource_counts: active };
}
try {
  const cli = await realpath(process.argv[2]);
  const installation = path.dirname(cli);
  const pkg = JSON.parse(await readFile(path.join(installation, "package.json"), "utf8"));
  if (pkg.version !== VERSION || pkg.name !== "openclaw") throw new Error("version");
  const entryPath = path.join(installation, "dist", ENTRY);
  const digest = createHash("sha256").update(await readFile(entryPath)).digest("hex");
  if (digest !== ENTRY_SHA256) throw new Error("source");
  ({ agentExecCommand } = await import(pathToFileURL(entryPath).href));
  if (typeof agentExecCommand !== "function") throw new Error("entry");
  metadata = { openclaw_version: VERSION, entry_file: ENTRY, entry_source_sha256: digest,
    internal_entry: true, persistent_worker: true, model_requests_serialized: true };
  emit({ ready: true, metadata, telemetry: telemetry() });
} catch {
  emit({ ready: false, error_kind: "native-worker-version-or-source-admission" });
  process.exit(1);
}

async function execute(request) {
  if (!request || typeof request !== "object" || !Number.isSafeInteger(request.id) || request.id < 1) throw new Error("request");
  if (request.op === "close") return { id: request.id, closed: true };
  if (request.op !== "execute" || typeof request.prompt !== "string" || !request.prompt.trim()
      || typeof request.configPath !== "string" || typeof request.cwd !== "string"
      || typeof request.modelRef !== "string" || !Number.isSafeInteger(request.timeout) || request.timeout < 1) throw new Error("request");
  requestIndex += 1;
  // Emit before entering native code: abrupt process death still leaves safe
  // counters for the in-flight request. Never emit prompt/config/auth data.
  emit({ id: request.id, event: "request-started", telemetry: telemetry() });
  let captured;
  const runtime = {
    log: () => {}, error: () => {}, writeStdout: () => {},
    writeJson: (value) => { captured = value; },
    exit: () => { throw new Error("runtime-exit"); },
  };
  // Positional prompt stays inside process memory. The same native function
  // owns temporary state, stored-auth admission, run config, and full cleanup.
  const result = await agentExecCommand(request.prompt, {
    config: request.configPath, cwd: request.cwd, model: request.modelRef,
    codeMode: "direct", thinking: "off", timeout: String(request.timeout),
    json: true, fallback: [],
  }, runtime);
  const envelope = result?.envelope ?? captured;
  if (!envelope || typeof envelope !== "object") throw new Error("envelope");
  if (!envelope.ok) {
    // Drop error strings/payloads entirely; the Python adapter preserves known
    // usage without exposing the native diagnostics or retrying this request.
    return { id: request.id, exitCode: result?.exitCode ?? 1, metadata, telemetry: telemetry(),
      envelope: { ok: false, status: envelope.status === "timeout" ? "timeout" : "error",
        final: "", usage: envelope.usage, provider: envelope.provider, model: envelope.model,
        assistantTurns: envelope.assistantTurns, toolSummary: envelope.toolSummary } };
  }
  return { id: request.id, exitCode: result?.exitCode ?? 0, metadata, telemetry: telemetry(),
    envelope: Object.fromEntries(["ok", "status", "final", "usage", "provider", "model",
      "assistantTurns", "toolSummary"].filter((key) => envelope[key] !== undefined).map((key) => [key, envelope[key]])) };
}

let buffer = Buffer.alloc(0);
for await (const chunk of process.stdin) {
  buffer = Buffer.concat([buffer, chunk]);
  if (buffer.length > LIMIT) { emit({ error_kind: "native-worker-request-too-large" }); process.exit(1); }
  let newline;
  while ((newline = buffer.indexOf(10)) >= 0) {
    const line = buffer.subarray(0, newline);
    buffer = buffer.subarray(newline + 1);
    let request;
    try {
      request = JSON.parse(line.toString("utf8"));
      const result = await execute(request);
      emit(result);
      if (result.closed) process.exit(0);
    } catch {
      emit({ id: Number.isSafeInteger(request?.id) ? request.id : null,
        error_kind: "native-worker-request-failed", telemetry: telemetry() });
    }
  }
}
if (buffer.length) emit({ error_kind: "native-worker-incomplete-request" });
