# MiMo first-pilot protocol

This is a development experiment for EvolveClaw, not a claim that the plugin improves task reliability. The user selected MiMo-V2.6-Flash and authorized use of their existing Xiaomi Token Plan on 2026-10-13. No live OpenClaw plugin activation is part of this experiment.

## Model, route, and limits

- Model: `xiaomi-token-plan/mimo-v2.6-flash` through native OpenClaw execution, with the configured European Token Plan endpoint `https://token-plan-ams.xiaomimimo.com/v1`.
- Credentials stay in OpenClaw's managed authentication store. The evaluator does not export them, write an env file, or send requests directly to the subscription endpoint.
- The first transport smoke and small five-condition pilot use thinking disabled, the same temperature across conditions, isolated state, and fake task tools. Host-added instructions are a recorded difference from direct SDK calls; this is not original-paper benchmark replication.
- Initial local limits: 250,000,000 plan credits and 2,000,000 raw input-plus-output tokens. Assistant, reflection, classification, candidate generation, selection, and consolidation all share the limits. Calls reserve a conservative allowance before execution; missing usage retains its reservation. Any native execution whose hidden calls or limits cannot be bounded must fail admission rather than claim a reliable spending cap.
- Dollar cost is unknown for this subscription experiment and is not reported as zero. The limits are local safeguards within the user's authorized plan allowance, not a new monthly learning budget.

Xiaomi describes the Standard monthly quota as **11 billion credits**, rather than raw tokens. The user's reported used balance was 239,002,660; if their total quota is exactly 11 billion credits, that implies 10,760,997,340 remaining at that point. This is user-reported metadata, not an authenticated balance measurement. Concurrent OpenClaw use can consume the same quota. The reported, unconfirmed expiry is 2026-10-24 23:59:59 UTC (2026-10-25 01:59:59 Europe/Copenhagen).

For Flash, the published conversion is:

`credits = 2 × cached_input + 100 × uncached_input + 200 × output`

Completion usage includes reasoning tokens; they must not be counted twice. Missing cache telemetry is conservatively treated as uncached input. Xiaomi also documents an off-peak coefficient of 0.8; local reservations omit that discount. Calculated credits are therefore conservative estimates at published rates, not a provider billing receipt. [Official subscription and quota rules](https://mimo.mi.com/docs/tokenplan/subscription), [thinking and usage fields](https://mimo.mi.com/docs/en-US/quick-start/usage-guide/text-generation/deep-thinking), [model and API example](https://mimo.mi.com/models/en-US/mimo-v2.6-flash).

## Order and stopping policy

1. Verify the token/credit ledger offline, native execution admission, model identity, tool denial, managed authentication, and usage extraction.
2. Run a minimal native transport smoke. Stop on authentication, model identity, tool exposure, schema, usage-contract, or provider-limit errors. Preserve failure evidence and do not silently switch to a pay-as-you-go endpoint, another model, or a direct subscription API call.
3. Run a small matched pilot over all five conditions: learning disabled, exact repaired v0.2, improved v0.3, released SCOPE SDK, and the experimental paper method. Preserve all failures and rejected lessons. Freeze the paper's primary efficiency answer before scoring; report its thoroughness answer separately.
4. Inspect formatting failures, actual/unknown usage, estimated quota, latency, accepted lessons, scope leakage, and rollback behavior. This stage establishes operational readiness and a usage estimate; its small sample cannot establish superiority.
5. Run broader development cases only after resolving pilot failures. The primary quality endpoint is future-task success, paired on task and sequence. Repeated mistakes, stale advice, scope leakage, and recurrence after rollback are secondary endpoints. Report denominators and family-cluster counts; repeated variants are not independent families.

The proposed 500 held-out sequences remain an authoring and review task. Hold them separate from development and freeze fixtures, scoring, meaningful-effect threshold, and stopping rules before examining held-out results. Budget availability does not substitute for task diversity or a valid comparison.

The user also offered an existing DeepSeek balance as a backup. If MiMo capacity is insufficient, stop that run and configure a separate matched model cohort; do not silently substitute DeepSeek for only some conditions or sequences.

## Plan scope

Xiaomi's subscription documentation specifies supported programming tools such as OpenClaw and restricts direct automated API use outside that scope. Native execution is used for this plugin-development experiment; a transport switch alone must not be described as provider approval for arbitrary workloads. The evaluator must not make a direct subscription request merely because its request format is compatible. [Published plan usage scope](https://mimo.mi.com/docs/tokenplan/subscription).

## First live transport smoke

On 2026-10-13, the isolated native OpenClaw smoke returned the exact requested `EvolveClaw MiMo smoke OK` text with provider `xiaomi-token-plan` and model `mimo-v2.6-flash`. OpenClaw reported one assistant turn, 2,627 input tokens, 9 output tokens, and zero cache read/write tokens: 2,636 total tokens, equivalent to 264,500 credits at the conservative published conversion. The complete native command took 38.881 seconds. Real tools were denied in the validated pinned configuration; the live Gateway/plugin configuration was not changed.

The generated model-catalog USD cost was zero; it is not subscription billing evidence and the experiment records dollar cost as unknown. This smoke establishes credential, route, identity, reply, and usage compatibility. It does not establish task quality or improvement over the other conditions. A warm execution path or a bounded pilot is needed before scaling the number of native requests.

Two subsequent live smokes reused one native worker and returned the expected structured JSON. They took 35.085 and 20.732 seconds and reported 5,536 combined tokens and 167,136 estimated credits, with cache usage included. Dollar cost stayed unknown. The worker pins OpenClaw 2026.10.2 and the source digest of its native agent-exec entry; it reuses imported code while retaining fresh temporary state and the existing native authentication/cleanup pipeline. The aggregate first-three-smoke consumption is 8,172 tokens and 431,636 estimated credits. The comparison's remaining local allowance is reduced by that consumption.
