# Actual-model evaluation readiness

The runner is implemented and the first two-family native MiMo pilot completed for four conditions: each passed 3/4 future-task probes, with no observed learning advantage. A fresh JSON-mode cohort then completed all five conditions: each learning condition, including the paper efficiency primary, passed 3/4; learning disabled passed 2/4. The baseline discrepancy was an output-format failure. See [the complete results](mimo-first-pilot-results.md) and [pilot protocol](mimo-pilot-protocol.md) for all stopped attempts, changes and usage. No experiment has yet established task-quality improvement. Mock responses establish integration mechanics only. The pilot has 20 authored sequences in 10 families. Development has 100 authored sequences in 20 families. The new [category batches](task-batches.md) contain 50 diagnostic and 500 held-out runnable sequences in 25 and 100 separate families respectively. Variants within a family are correlated examples. No paid evaluations of these new batches have been started; authoring and deterministic reference checks do not establish improved everyday reliability.

## Implemented conditions

| Condition | Actual implementation | Learning boundary and state | Important limits |
| --- | --- | --- | --- |
| `learning-off` | Fixture model agent; no optimizer | No learning; independent output directory | Same assistant instructions and fake tools as the two application conditions |
| `repaired-v0.2` | Exact `TaskScopedOptimizer` and custom prompts archived from commit `03ecaf210c412ee5ae685d8282d3f7e5ed634765` | Terminal run reflection, default efficiency rubric/frequency 3, agent-wide strategic JSON and session tactical state | Genuine historical sidecar algorithm; the historical HTTP server and TypeScript OpenClaw hooks are recorded but are not executed. Missing Git objects abort; the current class is never substituted |
| `improved` | Current production `server/task_optimizer.py` and `server/memory_store.py` | Terminal run reflection with the same application defaults, scoped SQLite provenance, session tactical state, actual history undo | The fixture supplies simulated trusted scope. This does not prove native audience admission, plugin authorization, lifecycle, cache or dashboard behavior |
| `scope_sdk_reference` | Unmodified installed `scope-optimizer==0.1.3` `SCOPEOptimizer`, default prompts/domains/settings | Every executor step; persistent agent-wide strategic JSON and upstream private task-applied-rule readout | Default truncation and agent-lifetime counter behavior remain. No private-state reset, wrapper repairs, or rollback is added |
| `scope_paper_k2_n2` | `ScopePaperController` using actual SDK generation/selection, classifier prompt, and consolidation primitives | Every role step; two candidates, parallel efficiency/thoroughness, sequence-only experiment namespace with separate role/perspective strategic stores and task-local tactical state | No implicit user/project memory routing is added. Hierarchical fixture executor uses Planner/Web Search/Analyzer/Browser with 20/3/3/5 steps per invocation. Executor instructions are authored for fake tools; unpublished original hierarchy prompts/harness and original benchmark tasks are not reproduced |

The application comparison is v0.3 versus the exact repaired v0.2 source, not the scripted `ScriptedMemory` surrogate. Source hashes, default settings, actual learning events, public requests, separate scored traces, and usage accounting are exported. The paper's primary answer is fixed to efficiency **before** grading; both perspective answers are also scored separately. An answer-key selector does not choose the reported answer.

## Isolation and model boundary

- Each condition, repetition, and sequence has its own memory directory. Every parallel paper callback constructs a new fixture agent and deep-copied task, so its FakeWorld and mutable tool trace are independent. Role/perspective memory is isolated inside that condition's controller directory. The pure paper reference uses the sequence alone as its experiment namespace: public user/project labels can inform model reasoning, but scope changes do not select a different persistent memory store. Production v0.3 alone adds user/project memory admission and routing; the historical application and released SDK retain agent-wide strategic retrieval.
- The assistant receives only public instructions, scope labels, advertised tools/arguments, observed fake tool results, and learned guidance. It has no real network, account, shell, or filesystem tools. Answer keys are used only after execution; scorer results and validated success labels are never supplied to any learner or promotion gate.
- Feedback is an ordinary authored user message, including deliberately wrong feedback. Application reflection receives bounded previous public user/assistant context as the sidecar does. Each fixture assistant execution starts a new model history; it does not yet reproduce native chat transcript context across turns. Strategic/tactical memory is the measured cross-run intervention.
- An undo event invokes the actual v0.3 history-restore API for the change accepted from the most recent user-feedback turn, if one exists. This owner action has an explicit recorded target; it does not select a rule using a scored failure. v0.2, released SDK, and the paper controller have no invented rollback mechanism.
- One reservation-based ledger covers assistant calls, reflection, classification, Best-of-N candidates/selection, consolidation, every condition, and both parallel perspectives. It can enforce raw prompt+completion tokens, weighted quota credits, and priced dollars independently. Unknown usage retains its reservation; trusted normalized native failure usage is reconciled and reservation overruns are recorded. Budget exhaustion and infrastructure errors abort with `incomplete.json` and no completed comparison. A typed bounded-executor step-limit failure instead counts as an incorrect task attempt and preserves its unfinished trace; it never becomes a successful negative answer. The adapters do not retry; lower-level native attempt counts remain unknown and are recorded.
- Configuration explicitly names provider, model, endpoint, backend, caps, split, conditions, and output. Direct HTTP selects a secret environment-variable name; native OpenClaw resolves its existing managed login without reading a provider secret in Python. A dollar cap requires known input/output prices; token/credit-only runs leave USD unknown/null. Host catalog cost zero is not evidence of free usage. The current text-only provider and reservation contract is described in `evaluation/models.py`.

## Offline planning

The default command writes a plan without constructing a model or reading credentials:

```sh
python -m evaluation.run_models \
  --provider openai-compatible --model selected-model \
  --base-url https://provider.example.invalid/v1 \
  --api-key-env EVOLVECLAW_EVALUATION_KEY \
  --input-usd-per-million 1 --output-usd-per-million 2 \
  --max-cost-usd 5 --max-calls 200 \
  --split pilot --output artifacts/evaluation/model-plan
```

The endpoint/model/prices above are placeholders for a **plan**, not provider recommendations. Actual execution requires a concrete configuration, a new output directory, and explicit `--execute`. `pilot`, `development`, `diagnostic` and `heldout` select authored fixtures. Use `--batch-id diagnostic.coding.01` or `heldout.research.01` through `.10` for category batches; batch and explicit sequence IDs cannot be combined. Repeat `--sequence-id` to select exact authored cases from distinct families; unknown/duplicate IDs are rejected. Output directories are exclusive and are not overwritten.

For the selected Xiaomi Token Plan, an offline plan needs no guessed dollar prices:

```sh
python -m evaluation.run_models \
  --provider xiaomi-mimo --model mimo-v2.6-flash \
  --base-url https://token-plan-ams.xiaomimimo.com/v1 \
  --execution-backend native-openclaw \
  --max-total-tokens 2000000 --max-quota-credits 250000000 \
  --quota-cached-input-credits 2 --quota-uncached-input-credits 100 \
  --quota-output-credits 200 --max-calls 2000 \
  --max-input-tokens 65536 --max-output-tokens 2048 \
  --split pilot --sequence-limit 1 \
  --output artifacts/evaluation/mimo-native-plan
```

The caps are distinct: raw tokens include prompt and completion once; subscription
credits use model-specific weights. MiMo-V2.6-Flash uses cached input 2, uncached
input 100, and output 200 credits per token. Estimates ignore the off-peak discount
and assume uncached input when cache detail is missing. These are conservative
local estimates, not an account balance or provider bill. [Official Token Plan
documentation](https://mimo.mi.com/docs/tokenplan/subscription).

Token Plan credentials must use the native OpenClaw backend; direct HTTP is
rejected before credential lookup. Actual native execution additionally supplies
`--openclaw-cli`, `--openclaw-config`, and `--openclaw-workspace` for a pinned
isolated profile with real tools denied. See [native execution](native-openclaw-evaluation.md)
for preparation and the host's additional context/retry limits. The native transport
can validate one completed assistant turn; it cannot independently prove one
provider attempt. Reports therefore expose model-execution requests and an unknown
native provider-attempt count. Strict HTTP-equivalent reservation guarantees remain
unsupported and can be required with `--require-strict-native-budget`, which fails
before a call.

For repeated native requests, add `--openclaw-warm-worker --node-path /absolute/path/to/node`.
The worker reuses pinned OpenClaw imports while serializing model execution; fake
worlds and paper perspective state remain independent. The CLI awaits worker
cleanup after both successful and aborted evaluations. Native scheduling and host
system instructions are recorded differences from the original paper harness.

`--openclaw-node` is an alias for the explicit Node path. Up to four independent
warm hosts can be selected with `--openclaw-workers`; each worker executes requests
sequentially. `--max-concurrent-sequences` independently bounds whole sequence
jobs to 1–4, defaulting to one. Each job keeps its own memory and original event
order, while every job and paper perspective shares the same atomic ledger.
Completed rows are saved in canonical condition/sequence order. On failure the
ledger blocks new reservations, all remaining jobs are cancelled and joined, and
only then is the final incomplete usage snapshot written.

`native_execution.json` records allowlisted native identity, normalized usage,
configuration hash, worker version/source hash, and scheduling/budget metadata
after completed sequences and on abort. Model text, provider headers, and raw
diagnostic output are excluded. Full scored fixture traces remain separate
evaluator-only artifacts.

## Verification and remaining evidence

Implemented offline checks in `tests/test_model_integration.py` exercise all five actual learning algorithms with injected provider responses; exact historical source provenance; default no-spend planning; no scorer inputs; independent paper callbacks and constant experiment namespaces across user/project scope changes; scoped retrieval and history undo preserving an unrelated rule; unavailable-baseline rejection; and shared-budget failure, including upstream-swallowed model exceptions. Separate model/controller tests cover provider accounting and step-level dual-stream behavior.

Before interpreting task quality:

1. Select the model/provider/endpoint/backend, explicit token/credit or priced-dollar allowance, sufficient call/output limits, and sampling temperature (`--temperature`, recorded default 0.3). The initial native MiMo smoke verified connectivity, model/provider identity, and usage reporting; it did not compare learning conditions. Exact paper sampling/seed behavior is unavailable and has not been replicated.
2. Run and inspect a small actual-model pilot. Report denominators, rejected/failed learning proposals, actual/unknown usage and estimated costs, category failures, both perspective results, and any incomplete runs. The base fixture prompt already emphasizes verifying tool results; ceiling effects are possible.
3. Review the new family-disjoint category fixtures, dependence assumptions and grading limits. Lock their fixture/scoring hashes before tuning. Repeated variants or repetitions are not extra independent families. New research sources are explicitly fictional snapshots; coding is bounded Python snippets and writing uses limited deterministic content rubrics. The new suite has scope switches and recovery cases, while rollback mechanics remain tested by the existing suites; no rollback-learning benefit is established by these new batches alone.
4. Run the predeclared v0.3 versus genuine v0.2 comparison with matched tasks and model settings. The cluster bootstrap is descriptive for the small pilot; family labels alone do not prove statistical independence. Do not transfer the SCOPE paper's headline gains to EvolveClaw.
5. Verify actual OpenClaw integration separately: native audience/project admission, hooks, same-session overlaps, authorization, restart/reload, memory controls, and dashboard. This fixture runner measures optimizer behavior rather than deployed plugin reliability.

Full SCOPE benchmark reproduction remains unavailable without the original hierarchy instructions, original task/harness assets and complete stochastic/task-order/reset protocol. The experimental controller and hierarchical fake-tool runner implement the documented algorithmic structure with their fidelity limits recorded explicitly.
