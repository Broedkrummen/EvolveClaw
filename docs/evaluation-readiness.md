# Actual-model evaluation readiness

The runner is implemented, but no paid model experiment has been run. Mock responses establish integration mechanics only. The current 20-sequence pilot has 10 authored families; the planned 100 development and 500 held-out slots have no executable fixtures. Neither this pilot nor the deterministic surrogates in `evaluation.runner` establishes that v0.3 improves everyday task reliability.

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
- One reservation-based ledger covers assistant calls, reflection, classification, Best-of-N candidates/selection, consolidation, every condition, and both parallel perspectives. Unknown or failed usage retains its reservation. Budget exhaustion aborts with `incomplete.json` and no completed comparison. No automatic retries occur.
- Configuration must explicitly name provider, model, endpoint, secret environment variable, input/output prices, dollar/call/token limits, split, conditions, and output. The secret value is never written in the plan or run artifacts. Costs at supplied rates are estimates rather than provider billing statements. The current text-only provider contract and token reservation limits are described in `evaluation/models.py`.

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

The endpoint/model/prices above are placeholders for a **plan**, not provider recommendations. Paid execution requires a reviewed concrete configuration, its named secret variable, a new output directory, and the explicit `--execute` flag. `development` and `heldout` currently fail with an authoring-required error; they never fall back to pilot data. Output directories are exclusive and are not overwritten.

## Verification and remaining evidence

Implemented offline checks in `tests/test_model_integration.py` exercise all five actual learning algorithms with injected provider responses; exact historical source provenance; default no-spend planning; no scorer inputs; independent paper callbacks and constant experiment namespaces across user/project scope changes; scoped retrieval and history undo preserving an unrelated rule; unavailable-baseline rejection; and shared-budget failure, including upstream-swallowed model exceptions. Separate model/controller tests cover provider accounting and step-level dual-stream behavior.

Before interpreting task quality:

1. Select the model/provider/endpoint, known prices, explicit spending allowance, sufficient call/token limits, and sampling temperature (`--temperature`, recorded default 0.3). Provider calls have not been smoke-tested against any live service. Exact paper sampling/seed behavior is unavailable and has not been replicated.
2. Run and inspect a small actual-model pilot. Report denominators, rejected/failed learning proposals, actual/unknown usage and estimated costs, category failures, both perspective results, and any incomplete runs. The base fixture prompt already emphasizes verifying tool results; ceiling effects are possible.
3. Author and review genuinely family-disjoint development and held-out tasks, including harder everyday assistant cases and realistic conflicting or malicious observations. Lock held-out fixtures and scoring before tuning. Repeated variants or repetitions are not extra independent families.
4. Run the predeclared v0.3 versus genuine v0.2 comparison with matched tasks and model settings. The cluster bootstrap is descriptive for the small pilot; family labels alone do not prove statistical independence. Do not transfer the SCOPE paper's headline gains to EvolveClaw.
5. Verify actual OpenClaw integration separately: native audience/project admission, hooks, same-session overlaps, authorization, restart/reload, memory controls, and dashboard. This fixture runner measures optimizer behavior rather than deployed plugin reliability.

Full SCOPE benchmark reproduction remains unavailable without the original hierarchy instructions, original task/harness assets and complete stochastic/task-order/reset protocol. The experimental controller and hierarchical fake-tool runner implement the documented algorithmic structure with their fidelity limits recorded explicitly.
