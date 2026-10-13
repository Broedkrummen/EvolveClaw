# Native OpenClaw evaluation transport

The native adapter runs a coding evaluation through OpenClaw's installed agent runtime. It does not call the Xiaomi provider endpoint directly or extract the login into a Python environment variable. Provider identity, configured model, output cap, sampling setting, one completed assistant turn, and denied native tools are checked for every request. Independent Python FakeWorld tools continue to handle all simulated actions.

## Supported execution and credential reuse

The installed [OpenClaw agent exec documentation](https://docs.openclaw.ai/cli/agent#agent-exec) describes `agent exec` as the headless embedded entry point for coding automation. It owns temporary run state, cleanup and a stable JSON response containing final text, model/provider identity and available usage. A pinned secret-free config prevents inheriting ordinary user memory, agents, plugins, channels or tool policy. The selected model is explicitly `xiaomi-token-plan/mimo-v2.6-flash`; it overrides the operator's ordinary primary model.

This installation stores the existing `xiaomi-token-plan:default` API-key profile in `/home/broedkrumme/.openclaw/state/openclaw.sqlite`, in the shared `config_machine_state` auth store. Read-only metadata checks confirmed the provider/profile/type and presence of a key, without returning it. V2 shared auth ownership is `state-db`; no old `auth-profiles.json` is required. Native `agent exec` captures the operator's original stored-auth agent/state root before selecting temporary run state and uses its own `withAuthProfileStoreAgentDir` context to resolve the login. Credentials never appear in adapter arguments, message stdin, report metadata or a new config file.

`prepare_native_workspace(new_directory, ...)` creates only a private empty workspace, an explicit provider/profile reference, pinned evaluation config and private retry settings. It reads or changes no live configuration. The resulting config was accepted by installed OpenClaw 2026.10.2 with zero validation warnings. Important current schema locations are:

- Runtime selection is under `agents.defaults.models[provider/model].agentRuntime`, rather than the retired defaults-level key.
- `contextTokens` belongs on the configured provider model definition.
- Output/sampling parameters are in the selected model's `params`; MiMo uses `extraBody.thinking.type="disabled"` and `extraBody.max_completion_tokens`, alongside native `maxTokens`.
- `tools.deny=["*"]` denies every native tool. Only the Xiaomi provider plugin is allowed. Bootstrap, bundled skills, automatic memory/compaction and model fallbacks are disabled.
- Private workspace `.openclaw/settings.json` disables native session/provider retry and compaction. It is separate from the operator's settings.

For the ordinary subprocess path, requests use `openclaw agent exec --config ... --cwd ... --model ... --code-mode direct --thinking off --message-file - --json`, with no retained state directory, fallback, delivery target, or live Gateway. `--auth-env-only` and `--isolated` must be omitted: they bypass credential/config surfaces and cannot be combined with `--config`.

## Warm execution

Repeated process startup was expensive in the parent's initial connectivity smoke. `scripts/openclaw-evaluation-worker.mjs` retains module imports between requests and calls the **existing** `agentExecCommand` implementation sequentially. That function still owns native config composition, stored-auth admission, the complete agent pipeline, ephemeral state, and cleanup. This is an internal entry adapter because the public plugin SDK does not export `agent exec`; its version and source are pinned and fail closed:

- Installed package: `openclaw` 2026.10.2.
- Entry: `dist/agent-exec-DcSrtj25.mjs`.
- SHA-256: `a638bf91efbd775ab4b2d66fd0d6e124074b6edcbad8f85a487e07dab25b8504`.

The warm worker exchanges bounded JSON lines over stdin/stdout. Prompts are positional **in-process arguments**, never shell arguments. Console/runtime diagnostics are suppressed; failed responses expose a generic error kind and safe usage, never raw stderr or provider/auth error strings. Model requests in one worker are serialized; paper perspectives and candidate generation retain independent logical streams/worlds, but this host scheduling changes wall-clock parallelism. It is recorded in metadata and must not be described as concurrent native inference.

```python
transport = NativeOpenClawTransport(
    cli_path, config_path, workspace_path,
    provider="xiaomi-token-plan", model="mimo-v2.6-flash",
    max_input_tokens=131072, max_output_tokens=1024,
    warm_worker=True, node_path=explicit_installed_node,
)
try:
    # Supply to BudgetedModel with transport_kind="native-openclaw".
    # Keep all calls in one asyncio event loop.
    ...
finally:
    await transport.close()
```

An async context manager provides the same shutdown. Success and failure must both close the worker. Cancellation stops the worker; an uncertain interrupted run is not automatically retried.

`NativeOpenClawPool` (also exported as `NativeOpenClawPoolTransport`) bounds native concurrency to 1–4 independent warm workers; three is the initial test setting. Its constructor takes the same explicit paths/provider/model/limits plus `workers=3` and `node_path`. A queue permits one request in each worker at a time. Each underlying invocation still owns new ephemeral native state, and all workers receive the same pinned configuration/empty workspace. The pool changes host scheduling rather than model identity, learning algorithms, individual sequence event order, or FakeWorld state. All workers use the evaluator's **one shared budget ledger**; they do not get separate allowances. Safe event metadata records worker index, queue/elapsed time, source provenance and known usage. Closing cancels queued/in-flight callers, joins their cleanup and closes every worker; it never dispatches queued requests during failure cleanup.

## Fidelity and accounting

The native CLI accepts a user request rather than an arbitrary provider message array. The adapter serializes the requested system/user/assistant roles inside that coding-evaluation request. OpenClaw's own system policy remains active. This is a real native-host execution, with a documented wrapper/system-prompt deviation from direct HTTP evaluation. It is not an exact reproduction of the paper's original runtime prompts or benchmark environment.

OpenClaw's normalized `usage.input` excludes separately reported cached input. The adapter maps `prompt_tokens=input+cacheRead`, preserves known cached tokens, and maps `completion_tokens=output`. Reasoning is already a subset of output and is never added twice. Totals must agree with the complete breakdown. When cache detail is absent but total/output are known, the conservative prompt count is `total-output`, charged at uncached rates; otherwise missing usage remains unknown. Unsupported cache-write usage cannot silently receive ordinary input pricing. Native catalog `cost.total=0` is not interpreted as a zero-dollar subscription bill.

The installed built-in runner omits `toolSummary` when no tool metadata exists. An absent summary is therefore accepted with the independently validated deny-all/native-runtime configuration and exactly one completed turn, but the report keeps `reported_tool_calls=None` and `tool_denial_source="validated-config"`. It does not fabricate an observed zero count. Any positive tool count, different model/provider, extra assistant turn, configured token-limit violation or config change aborts the request.

Native `contextTokens`, output parameters and private retry settings are configured guards. The whole native system prompt, lower transport attempts and provider enforcement are not independently bounded by this adapter. Its `budget_contract` records unknown native input overhead and maximum provider attempts; `require_strict_budget=True` rejects before execution. Token and Token Plan credit reservations remain conservative **operational guards**, not guarantees about native HTTP requests or the provider's bill. The initial host cap and actual/unknown usage must be reported separately from real subscription allowance/expiry, which cannot be inferred from a successful login.

The first parent-run live smoke established connectivity and the selected model's native reply/usage behavior. It established no learning-quality improvement. Offline native boundary tests use fake CLI/worker processes and prove role packing, accounting, admission, safe errors, serial reuse and shutdown; they make no provider calls. A finished matched learning comparison is still required before describing any reduction in mistakes.
