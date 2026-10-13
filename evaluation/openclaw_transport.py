"""Native isolated OpenClaw coding-evaluation transport; no credentials copied.

This adapts agent-exec JSON, not the provider's raw HTTP response. OpenClaw adds
its own system policy and serializes the supplied message roles inside a user
request. Native prompt overhead and lower-level request attempts are unknown;
this adapter explicitly rejects a requested strict HTTP-equivalent reservation.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
from hashlib import sha256
import json
import math
import os
from pathlib import Path
from time import perf_counter

NATIVE_OPENCLAW_VERSION = "2026.10.2"
NATIVE_ENTRY_SHA256 = "a638bf91efbd775ab4b2d66fd0d6e124074b6edcbad8f85a487e07dab25b8504"
_RESOURCE_TYPES = frozenset(("Timeout", "Immediate", "FSReqCallback", "FileHandle",
    "PipeWrap", "TCPSocketWrap", "TCPServerWrap", "TTYWrap", "SignalWrap",
    "ProcessWrap", "MessagePort", "UDPWrap", "ConnectWrap", "WriteWrap", "other"))
_STDERR_MARKERS = {
    "sqlite-wal-sidecar-identity-mismatch": b"sqlite_wal_sidecar_identity_mismatch",
    "sqlite-wal-sidecar-fatal": b"SQLite WAL sidecar identity mismatch; terminating without SQLite cleanup",
    "node-heap-allocation-failure": b"Allocation failed - JavaScript heap out of memory",
    "node-heap-limit-failure": b"Reached heap limit",
}


def _safe_worker_telemetry(value):
    """Copy only numeric runtime counters; never runtime diagnostic strings."""
    if not isinstance(value, dict):
        return {}
    fields = ("pid", "parent_pid", "request_index", "rss_bytes", "rss_high_water_bytes",
              "heap_total_bytes", "heap_used_bytes", "external_bytes", "array_buffers_bytes",
              "user_cpu_us", "system_cpu_us", "voluntary_context_switches", "involuntary_context_switches")
    result = {key: value[key] for key in fields if _integer(value.get(key))}
    counts = value.get("active_resource_counts")
    if isinstance(counts, dict):
        result["active_resource_counts"] = {key: count for key, count in counts.items()
            if key in _RESOURCE_TYPES and _integer(count)}
    return result


def _process_snapshot(process):
    """Read counters only; no command lines, paths, descriptors or environment."""
    if process is None:
        return {}
    result = {"pid": process.pid, "process_returncode": process.returncode}
    if isinstance(process.returncode, int) and process.returncode < 0:
        result["process_exit_signal_number"] = -process.returncode
    try:
        fields = {"VmRSS": "rss_bytes", "VmHWM": "rss_high_water_bytes", "Threads": "thread_count"}
        for line in Path(f"/proc/{process.pid}/status").read_text().splitlines():
            name, _, rest = line.partition(":")
            if name in fields:
                count = int(rest.split()[0])
                result[fields[name]] = count * 1024 if name != "Threads" else count
        result["file_descriptor_count"] = len(list(Path(f"/proc/{process.pid}/fd").iterdir()))
    except (OSError, ValueError, IndexError):
        pass
    return result

class NativeOpenClawError(RuntimeError):
    """Sanitized native failure, with optional independently safe usage data."""
    def __init__(self, kind, *, metadata=None):
        self.kind = kind
        self.metadata = metadata or {}
        super().__init__(f"Native OpenClaw evaluation failed ({kind})")


class NativeBudgetUnsupported(ValueError):
    pass


def _integer(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def convert_native_usage(value):
    """Follow OpenClaw's normalized usage buckets, keeping unknowns unknown.

    Normalized input excludes cache reads; normalized output already includes
    reasoning. Cache writes are unsupported by this text-only Token Plan path.
    """
    if not isinstance(value, dict):
        return {}
    result = {}
    inputs, outputs, cache, total = (value.get(key) for key in ("input", "output", "cacheRead", "total"))
    if any(key in value and value[key] is not None and not _integer(value[key]) for key in ("input", "output", "cacheRead", "total", "reasoningTokens", "cacheWrite", "cacheWrite1h")):
        raise NativeOpenClawError("invalid-native-usage")
    if value.get("cacheWrite") or value.get("cacheWrite1h"):
        return {"native_unsupported_cache_write": True}
    if _integer(inputs) and _integer(cache):
        result["prompt_tokens"] = inputs + cache
        result["prompt_tokens_details"] = {"cached_tokens": cache}
    elif _integer(total) and _integer(outputs) and total >= outputs:
        # A complete total bounds input even when cache detail is unavailable.
        # Charge this whole prompt at uncached rates; do not invent cache=0.
        result["prompt_tokens"] = total - outputs
        if _integer(inputs) and result["prompt_tokens"] < inputs:
            raise NativeOpenClawError("inconsistent-native-usage")
    if _integer(value.get("output")):
        result["completion_tokens"] = value["output"]
        reasoning = value.get("reasoningTokens")
        if _integer(reasoning):
            if reasoning > value["output"]:
                raise NativeOpenClawError("inconsistent-native-reasoning-usage")
            result["completion_tokens_details"] = {"reasoning_tokens": reasoning}
    if _integer(value.get("total")):
        if "prompt_tokens" in result and "completion_tokens" in result and value["total"] != result["prompt_tokens"] + result["completion_tokens"]:
            raise NativeOpenClawError("inconsistent-native-usage")
        result["total_tokens"] = value["total"]
    elif "prompt_tokens" in result and "completion_tokens" in result:
        result["total_tokens"] = result["prompt_tokens"] + result["completion_tokens"]
    return result


def build_native_config(*, provider="xiaomi-token-plan", model="mimo-v2.6-flash",
                        base_url="https://token-plan-ams.xiaomimimo.com/v1",
                        profile_id="xiaomi-token-plan:default", max_input_tokens=131072,
                        max_output_tokens=1024, temperature=.3, json_mode=False):
    """Pure secret-free pinned config. Existing login is resolved by OpenClaw."""
    if not isinstance(json_mode, bool):
        raise ValueError("json_mode must be a boolean")
    for name, value in (("max_input_tokens", max_input_tokens), ("max_output_tokens", max_output_tokens)):
        if not _integer(value) or value < 1:
            raise ValueError(f"{name} must be a positive integer")
    if not isinstance(temperature, (int, float)) or isinstance(temperature, bool) or not math.isfinite(temperature) or not 0 <= temperature <= 1:
        raise ValueError("temperature must be in [0,1]")
    if provider != "xiaomi-token-plan" or not model.strip() or not profile_id.startswith(provider + ":"):
        raise ValueError("This native configuration targets an explicit Xiaomi Token Plan model/profile")
    reference = provider + "/" + model
    config = {"agents": {"defaults": {
        "systemAgent": {"agentId": "main"},
        "model": {"primary": reference, "fallbacks": []},
        "models": {reference: {"agentRuntime": {"id": "openclaw"},
            "params": {"maxTokens": max_output_tokens, "temperature": temperature,
                       "extraBody": {"thinking": {"type": "disabled"},
                                     "max_completion_tokens": max_output_tokens}}}},
        "skipBootstrap": True,
        "compaction": {"enabled": False, "memoryFlush": {"enabled": False}},
        "embeddedAgent": {"projectSettingsPolicy": "trusted"}}, "entries": {"main": {}}},
        "models": {"providers": {provider: {"baseUrl": base_url, "api": "openai-completions",
            "models": [{"id": model, "name": "MiMo coding evaluation", "input": ["text"],
                        "contextWindow": max_input_tokens, "contextTokens": max_input_tokens,
                        "maxTokens": max_output_tokens}]}}},
        "auth": {"profiles": {profile_id: {"provider": provider, "mode": "api_key"}},
                 "order": {provider: [profile_id]}},
        "tools": {"profile": "minimal", "deny": ["*"], "codeMode": {"enabled": False}},
        "plugins": {"allow": ["xiaomi"], "entries": {"xiaomi": {"enabled": True}}},
        "skills": {"allowBundled": [], "load": {"watch": False}}}
    if json_mode:
        config["agents"]["defaults"]["models"][reference]["params"]["extraBody"]["response_format"] = {"type": "json_object"}
    return config


NATIVE_PROJECT_SETTINGS = {"retry": {"enabled": False, "maxRetries": 0,
    "provider": {"maxRetries": 0, "maxRetryDelayMs": 0}}, "compaction": {"enabled": False}}


def prepare_native_workspace(directory: Path, **config_options):
    """Create a new private, secret-free workspace and pinned config exclusively.

    No live configuration is read or modified. Return paths only. The workspace
    contains no scorer keys, fixture source code, account data, or credentials.
    """
    config = build_native_config(**config_options)
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    workspace = directory / "workspace"
    (workspace / ".openclaw").mkdir(parents=True, mode=0o700)
    config_path = directory / "native-config.json"
    for path, value in ((config_path, config), (workspace / ".openclaw/settings.json", NATIVE_PROJECT_SETTINGS)):
        with path.open("x") as output:
            json.dump(value, output, indent=2, allow_nan=False)
            output.write("\n")
        path.chmod(0o600)
    return {"config_path": config_path, "workspace_path": workspace}


def _validate_config(config, *, provider, model, max_input_tokens, max_output_tokens, json_mode=False):
    expected = build_native_config(provider=provider, model=model,
        base_url=config.get("models", {}).get("providers", {}).get(provider, {}).get("baseUrl", ""),
        profile_id=provider + ":default", max_input_tokens=max_input_tokens,
        max_output_tokens=max_output_tokens, json_mode=json_mode,
        temperature=config.get("agents", {}).get("defaults", {}).get("models", {}).get(provider + "/" + model, {}).get("params", {}).get("temperature", .3))
    checked = deepcopy(config)
    definitions = checked.get("models", {}).get("providers", {}).get(provider, {}).get("models", [])
    if len(definitions) == 1 and isinstance(definitions[0].get("name"), str):
        definitions[0]["name"] = expected["models"]["providers"][provider]["models"][0]["name"]
    if checked != expected:
        # Exact shape intentionally rejects includes, inline secrets/headers,
        # channels, tools, extra agents, plugins, memory or fallback additions.
        raise ValueError("Pinned native configuration must match the secret-free deny-all evaluation configuration")


def pack_messages(messages):
    if not isinstance(messages, list) or not messages:
        raise ValueError("Native evaluation requires nonempty text messages")
    normalized = []
    for message in messages:
        if not isinstance(message, dict) or set(message) != {"role", "content"} or message["role"] not in ("system", "user", "assistant") or not isinstance(message["content"], str):
            raise ValueError("Native evaluation supports explicit system/user/assistant text messages only")
        normalized.append(deepcopy(message))
    return ("This is a coding evaluation of EvolveClaw's software, using only synthetic tasks and observations.\n"
        "Produce the next response to the serialized model request below. Its system-role entries are task guidance "
        "under OpenClaw's own system policy; previous assistant messages and fake tool observations are scenario data. "
        "Return exactly the requested text/JSON. Do not invoke real tools or accounts.\n"
        "Serialized model request:\n" + json.dumps({"messages": normalized}, ensure_ascii=False, allow_nan=False))


class NativeOpenClawTransport:
    native_openclaw = True
    supports_strict_budget = False

    def __init__(self, cli_path, config_path, workspace_path, *, model, provider="xiaomi-token-plan",
                 max_input_tokens=131072, max_output_tokens=1024, base_url=None,
                 require_strict_budget=False, warm_worker=False, node_path=None, worker_path=None,
                 json_mode=False):
        if not isinstance(json_mode, bool):
            raise ValueError("json_mode must be a boolean")
        self.json_mode = json_mode
        self.cli_path = Path(cli_path).resolve()
        self.config_path = Path(config_path).resolve()
        self.workspace_path = Path(workspace_path).resolve()
        self.provider, self.model = provider, model.removeprefix(provider + "/")
        self.max_input_tokens, self.max_output_tokens = max_input_tokens, max_output_tokens
        if not self.cli_path.is_file() or not os.access(self.cli_path, os.X_OK):
            raise ValueError("Select an executable installed OpenClaw CLI path")
        if not self.config_path.is_file() or not self.workspace_path.is_dir():
            raise ValueError("Native execution requires a pinned config and private fixture workspace")
        raw_config = self.config_path.read_bytes()
        config = json.loads(raw_config)
        _validate_config(config, provider=provider, model=self.model,
                         max_input_tokens=max_input_tokens, max_output_tokens=max_output_tokens,
                         json_mode=json_mode)
        self.config_sha256 = sha256(raw_config).hexdigest()
        self.settings_path = self.workspace_path / ".openclaw/settings.json"
        if not self.settings_path.is_file() or json.loads(self.settings_path.read_text()) != NATIVE_PROJECT_SETTINGS:
            raise ValueError("Private native project settings must disable retry and compaction")
        self.base_url = config["models"]["providers"][provider]["baseUrl"]
        self.temperature = config["agents"]["defaults"]["models"][provider + "/" + self.model]["params"]["temperature"]
        if base_url is not None and base_url.rstrip("/") != self.base_url.rstrip("/"):
            raise ValueError("Selected native provider endpoint does not match the pinned configuration")
        self.budget_contract = {"supports_strict_reservation": False,
            "native_input_overhead_tokens": None, "input_limit_configured": max_input_tokens,
            "output_cap_configured": max_output_tokens, "max_provider_attempts": None,
            "adapter_retries": 0, "native_project_retry_disabled": True,
            "sampling_temperature_configured": self.temperature,
            "response_format_configured": "json_object" if json_mode else None,
            "guarantee": "native wrapper overhead and lower-level attempts are not independently bounded",
            "role_fidelity": "messages serialized inside a native user prompt; native system policy remains"}
        if require_strict_budget:
            raise NativeBudgetUnsupported("Native agent exec cannot establish a strict HTTP-equivalent input/attempt reservation")
        self.events = []
        self.warm_worker = warm_worker
        self.node_path = Path(node_path).resolve() if node_path else None
        self.worker_path = Path(worker_path).resolve() if worker_path else Path(__file__).resolve().parents[1] / "scripts/openclaw-evaluation-worker.mjs"
        if warm_worker and (self.node_path is None or not self.node_path.is_file() or not os.access(self.node_path, os.X_OK) or not self.worker_path.is_file()):
            raise ValueError("Warm native execution requires an explicit Node executable and worker script")
        self._worker, self._worker_metadata = None, None
        self._worker_lock = asyncio.Lock()
        self._request_id, self._closed = 0, False
        self._worker_generation = 0
        self._stderr_task = None
        self._stderr_bytes = 0
        self._stderr_digest = sha256()
        self._stderr_categories = set()
        self._last_worker_telemetry = {}
        self._bridge_sha256 = sha256(self.worker_path.read_bytes()).hexdigest() if warm_worker else None

    async def _collect_worker_stderr(self, stream):
        # Drain continuously so native fs.writeSync(2) cannot deadlock the host.
        # Retain a bounded matching window and fingerprint, never raw bytes.
        tail = b""
        while chunk := await stream.read(4096):
            self._stderr_bytes += len(chunk)
            self._stderr_digest.update(chunk)
            window = tail + chunk
            for category, marker in _STDERR_MARKERS.items():
                if marker in window:
                    self._stderr_categories.add(category)
            tail = window[-256:]

    def _worker_evidence(self, phase):
        return {"phase": phase, "worker_generation": self._worker_generation,
                "request_index": self._request_id,
                "bridge_source_sha256": self._bridge_sha256,
                "entry_source_sha256": NATIVE_ENTRY_SHA256,
                "process": _process_snapshot(self._worker),
                "last_worker_telemetry": deepcopy(self._last_worker_telemetry),
                "stderr_bytes": self._stderr_bytes,
                "stderr_sha256": self._stderr_digest.hexdigest(),
                "stderr_categories": sorted(self._stderr_categories),
                "stderr_retained_bytes": 0}

    async def _stop_worker(self):
        process, self._worker = self._worker, None
        if process is None:
            return {}
        cleanup = {"process_returncode_before_cleanup": process.returncode,
                   "signal_sent": None}
        if process.returncode is None:
            try:
                process.terminate()
                cleanup["signal_sent"] = "SIGTERM"
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(process.wait(), 5)
            except asyncio.TimeoutError:
                try:
                    process.kill()
                    cleanup["signal_sent"] = "SIGKILL"
                except ProcessLookupError:
                    pass
                await process.wait()
        if self._stderr_task is not None:
            try:
                await asyncio.wait_for(self._stderr_task, 2)
            except (asyncio.TimeoutError, OSError):
                pass
            self._stderr_task = None
        cleanup["process_returncode_after_cleanup"] = process.returncode
        return cleanup

    async def close(self):
        async with self._worker_lock:
            self._closed = True
            if self._worker is not None and self._worker.returncode is None:
                try:
                    self._request_id += 1
                    self._worker.stdin.write((json.dumps({"id": self._request_id, "op": "close"}) + "\n").encode())
                    await self._worker.stdin.drain()
                    await asyncio.wait_for(self._worker.wait(), 5)
                except (BrokenPipeError, ConnectionError, asyncio.TimeoutError):
                    pass
            await self._stop_worker()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.close()

    async def _worker_call(self, stdin, timeout):
        async with self._worker_lock:
            if self._closed:
                raise NativeOpenClawError("native-worker-closed")
            phase = "worker-start"
            started_telemetry = {}
            try:
                if self._worker is None:
                    if sha256(self.worker_path.read_bytes()).hexdigest() != self._bridge_sha256:
                        raise NativeOpenClawError("native-worker-source-changed")
                    self._worker = await asyncio.create_subprocess_exec(str(self.node_path), str(self.worker_path), str(self.cli_path),
                        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE, cwd=self.workspace_path, limit=4_000_001)
                    self._worker_generation += 1
                    self._stderr_task = asyncio.create_task(self._collect_worker_stderr(self._worker.stderr))
                    phase = "worker-admission"
                    ready_line = await asyncio.wait_for(self._worker.stdout.readline(), 120)
                    if not ready_line:
                        raise NativeOpenClawError("native-worker-protocol-eof")
                    ready = json.loads(ready_line)
                    if ready.get("ready") is not True or not isinstance(ready.get("metadata"), dict):
                        raise NativeOpenClawError("native-worker-admission")
                    self._worker_metadata = ready["metadata"]
                    if self._worker_metadata.get("openclaw_version") != NATIVE_OPENCLAW_VERSION or self._worker_metadata.get("entry_source_sha256") != NATIVE_ENTRY_SHA256:
                        raise NativeOpenClawError("native-worker-version-or-source-admission")
                    self._last_worker_telemetry = _safe_worker_telemetry(ready.get("telemetry"))
                self._request_id += 1
                request = {"id": self._request_id, "op": "execute", "prompt": stdin.decode("utf-8"),
                           "configPath": str(self.config_path), "cwd": str(self.workspace_path),
                           "modelRef": self.provider + "/" + self.model, "timeout": math.ceil(timeout)}
                encoded = (json.dumps(request, ensure_ascii=False, allow_nan=False) + "\n").encode()
                if len(encoded) > 4_000_000:
                    raise ValueError("Native worker request exceeds the supported size")
                phase = "request-write"
                self._worker.stdin.write(encoded)
                await self._worker.stdin.drain()
                phase = "reply-read"
                reply_line = await asyncio.wait_for(self._worker.stdout.readline(), timeout + 30)
                if not reply_line:
                    raise NativeOpenClawError("native-worker-protocol-eof")
                phase = "reply-json"
                reply = json.loads(reply_line)
                if isinstance(reply, dict) and reply.get("event") == "request-started" and reply.get("id") == self._request_id:
                    started_telemetry = _safe_worker_telemetry(reply.get("telemetry"))
                    self._last_worker_telemetry = started_telemetry
                    phase = "reply-read"
                    reply_line = await asyncio.wait_for(self._worker.stdout.readline(), timeout + 30)
                    if not reply_line:
                        raise NativeOpenClawError("native-worker-protocol-eof")
                    phase = "reply-json"
                    reply = json.loads(reply_line)
                phase = "reply-schema"
                if not isinstance(reply, dict):
                    raise NativeOpenClawError("native-worker-protocol")
                self._last_worker_telemetry = _safe_worker_telemetry(reply.get("telemetry")) or self._last_worker_telemetry
                if reply.get("id") != self._request_id or "error_kind" in reply or not isinstance(reply.get("envelope"), dict):
                    raise NativeOpenClawError("native-worker-protocol")
                evidence = self._worker_evidence("completed")
                evidence["request_started_telemetry"] = started_telemetry
                return json.dumps(reply["envelope"]).encode(), b"", reply.get("exitCode", 1), deepcopy(self._worker_metadata), evidence
            except asyncio.CancelledError:
                evidence = self._worker_evidence(phase)
                evidence["cleanup"] = await self._stop_worker()
                evidence.update({"stderr_bytes": self._stderr_bytes, "stderr_sha256": self._stderr_digest.hexdigest(),
                                 "stderr_categories": sorted(self._stderr_categories)})
                self.events.append({"status": "cancelled", "native_evidence": evidence})
                self._closed = True
                raise
            except Exception as exc:
                # EOF can precede asyncio's child-status callback. Briefly join
                # before cleanup, preserving an actual signal rather than the
                # SIGTERM subsequently sent by this adapter.
                if self._worker is not None and isinstance(exc, NativeOpenClawError) and exc.kind == "native-worker-protocol-eof":
                    try:
                        await asyncio.wait_for(self._worker.wait(), .25)
                    except asyncio.TimeoutError:
                        pass
                kind = exc.kind if isinstance(exc, NativeOpenClawError) else (
                    "native-worker-timeout" if isinstance(exc, asyncio.TimeoutError) else
                    "native-worker-invalid-json" if isinstance(exc, (json.JSONDecodeError, UnicodeDecodeError)) else
                    "native-worker-broken-pipe" if isinstance(exc, (BrokenPipeError, ConnectionError)) else
                    "native-worker-failure")
                evidence = self._worker_evidence(phase)
                evidence["request_started_telemetry"] = started_telemetry
                evidence["cleanup"] = await self._stop_worker()
                evidence.update({"stderr_bytes": self._stderr_bytes, "stderr_sha256": self._stderr_digest.hexdigest(),
                                 "stderr_categories": sorted(self._stderr_categories)})
                metadata = {"native_openclaw": True, "config_sha256": self.config_sha256,
                            "native_evidence": evidence, "worker": deepcopy(self._worker_metadata)}
                self.events.append({**deepcopy(metadata), "status": "failed", "kind": kind})
                self._closed = True
                raise NativeOpenClawError(kind, metadata=metadata) from None

    async def __call__(self, url, payload, headers, timeout):
        # Headers are deliberately ignored. Native OpenClaw resolves its own
        # existing stored login; no environment key is inspected or copied.
        if sha256(self.config_path.read_bytes()).hexdigest() != self.config_sha256:
            raise ValueError("Pinned native configuration changed after admission")
        if json.loads(self.settings_path.read_text()) != NATIVE_PROJECT_SETTINGS:
            raise ValueError("Private native settings changed after admission")
        if payload.get("model") not in (self.model, self.provider + "/" + self.model):
            raise ValueError("Request model differs from the explicit native model")
        caps = [payload[key] for key in ("max_tokens", "max_completion_tokens") if key in payload]
        if not caps or any(cap != self.max_output_tokens for cap in caps):
            raise ValueError("Request output cap differs from the pinned native cap")
        if payload.get("temperature") != self.temperature:
            raise ValueError("Request temperature differs from the pinned native sampling setting")
        if (self.json_mode and payload.get("response_format") != {"type": "json_object"}) or (
                not self.json_mode and "response_format" in payload):
            raise ValueError("Request response format differs from the explicitly selected native JSON mode")
        if url != self.base_url.rstrip("/") + "/chat/completions":
            raise ValueError("Request endpoint differs from the explicit native provider")
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("A finite positive native timeout is required")
        stdin = pack_messages(payload.get("messages")).encode("utf-8")
        if len(stdin) > self.max_input_tokens:
            raise ValueError("Serialized request exceeds the configured conservative text-byte bound")
        args = [str(self.cli_path), "agent", "exec", "--config", str(self.config_path),
                "--cwd", str(self.workspace_path), "--model", self.provider + "/" + self.model,
                "--code-mode", "direct", "--thinking", "off", "--timeout", str(math.ceil(timeout)),
                "--message-file", "-", "--json"]
        worker_metadata, native_evidence = None, None
        if self.warm_worker:
            stdout, stderr, exit_code, worker_metadata, native_evidence = await self._worker_call(stdin, timeout)
        else:
            process = await asyncio.create_subprocess_exec(*args, stdin=asyncio.subprocess.PIPE,
                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                        cwd=self.workspace_path, limit=4_000_001)
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(stdin), timeout=timeout + 30)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                process.kill()
                await process.communicate()
                self.events.append({"status": "failed", "kind": "process-timeout-or-cancel"})
                raise NativeOpenClawError("process-timeout-or-cancel") from None
            exit_code = process.returncode
        # Never expose raw stdout/stderr from an error: provider/auth diagnostics
        # can contain credentials, request details, or private filesystem data.
        if len(stdout) > 4_000_000 or len(stderr) > 4_000_000:
            raise NativeOpenClawError("oversized-native-output")
        try:
            envelope = json.loads(stdout)
        except (ValueError, UnicodeDecodeError):
            raise NativeOpenClawError("invalid-native-envelope") from None
        if not isinstance(envelope, dict):
            raise NativeOpenClawError("invalid-native-envelope")
        usage = convert_native_usage(envelope.get("usage"))
        metadata = {"native_openclaw": True, "exit_code": exit_code,
                    "usage": usage, "config_sha256": self.config_sha256,
                    "native_budget_contract": deepcopy(self.budget_contract)}
        if worker_metadata:
            metadata["worker"] = worker_metadata
        if native_evidence:
            metadata["native_evidence"] = native_evidence
        if exit_code != 0 or envelope.get("ok") is not True or envelope.get("status") != "ok":
            # Failed runs can contain several turns and known billed usage.
            # Preserve only independently safe counters and enum/identity data.
            metadata["native_failure_status"] = "timeout" if envelope.get("status") == "timeout" else "error"
            if _integer(envelope.get("assistantTurns")):
                metadata["assistantTurns"] = envelope["assistantTurns"]
            failed_summary = envelope.get("toolSummary")
            if isinstance(failed_summary, dict) and _integer(failed_summary.get("calls")):
                metadata["reported_tool_calls"] = failed_summary["calls"]
            if envelope.get("provider") == self.provider and envelope.get("model") == self.model:
                metadata.update(provider=self.provider, model=self.model)
            self.events.append({**metadata, "status": "failed", "kind": "native-run-error"})
            raise NativeOpenClawError("native-run-error", metadata=metadata)
        if envelope.get("provider") != self.provider or envelope.get("model") != self.model:
            raise NativeOpenClawError("native-model-identity-mismatch", metadata=metadata)
        if envelope.get("assistantTurns") != 1 or type(envelope.get("assistantTurns")) is not int:
            raise NativeOpenClawError("native-turn-count-unverified", metadata=metadata)
        summary = envelope.get("toolSummary")
        if summary is not None and (not isinstance(summary, dict) or summary.get("calls") != 0 or type(summary.get("calls")) is not int):
            raise NativeOpenClawError("native-tool-denial-unverified", metadata=metadata)
        if not isinstance(envelope.get("final"), str):
            raise NativeOpenClawError("native-final-text-missing", metadata=metadata)
        if usage.get("completion_tokens", 0) > self.max_output_tokens or usage.get("prompt_tokens", 0) > self.max_input_tokens:
            raise NativeOpenClawError("native-configured-token-limit-exceeded", metadata=metadata)
        metadata.update({"status": "completed", "provider": self.provider, "model": self.model,
                         "assistantTurns": 1,
                         "reported_tool_calls": summary["calls"] if summary is not None else None,
                         "tool_denial_source": "validated-config",
                         "native_usage_status": "actual" if "prompt_tokens" in usage and "completion_tokens" in usage else "unknown"})
        self.events.append(deepcopy(metadata))
        return {"choices": [{"message": {"content": envelope["final"]}}], "usage": usage,
                "native_openclaw": metadata}


class NativeOpenClawPool:
    """Bounded independent warm hosts; one request at a time in each worker."""
    native_openclaw = True
    supports_strict_budget = False

    def __init__(self, cli_path, config_path, workspace_path, *, workers=3, model,
                 provider="xiaomi-token-plan", max_input_tokens=131072,
                 max_output_tokens=1024, base_url=None, node_path=None,
                 worker_path=None, require_strict_budget=False, json_mode=False):
        if not isinstance(workers, int) or isinstance(workers, bool) or not 1 <= workers <= 4:
            raise ValueError("Native worker count must be an integer in [1,4]")
        if not isinstance(json_mode, bool):
            raise ValueError("json_mode must be a boolean")
        self.workers = [NativeOpenClawTransport(cli_path, config_path, workspace_path,
            model=model, provider=provider, max_input_tokens=max_input_tokens,
            max_output_tokens=max_output_tokens, base_url=base_url, node_path=node_path,
            worker_path=worker_path, warm_worker=True, require_strict_budget=require_strict_budget,
            json_mode=json_mode)
            for _ in range(workers)]
        self.budget_contract = {**deepcopy(self.workers[0].budget_contract),
            "native_worker_count": workers, "maximum_concurrent_native_requests": workers,
            "model_requests_serialized_per_worker": True, "independent_ephemeral_run_state": True}
        self.events = []
        self._queue = asyncio.Queue()
        for index, worker in enumerate(self.workers):
            self._queue.put_nowait((index, worker))
        self._active_tasks = set()
        self._closing = False
        self._close_complete = asyncio.Event()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.close()

    async def close(self):
        if self._closing:
            await self._close_complete.wait()
            return
        self._closing = True
        owner = asyncio.current_task()
        active = [task for task in self._active_tasks if task is not owner]
        # Do not dispatch queued work after cancellation/failure during cleanup.
        # Issued requests retain their host reservation if usage is unavailable.
        try:
            for task in active:
                task.cancel()
            if active:
                await asyncio.gather(*active, return_exceptions=True)
            await asyncio.gather(*(worker.close() for worker in self.workers))
        finally:
            self._close_complete.set()

    async def __call__(self, url, payload, headers, timeout):
        if self._closing:
            raise NativeOpenClawError("native-pool-closed")
        task = asyncio.current_task()
        self._active_tasks.add(task)
        started = perf_counter()
        acquired, index, worker = False, None, None
        try:
            index, worker = await self._queue.get()
            acquired = True
            if self._closing:
                raise NativeOpenClawError("native-pool-closed")
            queue_seconds = perf_counter() - started
            response = await worker(url, payload, headers, timeout)
            metadata = {**deepcopy(response["native_openclaw"]), "pool_worker_index": index,
                        "pool_worker_count": len(self.workers), "queue_seconds": queue_seconds,
                        "elapsed_seconds": perf_counter() - started,
                        "native_budget_contract": deepcopy(self.budget_contract)}
            response = {**response, "native_openclaw": metadata}
            self.events.append(deepcopy(metadata))
            return response
        except asyncio.CancelledError:
            evidence = {}
            worker_events = getattr(worker, "events", [])
            if worker_events and worker_events[-1].get("status") == "cancelled":
                evidence = {"native_evidence": deepcopy(worker_events[-1].get("native_evidence", {}))}
            self.events.append({**evidence, "status": "cancelled", "pool_worker_index": index,
                                "elapsed_seconds": perf_counter() - started})
            raise
        except Exception as exc:
            safe = deepcopy(exc.metadata) if isinstance(exc, NativeOpenClawError) else {}
            self.events.append({**safe, "status": "failed", "pool_worker_index": index,
                                "error_type": type(exc).__name__,
                                "elapsed_seconds": perf_counter() - started})
            raise
        finally:
            if acquired:
                self._queue.put_nowait((index, worker))
            self._active_tasks.discard(task)


NativeOpenClawPoolTransport = NativeOpenClawPool
