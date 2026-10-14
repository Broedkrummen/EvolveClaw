# Memory systems: initial research for the phase after scoped learning

Research date: **13 October 2026**. This bounded 10–15 minute literature sprint used Firecrawl for paper discovery, canonical full text, primary passages, and author repositories. It builds on the [SCOPE/EvolveClaw assessment](research-assessment.md). It is input to a later design discussion; it does not expand the [current improvement plan](next-version-plan.md).

## Recommendation

Test **selective, evidence-backed learning** before adding a larger or more complicated memory system. Preserve the distinction between what happened, what lesson was inferred, and whether applying that lesson helped. The strongest next-phase candidates are outcome-aware retrieval, careful handling of changed or contradictory information, controlled consolidation, and rollback that follows dependencies.

This is a design inference from the studies below, not a demonstrated performance improvement for EvolveClaw. We have not run these systems, reproduced their scores, or evaluated the next plugin version. The existing repair proves compatibility and repaired behavior; it does not prove that learned guidance reduces everyday mistakes.

## Three problems that should have different measurements

**Conversation memory** remembers facts, preferences, plans, and corrections. **Procedural memory** learns advice about completing tasks. **Executable skills** store reusable programs or workflows with observable postconditions. These can complement each other, but they have different failure modes and evidence requirements.

A system can remember the right hotel preference while choosing the wrong itinerary. A confident reflection can recommend a bad procedure. A skill that ran successfully once can fail in another environment. Therefore memory-question accuracy, rule usefulness, and task completion should remain separate results. [MemoryArena](https://arxiv.org/html/2602.16313v1) specifically evaluates causally dependent tasks rather than isolated recall.

## Literature map and inspection coverage

“Full text” means the canonical paper was retrieved and relevant methods/results were inspected; it does not mean an exhaustive audit of every appendix or a reproduction. “Passages” means targeted primary in-body passages rather than a complete paper review. Links pin inspected versions where available. An arXiv link alone does not establish publication status.

| Work | What it contributes | Coverage | Relevance to a later EvolveClaw phase |
| --- | --- | --- | --- |
| [MemGPT](https://arxiv.org/html/2310.08560v2) | Managed context tiers and explicit movement between them | Full text | Context management; distinct from validating learned lessons |
| [A-MEM](https://arxiv.org/html/2502.12110v11) | Linked atomic notes and evolving connections | Full text | Evidence navigation and relevant retrieval; model-generated links need checking |
| [Mem0](https://arxiv.org/html/2504.19413v1) | Extracted fact memory, update decisions, optional graph memory | Full text | Useful efficiency baseline; paper, OSS, and hosted product differ |
| [Zep](https://arxiv.org/html/2501.13956v1) | Temporal knowledge graphs | Full text | Time-aware facts and provenance; greater infrastructure burden |
| [Reflexion](https://arxiv.org/html/2303.11366v4) | Verbal feedback for another attempt | Full text | Later same-task correction option, currently deferred |
| [ExpeL](https://arxiv.org/html/2308.10144v3) | Insights from success/failure contrast plus retrieved episodes | Full text | Conditions supporting a lesson and transfer to unseen tasks |
| [Voyager](https://arxiv.org/html/2305.16291v2) | Executable skill library with environmental feedback | Full text | Future verified procedures; substantial additional scope |
| [Generative Agents](https://arxiv.org/html/2304.03442v2) | Evidence-linked reflection and selective retrieval | Full text | Source-event pointers; its measured objective is believability |
| [MemoryBank](https://arxiv.org/html/2305.10250v3) | Conversation profiles and heuristic forgetting | Full text | User-specific memory; recency is not proof of correctness |
| [ACE](https://arxiv.org/html/2510.04618v3) | Stable playbook IDs, counters, and localized deltas | Full text + focused code | Auditable rule changes without rewriting the entire store |
| [MemRL](https://arxiv.org/html/2601.03192v2) | Relevance filtering followed by reward-based utility ranking | Full text + focused code | Retrieve advice by observed usefulness as well as similarity |
| [Live-Evo](https://arxiv.org/html/2602.02369v1) | Memory-on/off outcome contrast before write-back | Full text | Candidate-promotion experiment in replayable tasks |
| [Useful Memories Become Faulty When Continuously Updated by LLMs](https://arxiv.org/html/2605.12978v2) | Negative evidence on repeated consolidation | Full text | Preserve episodes and test consolidation rather than assuming benefit |
| [TARL](https://arxiv.org/html/2608.03699v1) | Executable add/revise/no-op/reject/defer transactions | Full text | Precise memory-update semantics and state-transition tests |
| [Dependency-Guided Rollback Repair](https://arxiv.org/html/2608.10502v1) | Trace dependencies and selective repair after diagnosed faults | Full text | Retire contaminated derived memories while preserving unrelated ones |
| [MemoryLACE](https://arxiv.org/html/2609.03201v1) | Local merge, supersession, contradiction, and temporal links | Full text | Lightweight lifecycle model instead of a comprehensive graph |
| [LoCoMo](https://arxiv.org/html/2402.17753v1) | Long conversation recall | Passages + author material | Fact-recall diagnostic; dataset/version differences matter |
| [LongMemEval](https://arxiv.org/html/2410.10813v2) | Extraction, temporal reasoning, updates, and abstention | Passages | Useful QA suite; does not establish obsolete-memory removal |
| [MemoryArena](https://arxiv.org/html/2602.16313v1) | Interdependent shopping, travel, search, and reasoning tasks | Passages | Closer to everyday assistant reliability |
| [STALE](https://arxiv.org/abs/2605.06527) | Implicit state changes and resistance to stale premises | Passages | Changed circumstances must change later recommendations |
| [MINJA](https://arxiv.org/html/2503.03704v5) | Query-induced poisoning of persistent agent memory | Passages | Test whether untrusted interaction becomes durable guidance |
| [MemoryGraft](https://arxiv.org/html/2512.16962v1) | Procedural poisoning through ingested artifacts | Passages | Distinguish poison admission, retrieval, and executed behavior |

Detailed supporting notes: [architectures](research/memory-systems/architectures.md), [experience and learning](research/memory-systems/experience.md), [evaluation and failure modes](research/memory-systems/evaluation.md).

## Findings that change how we should assess improvements

### 1. Rewriting memories can destroy useful knowledge

The August 2026 revision of [Useful Memories Become Faulty…](https://arxiv.org/html/2605.12978v2) reports early benefit followed by regression under repeated consolidation. Applicability conditions disappear, unrelated task families mix, and abstractions overfit narrow experience streams. Raw episodes are competitive in several tested conditions. This does not establish that all consolidation is harmful, or that SCOPE specifically suffers the same measured degradation.

The practical hypothesis is to retain source evidence under explicit retention limits, make local changes, and compare consolidated rules against retrieval of the original episodes. Automatic learning can remain automatic while weak lessons remain provisional. A memory being retrieved frequently should not by itself promote it: frequent exposure can reinforce an incorrect rule.

### 2. Outcome feedback is the scarce resource

[ExpeL](https://arxiv.org/html/2308.10144v3) contrasts failed and successful trajectories and tests transfer to unseen tasks. [MemRL](https://arxiv.org/html/2601.03192v2) updates experience utility from environment rewards. Their strongest borrowable idea is separating relevance from demonstrated usefulness.

The distinction matters quantitatively. MemRL reports BigCodeBench improvement from **48.5% to 59.5%** in the last epoch after repeated learning; frozen-memory held-out transfer is **48.5% to 50.8%**. Repeated-task improvement and generalization are different claims. A later EvolveClaw evaluation should report both where applicable.

Do not replace rewards with reflection confidence and claim the same method. For everyday tasks, evidence may be a user correction, an independently checked constraint, or a verified tool result. No correction is an unknown outcome, not success. A successful request to a tool is also not proof that the whole task was completed correctly.

### 3. Stable IDs and local changes are a practical foundation

[ACE](https://arxiv.org/html/2510.04618v3) uses identifiable playbook entries, helpful/harmful counters, and deterministic merging of localized edits. This supports inspectable changes and avoids unnecessary wholesale rewriting.

Its supervision deserves care: in the inspected [code](https://github.com/ace-agent/ace/blob/82709de050e1db6e6ef2f07bcb0393560b94992a/ace/ace.py#L498), hiding the reference answer still supplies correctness feedback. “No revealed ground truth” does not mean “no reliable feedback.” Helpful/harmful counters also inherit attribution errors when a model decides which rule caused an outcome. EvolveClaw should display observations separately from inferred usefulness.

### 4. Changed facts require explicit lifecycle semantics

[TARL](https://arxiv.org/html/2608.03699v1) defines five actions: append, revise, no-op, reject conflicting evidence, and defer verification. Its 5,422 annotated examples test exact next-state behavior, conflict preservation, and memory pollution. The evaluated method trains a controller using these labels with a frozen language backbone; its results are not a drop-in inference-only improvement for SCOPE.

[MemoryLACE](https://arxiv.org/html/2609.03201v1) offers a simpler structural idea: retain atomic evidence, track supersession/contradiction locally, and retrieve related evidence together. On its BEAM 100K subset of 20 conversations/400 questions, Qwen3.5-9B overall accuracy is **51.9% versus Hindsight's 50.3%**, but temporal accuracy is **26.3% versus 35.0%**. Its overall win conceals a relevant regression. Results support testing lifecycle handling, not declaring it solved.

For us, a user explicitly changing a preference, an unreliable source contradicting a fact, and two equally credible sources disagreeing should cause different transitions. Keeping every contradictory statement active makes history available but does not establish which advice should guide a task.

### 5. Rollback must account for derived contamination

[Dependency-Guided Rollback Repair](https://arxiv.org/html/2608.10502v1) traces dependencies between memory, claims, tool observations, and subsequent writes. On 150 controlled shopping/travel/support cases it reports **85.3% recovery**, compared with **77.3%** for LLM-judge repair. However, recurrence is **26.6% versus 12.1%** for that judge baseline. Better initial recovery does not imply best lasting repair.

Importantly, methods receive the identifiers of already diagnosed faulty memories. This is a repair study, not a demonstrated automatic fault detector. Its adapted LongMemEval-V2 subset is restricted to cases fitting the repair schema. A later plugin can test dependency-aware retirement without claiming automatic diagnosis or unrestricted replay. Memory rollback cannot undo a sent message, completed purchase, or other external action.

### 6. More infrastructure does not automatically mean better memory

[Mem0](https://arxiv.org/html/2504.19413v1) reports a **66.88** LoCoMo judge score against **52.90** for ChatGPT memory, while full context scores **72.90**. Its relative improvement headline is against the former baseline. Scores differ across QA subsets, models, judges, and context budgets; they do not rank EvolveClaw against Mem0.

The current author repository also distinguishes its OSS functionality from a proprietary managed platform. Similarly, [Graphiti](https://github.com/getzep/graphiti) and the hosted Zep engine are not interchangeable. We should compare a small baseline appropriate to our installation before adopting another service or graph database. The architecture notes record these deployment differences.

## Proposed experiments for the later phase

These are ranked research hypotheses, not approved additions to the current build.

| Priority | Hypothesis | Smallest useful experiment | Evidence needed to proceed |
| --- | --- | --- | --- |
| 1 | Relevant, supported advice beats injecting all rules | Compare current scoped rules with task-filtered retrieval; distinguish observed usefulness from model confidence | Better held-out task completion without worse scope leakage or stale advice |
| 2 | Retained episodes plus gated consolidation prevent degradation | Compare raw episodes, localized rules, and repeated consolidation over the same evolving histories | Stable or better completion over time, with retention and token costs measured |
| 3 | Explicit temporal/conflict states improve everyday plans | Use changed travel constraints, preferences, availability, and project conventions | Correct current-state use, appropriate clarification, and no destructive overwrite of valid evidence |
| 4 | Dependency-aware rollback repairs more than snapshots alone | Seed a faulty rule that produces derived rules, retire it, restart, and run clean tasks | Derived contamination removed; unrelated newer learning preserved; low recurrence |
| 5 | Outcome-gated promotion reduces bad durable lessons | In replayable evaluation tasks, compare candidate lessons with memory off before promotion | Reliable gain that survives held-out transfer, after counting extra computation |

The fifth experiment borrows from [Live-Evo](https://arxiv.org/html/2602.02369v1), which uses memory-on/off execution plus candidate re-evaluation. This adds repeated work and needs reliable eventual labels. It belongs in a controlled evaluation environment first. It does not change the agreed choice to learn for future tasks rather than add an extra correction pass to live tasks.

Executable skill synthesis and same-task Reflexion-style retries remain later options. Neither is required to establish whether scoped automatic learning works.

## Evaluation design before choosing a winner

Use a mixed everyday-assistant suite: planning with revised constraints, shopping comparisons, research with corrections, scheduling drafts, document work, and a small tool/coding component. Include tasks spanning sessions, changed premises, unknown/conflicting evidence, unrelated projects, and misleading external material. Record actual constraints and completion rather than treating plausible wording as success.

Compare **memory off**, the repaired plugin, the agreed scoped-learning version, simple episode retrieval, and one candidate mechanism at a time. Match models, tools, histories, and token budgets; report added reflection/replay computation. Freeze held-out task families before tuning. Measure completion, user corrections, stale-rule application, inappropriate scope reuse, rule churn, recovery/recurrence, latency, prompt tokens, and synthesis usage. Inspect a sample of model-judged results against independent labels and report uncertainty.

[LongMemEval](https://arxiv.org/html/2410.10813v2) provides valuable update and abstention diagnostics, but its update judge permits the old fact alongside the correct new fact. Add a separate test for reliance on obsolete information. [STALE](https://arxiv.org/abs/2605.06527) supplies a useful distinction between resolving the new state, resisting an old premise, and adapting a later recommendation.

[MINJA](https://arxiv.org/html/2503.03704v5) demonstrates persistent poisoning in three particular agent settings; its injection success and attack success are different metrics. [MemoryGraft](https://arxiv.org/html/2512.16962v1) reports poisoned retrieval exposure in a small handcrafted experiment. Test admission, retrieval, harmful use, and recovery separately. Source labels and scope boundaries need enforcement tests; neither labels nor a rollback button establish effectiveness by themselves.

Measure consumption before selecting the learning budget, as agreed. Report the cost per evaluated task and per useful retained lesson, including extraction, consolidation, embeddings, retrieval context, and any evaluation replays.

## Scope, limitations, and reproducibility

The sprint prioritized primary sources relevant to procedural learning, lifecycle management, and everyday task reliability. Older foundational papers and recent 2026 work were included. Abstract-only leads were excluded from recommendations; marketing comparisons were not treated as independent efficacy evidence. A-MEM and MINJA have verified NeurIPS 2025 entries in the supporting notes; this pass did not establish publication status for every other work.

Firecrawl search produced overlapping candidates, not an exhaustive or systematic-review population. Shared request limits constrained throughput. Canonical scraping sometimes failed; explicit arXiv version URLs often worked, and targeted primary passages filled some gaps. Dataset revisions, QA subsets, judges, stronger reflection models, reward access, and repeated attempts make many reported scores incomparable. The table covers 22 distinct works, with 16 full-text retrievals and six passage-level reviews; MemoryBank also appears in the evaluation notes.

Source snapshots, search responses, retrieval errors, and pinned repository inspections are retained locally under `/home/broedkrumme/evolveclaw-research/literature-sources/`. Supporting notes identify coverage and code pins. ACE and MemRL received focused source inspection, not a full repository audit. No paid model evaluation was performed.

Follow-up leads needing deeper verification include LongMemEval-V2, Memora/forgetting, MemOps, and TANGLE/conflict evaluation. A next research pass should inspect released evaluators and licenses, then reproduce the simplest baselines on our task mix. The current scoped history/rollback implementation remains the next delivery; this research supplies its successor's candidate experiments.
