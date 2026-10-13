# Experimental SCOPE paper controller

This implements the four published SCOPE algorithm components using a caller-provided model and a caller-provided agent executor. It does not launch OpenClaw, configure credentials, access live tools, or select a supposedly correct answer from hidden benchmark labels. Model clients and spending limits belong to the evaluation runner.

Primary method: [SCOPE v2, revised 28 May 2026](https://arxiv.org/html/2512.15374v2), particularly [methodology](https://arxiv.org/html/2512.15374v2#S3), [hierarchical agents](https://arxiv.org/html/2512.15374v2#A2), [hyperparameters](https://arxiv.org/html/2512.15374v2#A4), [perspectives](https://arxiv.org/html/2512.15374v2#A5), and [published prompts](https://arxiv.org/html/2512.15374v2#A6). The supplied SDK is [scope-optimizer 0.1.3](https://github.com/JarvisPei/SCOPE/tree/4dc0da5e7843dce84a851bd7a53e4e45932b27d0). Its March 2026 snapshot predates the revised paper. The controller imports the SDK's actual `GuidelineSynthesizer`, `MemoryOptimizer`, and classifier prompt; it does not substitute scripted rules for these algorithms.

## Public interface

```python
from evaluation.scope_paper import PaperConfig, ScopePaperController

controller = ScopePaperController(budgeted_model, experiment_directory,
                                 config=PaperConfig())

async def execute(public_task, perspective, guidance):
    # The caller owns its independent FakeWorld and hierarchical agent loop.
    prompt = guidance.prompt("Planner", planner_base_prompt)
    output = await budgeted_model.generate(planner_messages(prompt, public_task))
    # Invoke an actual allowed simulated tool, then report its observed result.
    await guidance.observe_step(
        "Planner", planner_base_prompt,
        model_output=output.content,
        tool_calls=actual_tool_call,
        observations=actual_tool_result,
        error=actual_error_or_none,
    )
    # Rebuild guidance.prompt before the next invocation, in this same task.
    return final_response

results = await controller.run_task(public_task, execute,
                                    namespace=public_task["scope"])
```

The example illustrates the callback boundary, not a complete agent executor. `public_task` is a JSON object with nonempty `task_id` and `instruction`. `namespace` is an explicit nonempty JSON object or string. The runner must pass public requests rather than scoring keys. A namespace is an authored experimental identity, not an authorization grant from OpenClaw.

The callback runs once for each configured perspective and receives an independent JSON copy of the public request. Each execution must create its own tool/environment state. Mutation by one executor cannot change the request received by the other or the source task used for reflection. The callback returns a JSON-compatible final response.

`guidance.prompt(role, base_prompt)` produces the base system instructions followed by that role's persistent strategic rules and current-task tactical rules. Call it before every agent/model step. `await guidance.observe_step(...)` captures a frozen trace of that completed step and performs reflection. It returns acceptance/rejection diagnostics, effective memory stream, confidence, and consolidation metadata. Non-string observations and tool inputs are captured as JSON text; later mutation of the original objects cannot change recorded evidence. Guidance expires when its execution ends.

`PerspectiveResult` contains `perspective`, `task_id`, `status`, `response`, `steps`, `learning_events`, `meta_model_calls`, and an optional `error`; `to_dict()` returns a detached copy for artifacts. Solver model usage is recorded by the caller's budgeted model, while `meta_model_calls` counts controller requests. An executor/model failure is reported as an error result, not a completed answer.

## Algorithm implemented

Defaults reproduce Appendix D's settings:

| Component | Default |
| --- | --- |
| Candidate synthesis | N=2 separate model requests, then the SDK selector |
| Perspective exploration | K=2 entire executions: efficiency and thoroughness |
| Successful-step analysis | Every successful step, frequency 1 |
| Admission | Classifier confidence at least 0.5 and not duplicate |
| Strategic routing | Classifier says strategic and confidence at least 0.85 |
| Tactical budget | 20 task-local rules per role |
| Strategic budget | 10 rules per domain per role and perspective |
| Optimization | Trigger above 10; target 8; at most two passes |

Both candidate requests use the explicitly supplied model, matching the paper's same-model default. The released SDK counts candidates as the primary model plus `candidate_models`; the controller supplies N-1 additional references. It uses the SDK's real selector rather than choosing by fixture scores. This does not guarantee diverse candidates: temperature, random seeds, and sampling configuration are the responsibility of the supplied model and must be recorded.

Error steps invoke the published corrective generator. A step without an explicit error is a successful **execution** for reflection purposes; it is not declared correct against an answer key. Successful steps invoke the efficiency or thoroughness quality rubric and may produce no update. Generator context includes observed output, actual tool calls/results, the current composed system prompt, task instruction, role, and already applied tactical rules. Classification sees both strategic and tactical memory.

The classifier rejects semantic duplicates; exact duplicates are also rejected locally. Invalid classifier JSON, scope, domain, or nonfinite confidence produces no accepted lesson. Accepted strategic proposals below the promotion threshold become tactical. Strategic rules are added immediately and are available to the next step; tactical rules are available only until that execution/task ends. The controller never excludes error traces or failed task histories simply because an external scorer marked them unsuccessful.

Domains are the published seven: `tool_usage`, `data_validation`, `error_handling`, `efficiency`, `analysis_methodology`, `safety`, and `general`. On overflow, the actual SDK optimizer analyzes relationships, resolves conflicts first, verifies and prunes subsumption second, and consolidates related rules third. If semantic optimization remains above capacity after its bounded passes, the controller applies the SDK's confidence-ranked hard-cap fallback and records it. Reaching eight rules is a target, not a guarantee or a reason to silently discard unrelated advice.

## Hierarchical architecture and execution coverage

The paper's top-level planner decomposes and delegates to web search, analyzer, and browser agents. The published role limits are exported as `ROLE_STEP_LIMITS`: Planner 20, Web Search 3, Analyzer 3, Browser 5. The research system used GPT-4.1 for Planner/Browser and Gemini-2.5-Pro for Web Search/Analyzer; all meta-components used GPT-4.1. Using another model configuration is an experimental deviation that must be recorded.

The executor must enforce those limits for each agent invocation/subtask, route delegation to the appropriate allowed simulated tools, return subordinate observations to the planner, and call the same guidance object's methods with the actual stable role. The controller deliberately does not impose a three-step total for all search invocations across an entire task: repeated delegation is part of the hierarchy. It supports role-local evolution, but an executor calling only `Planner` is a single-role experiment and must not be labeled a reproduction of the hierarchical architecture.

Each role learns from its own trace. Subordinate results can become planner observations through normal delegation. The paper does not publish an automatic cross-role strategic-memory sharing rule; the controller does not invent one. It also keeps perspectives separate rather than merging efficiency and thoroughness rules into one prompt. Corrective rubric wording is shared in the published SDK; perspective differences primarily come from quality rubrics and independently evolved histories.

## Persistence and task boundaries

Strategic data is isolated by the hash of the explicit experiment namespace, perspective, and stable role. Atomic JSON replacement persists each role's strategic memory across tasks and controller restarts. Tactical memory, successful-step counters, and task-local rule budgets are fresh for every execution/task. Use one directory per experimental condition and one controller per directory; tasks sharing a namespace are serialized inside that controller. This experimental JSON store is not the production plugin's SQLite store and does not claim cross-process coordination, authorization enforcement, rollback, or secure deletion.

This fixes three released-SDK discrepancies without pretending they are unchanged SDK behavior: its admission counter is keyed only by agent and never resets between tasks; it counts both memory streams against that budget; and a strategic-labeled proposal below 0.85 can retain a strategic label despite not being persisted. This controller explicitly counts only task-local tactical rules and follows the paper's effective routing. The unmodified SDK remains a distinct evaluation condition.

Network/budget exceptions are observed outside SDK helpers and returned as execution failures. This matters because SDK candidate/selection/optimization helpers catch model exceptions. The controller cannot create or enlarge a model budget; the provided model must reserve and enforce its own budget for all solver and meta-calls.

## Interpretation and unresolved reproduction details

Store both perspective responses and score them independently after execution. A separately reported oracle Pass@2 can mean either response passed the external evaluator, as in the paper. It is not a deployable answer selector, and no hidden answer is supplied to reflection or used to choose the user-facing response. A separately designed chooser would be another experimental condition.

The original paper does not release its full hierarchical benchmark harness, exact random-seed/task-order protocol, or a non-oracle final-answer chooser. The per-task tactical limit is interpreted per optimized role, consistent with the SDK's agent-specific organization; the paper's table itself does not specify the aggregation unit. Exact stochastic sampling, initial perspective-specific base instructions beyond the supplied rubrics, and persistence/reset rules between independent benchmark repetitions remain incompletely specified. These limits prevent claiming exact benchmark replication or transferring its headline improvement percentages to this plugin.

Local tests use injected, non-network models while exercising the actual SDK synthesizer/selector and optimizer. They verify K=2 complete executions, N=2 candidate requests, next-step advice, error and quality analysis, threshold routing, task-budget reset, persistent role/perspective/namespace separation, immutable traces, consolidation priority, and budget-error propagation. They establish algorithm plumbing; they provide no real-model efficacy result or evidence that synthesized advice is correct.
