# SCOPE paper and implementation audit for EvolveClaw

Research date: 13 October 2026. This memo reports a read-only investigation, not a live efficacy experiment or a completed OpenClaw repair.

## Decision in brief

SCOPE is a plausible, useful prompt-adaptation architecture: reflect on errors and successful steps, separate temporary advice from reusable advice, and compact long-term rules. Its paper reports substantial improvements in its own research harness. EvolveClaw genuinely imports the SCOPE optimizer rather than only borrowing its name.

However, the paper does not establish EvolveClaw's effectiveness. The headline results use two answer attempts and an evaluation union; the strongest configuration includes mechanisms EvolveClaw does not enable. The public library also has lifecycle and routing defects directly relevant to the reported stoppage. Restoring plugin registration is necessary but insufficient: truthful traces, isolated session state, temporary-rule cleanup, persistent-rule refresh, and accepted-rule accounting must also work.

Assessment: **promising research method; partially reproducible SDK; unvalidated and currently defective EvolveClaw integration**. No defensible numeric product rating or guaranteed improvement percentage can be derived from the supplied material.

## Primary sources and pins

- [Paper metadata and version history](https://arxiv.org/abs/2512.15374): v1 submitted 17 December 2025; current v2 revised 28 May 2026.
- [Complete paper v2 HTML](https://arxiv.org/html/2512.15374v2), [versioned PDF](https://arxiv.org/pdf/2512.15374v2), and [v1 HTML](https://arxiv.org/html/2512.15374v1). Firecrawl retrieved both complete HTML versions and the v2 PDF; conclusions below use v2 and were checked against PDF text for the numerical discrepancies.
- [SCOPE repository snapshot](https://github.com/JarvisPei/SCOPE/tree/4dc0da5e7843dce84a851bd7a53e4e45932b27d0), commit `4dc0da5e7843dce84a851bd7a53e4e45932b27d0`, dated 26 March 2026. Checkout: `/home/broedkrumme/evolveclaw-research/SCOPE`.
- [SCOPE package metadata](https://github.com/JarvisPei/SCOPE/blob/4dc0da5e7843dce84a851bd7a53e4e45932b27d0/pyproject.toml): version 0.1.3, MIT, Python >=3.8. [Live PyPI page](https://pypi.org/project/scope-optimizer/) also showed 0.1.3 when scraped.
- [EvolveClaw snapshot](https://github.com/Broedkrummen/EvolveClaw/tree/a9c62516051c4fa6369b1c7b20c07c3371e1901d), commit `a9c62516051c4fa6369b1c7b20c07c3371e1901d`. Checkout: `/home/broedkrumme/projects/EvolveClaw`.

The library snapshot predates the revised paper. The v2 additions include overhead measurements, single-agent coding and stronger-model experiments, and sensitivity studies. They should not be represented as reproduced by the March SDK or EvolveClaw.

## What SCOPE actually does

This is inference-time prompt editing, not retraining model weights. A separate LLM proposes an imperative guideline after an error or a potentially improvable successful step. The current prompt and previous advice provide context. Optional Best-of-N synthesis creates several suggestions and asks another LLM call to select one.

A classifier checks duplication, labels the guideline temporary/tactical or reusable/strategic, assigns a domain, and supplies a confidence estimate. The paper places high-confidence reusable guidelines in a persisted strategic store; other accepted advice belongs to the current task. The next prompt combines the original instructions with those two memories.

When a domain exceeds ten strategic rules, another LLM pipeline resolves conflicts, verifies subsumption, and merges overlapping advice, aiming for eight rules. This is more disciplined than indefinitely appending reflections.

Finally, the research harness maintains separate efficiency and thoroughness perspectives. These are **different prompt-evolution executions**, not the same thing as tactical versus strategic memory. Their complementary task successes are combined using the benchmark evaluator.

The architecture has practical strengths. It can correct repeated tool misuse without changing the base agent, learn reusable formatting or fallback practices, and react during a long task when the framework exposes an actual step boundary. Per-agent stores can avoid giving a browser's advice to a planner. Persistent, bounded memory is a coherent design for repeated work. The prompts and interfaces are published, making the mechanism inspectable.

The critic does not obtain a correctness oracle from the execution trace. A successful API call can still produce a wrong answer. Generator and classifier confidence are model judgments, not calibrated probabilities of improved task performance. Better wording, language adoption, or fewer exceptions are evidence of behavior change; they are not by themselves evidence of correctness.

Sources: [paper method](https://arxiv.org/html/2512.15374v2#S3), [published prompts](https://arxiv.org/html/2512.15374v2#A6), [optimizer code](https://github.com/JarvisPei/SCOPE/blob/4dc0da5e7843dce84a851bd7a53e4e45932b27d0/scope/optimizer.py).

## Results, with their actual meaning

The authors' custom hierarchy uses GPT-4.1 for planning/browser agents and Gemini-2.5-Pro for search/analyzer agents. GPT-4.1 supplies SCOPE's generator, selector, classifier, and optimizer. Research defaults are two candidate guidelines, two perspective executions, quality analysis every successful step, and strategic confidence >=0.85.

| Reported benchmark | Static hierarchy | DC adaptation | ACE adaptation | Full SCOPE |
| --- | ---: | ---: | ---: | ---: |
| HLE | 14.23% | 18.44% | 23.72% | 38.64% |
| GAIA validation, 165 tasks | 32.73% | 35.76% | 38.18% | 56.97% |
| DeepSearch | 14.00% | 21.00% | 23.00% | 32.00% |

These are author-reported results, not independently reproduced scores. The paper says **all methods receive two attempts per task** and a task succeeds if either answer is correct (Pass@2). Appendix K.3 clarifies that static baselines repeat the same prompt, while full SCOPE runs efficiency and thoroughness once each. It would be inaccurate to say SCOPE alone gets an extra answer attempt.

The important transfer limitation is the oracle union: method equation (10) maximizes benchmark success over executions. This measures whether a correct answer exists among the two attempts. The paper does not demonstrate a deployed selector that reliably knows which answer to return without benchmark labels. It therefore does not establish single-answer conversational reliability.

On GAIA, cumulative ablations report 32.73 ->37.58 ->41.21 ->44.24 ->46.06 ->56.97 as generation, dual-stream routing, Best-of-N, memory optimization, and perspective exploration are added. The last 10.91-point increase is the largest. Efficiency alone scores 44.85%, thoroughness alone 46.06%, and their overlap 33.94%; their union is exactly 56.97%. Those constituent measurements help distinguish a usable single execution from the aggregate headline.

The single-agent SWE-bench Verified appendix reports 54.2% baseline, 54.8% per-step reflection, and 62.4% SCOPE with GPT-5-mini in mini-swe-agent v2. That is relevant evidence against the idea that SCOPE only works with hierarchical agents. It still uses a different agent, tasks, model, and integration than EvolveClaw.

The stronger-model appendix reports GPT-5.4 GAIA improving from 49.80% to 67.30%. Treat this as an additional author-reported experiment; the missing harness and inconsistencies below limit independent verification.

Sources: [experiment setup/results](https://arxiv.org/html/2512.15374v2#S4), [perspective results](https://arxiv.org/html/2512.15374v2#S5.T7), [additional experiments](https://arxiv.org/html/2512.15374v2#A11).

## How strong is the evidence?

**Helpful controls.** The authors compare a static agent and two adapted prompt/memory baselines under a shared architecture. There are placement, model-choice, candidate-count, confidence-threshold, reflection, and step-budget comparisons. The two-attempt protocol is disclosed. Full prompts and multiple diagnostic counts are provided. These are meaningful improvements over an abstract-only efficacy claim.

**Limited causal ablation.** The main ablation is cumulative, in a fixed order. It shows that a pipeline can improve as components are added; it does not isolate independent effects or interactions. On 165 GAIA tasks, the 1.82-point memory-optimization gain corresponds to approximately three additional successes. Without paired task outcomes or repeated runs, its stability is unknown.

**Statistical reporting gaps.** Two attempts per task are the definition of the reported Pass@2 metric, not repeated independent experimental studies. No confidence intervals, seed-to-seed variation, repeated task-order analyses, or significance tests are supplied in the inspected full text. The paper's use of “significantly” is not backed by a reported statistical test. Close meta-model scores (45.45/46.06/46.67%) do not establish that arbitrary cheaper or local models are interchangeable.

**Reproducibility gaps.** The repository contains the optimizer SDK, adapter classes, examples, and mocked/unit integration tests. It does not contain the published hierarchical research harness, benchmark runner, DC/ACE implementations, task-level result artifacts, or reproduction scripts for the v2 additions. The suite can verify mechanics without reproducing any headline score. No independent reproduction was found in the bounded Firecrawl search; that is a search limitation, not proof that none exists.

**Evaluation details remain incomplete.** GAIA is explicitly the public validation set. HLE is described as a 2,500-question benchmark, but the exact scored subset/handling of inaccessible and multimodal tasks is not specified clearly. DeepSearch's actual scored sample count and evaluator are not sufficiently pinned. Memory initialization, reset policy between repetitions/benchmarks, task order, parallel sharing, and exclusion of answer-specific strategic rules need documentation.

**Leakage is unresolved, not established.** Learning from one's own unlabeled execution on a stream of tasks is a legitimate online-learning setting. The library API does not require ground-truth answers. However, public benchmark answers, persistent rule reuse, task order, and benchmark-specific prompt tuning can affect the results. The inspected materials do not demonstrate a leakage incident, and they do not provide enough artifacts to exclude it. A held-out evaluation must define adaptation separately from scoring and prohibit evaluator feedback from entering memory.

**Numerical inconsistencies confirmed in HTML and PDF.**

- Main GAIA static baseline is 32.73%, but Appendix K.2 lists GPT-4.1 baseline 31.35% with the same 1,714 errors; whether these are different configurations is unexplained.
- Main system-prompt SCOPE has 1,461 errors at 46.06%; Appendix K.2 assigns 1,109 errors to 46.06%. In the placement table, 1,109 belongs to hybrid placement at 43.64%.
- Step-budget Table 22 associates full SCOPE's 56.97% with 139 step-limit hits, while 139 also belongs to hybrid placement in the earlier table. A separate experiment is possible, but its configuration is not explained.
- Some percentages do not correspond to whole-task counts under the stated denominators and simple Pass@2 union. For example, 14.23% cannot be the rounded proportion of an integer number of successes over exactly 2,500 tasks; 33.13%, 49.80%, and 67.30% do not match integer success counts over exactly 165 tasks. An omitted subset or averaging scheme could explain this; it needs clarification.

These observations reduce confidence in fine-grained comparisons. They do not by themselves disprove the method or establish misconduct.

Sources: [benchmark details](https://arxiv.org/html/2512.15374v2#A3), [placement table](https://arxiv.org/html/2512.15374v2#S4.T3), [K.2](https://arxiv.org/html/2512.15374v2#A11.SS2), [K.4](https://arxiv.org/html/2512.15374v2#A11.SS4).

## Cost and latency: measured scope versus implication

On 100 HLE samples, the paper reports 1,119 ->1,166 API calls (+4.2%), 4.9M ->12.4M prompt tokens (+152%), and 469K ->288K completion tokens (-38.6%). A reflection comparison uses 2,331 calls and scores 16%, versus SCOPE's 36%.

This is evidence that smarter context can reduce waste in that particular experiment. A small increase in call count is **not** evidence of a small increase in financial cost. The reported totals add 7.5M prompt tokens while saving 181K completion tokens. Ignoring mixed models and caching, token cost falls only if each completion token costs more than approximately 41.4 prompt tokens. That threshold is a calculation from the table, not a claim about actual provider pricing. Cache discounts, model mix, and both execution streams need explicit accounting.

The “+0s async” label means synthesis was intended to be overlapped with ongoing work. Asynchronous functions still take time. The public optimizer awaits generation, classification, and possible consolidation sequentially; only candidate generation is parallel. A host must schedule analysis separately and decide which later prompt can consume its result. No latency distribution, total elapsed time, queue saturation analysis, or crash-loss measurement is provided.

Sources: [overhead table](https://arxiv.org/html/2512.15374v2#S4.T5), [optimizer calls](https://github.com/JarvisPei/SCOPE/blob/4dc0da5e7843dce84a851bd7a53e4e45932b27d0/scope/optimizer.py#L432), [parallel candidate generation](https://github.com/JarvisPei/SCOPE/blob/4dc0da5e7843dce84a851bd7a53e4e45932b27d0/scope/synthesizer.py#L146).

## Public SDK: defects relevant to a long-running plugin

The following are observed in the pinned code; the first three include deterministic local mock probes with no external model calls.

1. **A per-task cap becomes a process-lifetime cap.** Accepted-rule and success-frequency counters are keyed only by agent name. They are never reset when task_id changes, and the SDK exposes no reset/reset_tactical method. A mock optimizer configured for one rule accepted one in task A and rejected the next in task B; its count stayed one. At the default twenty-rule cap, a long-running agent eventually stops accepting rules while still paying for synthesis/classification.
2. **Returned “strategic” does not imply persistent.** The optimizer returns the classifier's scope even if its confidence is below the promotion threshold or the store rejects the rule. A strategic-confidence 0.8 mock result returned (“rule”, “strategic”) with zero stored rules. The paper says low-confidence strategic advice should instead enter tactical memory. An integration that retains all returned strategic labels across sessions violates that contract.
3. **Lexical duplicate detection can reject opposite instructions.** A direct store probe added “Always use the browser tool for all research tasks” and then rejected the otherwise identical “Never…” rule as a duplicate. The substring/word-overlap guard ignores polarity. The higher-level LLM classifier may catch some such cases, but the store's final check does not.
4. **Configurable promotion threshold has a second fixed gate.** The outer optimizer accepts a configurable threshold; the store independently requires >=0.85. Lower thresholds therefore do not work as advertised all the way to persistence.
5. **History can erase the most important evidence.** The SDK defaults to truncating model output to its first 200 characters and tool calls/observations to 150 each. An integration that prepends conversation history before current output can leave the critic with old material and no current answer.
6. **Concurrency is not fully transactional.** File locks protect writing, but loading, LLM optimization, and forced overwrite are outside one read-modify-write transaction. Another accepted rule written during optimization can be lost when the older snapshot is forced over the store. This is a code-derived risk; no live data-loss experiment was run.
7. **Bounds and provenance are incomplete.** Counts limit entries per domain, not actual token length. Merged/conflict-resolved rules inherit the maximum parent confidence and only the first parent's source task/timestamp, which can inflate certainty and lose evidence.
8. **Best-of-N is not enabled by its flag alone.** It requires nonempty candidate_models as well. There is no built-in controller for the paper's K parallel perspective executions.

During the initial read-only investigation, deterministic mock probes succeeded without provider calls. During repair verification, a separate virtual environment ran all 55 upstream tests successfully. These mocked/mechanical tests do not reproduce any benchmark score or establish model efficacy.

Sources: [counters/acceptance](https://github.com/JarvisPei/SCOPE/blob/4dc0da5e7843dce84a851bd7a53e4e45932b27d0/scope/optimizer.py#L196), [scope/promotion return](https://github.com/JarvisPei/SCOPE/blob/4dc0da5e7843dce84a851bd7a53e4e45932b27d0/scope/optimizer.py#L505), [store persistence and deduplication](https://github.com/JarvisPei/SCOPE/blob/4dc0da5e7843dce84a851bd7a53e4e45932b27d0/scope/strategic_store.py), [memory optimizer](https://github.com/JarvisPei/SCOPE/blob/4dc0da5e7843dce84a851bd7a53e4e45932b27d0/scope/memory_optimizer.py), [existing tests](https://github.com/JarvisPei/SCOPE/tree/4dc0da5e7843dce84a851bd7a53e4e45932b27d0/tests).

## EvolveClaw versus the tested research configuration

| Capability | Paper's strongest configuration | EvolveClaw snapshot |
| --- | --- | --- |
| SCOPE implementation | Published algorithm/research hierarchy | Genuine Python SCOPEOptimizer sidecar |
| Reflection trigger | Error/subtask step, permitting same-task recovery | One /step request at agent_end; captures tools but analyzes after the whole run |
| Perspectives | Efficiency and thoroughness, separate executions, evaluated union | One configured mode; default efficiency |
| Best-of-N | N=2 plus selector | Not passed to optimizer; default off |
| Successful-step analysis | Every successful step | Default every third run completion |
| Agent specialization | Distinct planning/browser/search/analyzer advice | Default name openclaw-agent; subagent sessions skipped |
| Domains/prompts | Seven research domains, research rubrics | Eight assistant-focused domains and custom prompts |
| Strategic memory | Compacted persisted store, read into prompt | Store exists; plugin caches a snapshot and appends returns |
| Tactical lifecycle | Current task only | Shared global plugin state; switches clear local tactical entries, sidecar reset is ineffective with this SDK |
| Evidence fidelity | Execution traces plus prompt | Event-field assumptions, summary truncation, and SDK truncation lose evidence |
| Outcome evaluation | Benchmark evaluator | Counters of steps/rules; no task-success measurement or benchmark suite |

Sources: [sidecar initialization and analysis](https://github.com/Broedkrummen/EvolveClaw/blob/a9c62516051c4fa6369b1c7b20c07c3371e1901d/server/server.py#L65), [defaults](https://github.com/Broedkrummen/EvolveClaw/blob/a9c62516051c4fa6369b1c7b20c07c3371e1901d/server/config.py#L19), [global state/hooks](https://github.com/Broedkrummen/EvolveClaw/blob/a9c62516051c4fa6369b1c7b20c07c3371e1901d/plugin/src/index.ts#L278), [custom prompts](https://github.com/Broedkrummen/EvolveClaw/blob/a9c62516051c4fa6369b1c7b20c07c3371e1901d/server/prompts.py), [dependency floor](https://github.com/Broedkrummen/EvolveClaw/blob/a9c62516051c4fa6369b1c7b20c07c3371e1901d/server/requirements.txt).

The custom-prompt API arrived in SCOPE 0.1.3, but EvolveClaw permits scope-optimizer>=0.1.1. A previously installed older satisfying version can lack the required constructor arguments. This is a concrete compatibility candidate independent of OpenClaw versioning.

A saved store can contain useful advice even when live learning is broken. Conversely, seeing an increasing rule counter proves synthesis activity, not better outcomes. EvolveClaw's prompt instruction to favor more recent conflicting advice also lacks an evidence-based success test.

Learning raw user/tool text into future system guidance introduces a concrete authority issue: a malicious page, mistaken response, or one-task preference can be generalized and repeatedly injected. Neither the paper nor this integration demonstrates prompt-injection resistance, calibrated confidence, automatic rollback on regression, or robust preference scope. Treat learned advice as subordinate to explicit current instructions and retain inspectable provenance.

## Minimum repair implications and later efficacy test

For the authorized plugin migration, preserve corrective and enhancement learning, tactical/strategic separation, strategic persistence/compaction, configured model support, automatic service lifecycle, injection modes, filtering, and observability. Registration verification alone is too narrow.

The repair should verify actual supported hook payloads, preserve meaningful bounded traces, isolate session/run state, implement an effective task reset, distinguish accepted temporary advice from confirmed persisted advice, refresh compacted strategic memory, and make sidecar failures visible without breaking normal assistance. Pin a compatible SCOPE version or explicitly contain its defects. Keep current model/domain customizations.

Do not add two answer executions simply to match the paper: that doubles external actions and still needs a usable selector. The minimum preservation request does not require this absent capability. Any later optional perspective or Best-of-N feature needs explicit cost limits and a separate efficacy experiment.

A realistic next experiment compares the repaired plugin off/on over held-out representative OpenClaw tasks with the same model/tools and fixed budget. Freeze or separately define adaptation memory, prohibit answer-label feedback, retain task-level paired outcomes and trace provenance, and report first-answer success, repeated-error rate, completion time, prompt/completion tokens, guideline adoption, and regressions. Include interleaved sessions and stale preferences. Judge efficacy by completed tasks rather than rule counts. Paid live model evaluation was not performed in this research pass.

## Repair status

The implementation comparison and defect findings above describe the pinned original EvolveClaw snapshot. Version 0.2.0 repairs registration/configuration, actual hook payloads, run/session isolation, task counters/reset, persistent-rule refresh, unpersisted strategic fallback, context truncation, dependency setup, and provider URL forwarding. A pinned SCOPE 0.1.3 adapter contains the lifecycle defects without changing the upstream strategic JSON format. Lexical polarity deduplication, multi-process store transactions, calibrated confidence, parallel perspectives, Best-of-N, and efficacy evaluation remain future work. See [migration and verification](migration.md) for the tested behavior and its limits.

