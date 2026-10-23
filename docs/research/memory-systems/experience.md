# Experiential learning and procedural memory: first literature sprint

**Scope/date:** 13 October 2026, first bounded literature sprint. This is research for a later phase after the current EvolveClaw design, not authorization to add features. Findings compare published primary methods with scoped automatic rules, retained history, rollback, and metrics. No product code or running configuration changed; no live model evaluation was run.

## Main conclusion

The most useful addition to SCOPE's idea is not more aggressive reflection. It is distinguishing **a plausible lesson from an outcome-supported lesson**, selecting advice for the current task, and preserving the original evidence when abstractions are rewritten.

The literature supports three separate kinds of memory: raw episodes, abstract procedural guidance, and executable skills. They should not be treated as equivalent. Success in a simulator with explicit rewards does not establish that an everyday assistant can automatically determine answer quality.

For a later research-led design, the strongest borrowable ideas are localized edits with stable IDs (ACE), evidence pointers (Generative Agents), failure/success contrast (ExpeL), outcome-aware retrieval (MemRL), and evaluation against memory-off controls (Live-Evo). A recent negative result adds an essential control: compare abstract rules with the same unabstracted episodes, and gate consolidation. These are candidates to discuss, not automatic additions to current scope.

## Sources inspected

Firecrawl fetched complete canonical HTML papers, not just abstract excerpts:

| Work | Inspected version | Main role |
| --- | --- | --- |
| [Reflexion](https://arxiv.org/html/2303.11366v4) | v4, 10 Oct 2023 | Within-task retry using verbal feedback |
| [ExpeL](https://arxiv.org/html/2308.10144v3) | v3, 20 Dec 2024 | Cross-task insights plus successful episodes |
| [Voyager](https://arxiv.org/html/2305.16291v2) | v2, 19 Oct 2023 | Verified executable skill library |
| [Generative Agents](https://arxiv.org/html/2304.03442v2) | v2, 6 Aug 2023 | Evidence-linked reflection and selective retrieval |
| [MemoryBank](https://arxiv.org/html/2305.10250v3) | v3, date displayed 21 May 2023 | Conversation facts, profiles, recency/rehearsal |
| [ACE](https://arxiv.org/html/2510.04618v3) | v3, 29 Mar 2026 | Itemized playbook updates and feedback counters |
| [MemRL](https://arxiv.org/html/2601.03192v2) | v2, 12 Feb 2026 | Reward-updated experience utility |
| [Live-Evo](https://arxiv.org/html/2602.02369v1) | v1, 2 Feb 2026 | Contrastive memory-on/off evaluation |
| [Useful Memories Become Faulty When Continuously Updated by LLMs](https://arxiv.org/html/2605.12978v2) | v2, 29 Aug 2026 | Consolidation regression and episodic controls |

These links identify inspected arXiv versions. This sprint did not verify each work's publication venue; it makes no new peer-review-status claims. An arXiv source does not imply either acceptance or nonacceptance elsewhere.

Author-linked repositories inspected through Firecrawl: [ExpeL](https://github.com/LeapLabTHU/ExpeL), [Voyager](https://github.com/MineDojo/Voyager), [ACE](https://github.com/ace-agent/ace), [MemRL](https://github.com/MemTensor/MemRL). ACE and MemRL also received a focused local code inspection:
- ACE pinned `82709de050e1db6e6ef2f07bcb0393560b94992a`.
- MemRL pinned `c1b322ca43de36ddf64c6712f89d0095bfc35ce0`.

The Reflexion paper's linked `noahshinn024/reflexion` URL returned a GitHub 404 during scraping; paper-level conclusions remain grounded in full text. No author repository for Live-Evo was established in this bounded pass. Full source snapshots are in `literature-sources/*-firecrawl.md`.

## What each approach adds

### Reflexion: feedback-conditioned retries, with a verifier limitation

Reflexion separates Actor, Evaluator, and Self-Reflection. After an episode, a scalar or binary success signal plus the trajectory is transformed into verbal feedback. A small memory, usually one to three reflections, informs the next attempt. This principally improves repeated attempts at the **same task**, rather than automatically learning durable cross-task rules.

The evaluator differs by domain: exact-answer matching for reasoning, environment completion and loop heuristics for ALFWorld, and self-generated tests for programming. The paper uses 134 ALFWorld environments; reasoning includes a 100-question HotpotQA subset. Coding reports HumanEval Python 80.1% GPT-4 ->91.0% Reflexion, but MBPP Python falls from 80.1% to77.1%. The paper analyzes false-positive and false-negative self-generated tests as a reason for regressions. Rust HumanEval is a selected 50-problem subset, not the full Python benchmark.

Its coding Pass@1 label does not mean one internal generation: candidate refinement occurs before the final answer, using generated tests rather than hidden evaluation tests. Repeated-trial ALFWorld improvements likewise cannot be read as first-attempt reliability.

**Potential borrow:** use a concrete failure observation to produce a bounded, task-local correction. **Limit:** a successful tool call or self-assured reflection is not a valid answer-quality reward. The negative MBPP result directly refutes an unconditional “reflection improves performance” claim.

Source: [method](https://arxiv.org/html/2303.11366v4#S3), [experiments and verifier analysis](https://arxiv.org/html/2303.11366v4#S4).

### ExpeL: contrast failure with success, and retain examples

ExpeL collects training episodes via retry, compares a failed and successful trajectory for the same task, and also finds patterns across successes. Insights support ADD, EDIT, UPVOTE, and DOWNVOTE; new insights start with importance two and are removed when downvotes reduce this to zero. Successful trajectories remain separately retrievable using task similarity.

Evaluation is deliberately on unseen tasks with a single attempt, after experience gathering. Experiments use four-fold validation with mean and standard error, GPT-3.5-turbo for evaluation actions, and GPT-4 for insight extraction. This stronger teacher is an important difference from purely same-model self-improvement. Reported ExpeL performance includes39% HotpotQA and59% ALFWorld; the paper compares these with Reflexion's40% and54% respectively after three attempts. That comparison illustrates transfer rather than an equal-compute contest.

Results distinguish domains: HotpotQA benefits more from insights than retrieval alone (36% vs31%); ALFWorld benefits more from retrieval than insights alone (55% vs50%). Generic rules and concrete examples are therefore complementary, and the useful balance depends on the task.

**Potential borrow:** retain evidence for a correction, contrast the same failure with an observed successful resolution, and avoid turning one successful trace into an absolute global rule. **Limit:** deterministic environments and known completion/answer rewards provide cleaner feedback than real assistant interactions. LLM votes are judgments, not independent outcome validation.

Source: [experience gathering/abstraction](https://arxiv.org/html/2308.10144v3#S4), [evaluation](https://arxiv.org/html/2308.10144v3#S5), [author code](https://github.com/LeapLabTHU/ExpeL).

### Voyager: reusable capabilities are executable, verified artifacts

Voyager maintains a Minecraft skill library containing programs, indexed by descriptions. It retrieves top-five skills, composes them into new programs, executes, and iterates using environment observations, runtime errors, and a separate GPT-4 task-state critic. Programs enter the library after the critic judges completion; after four failed refinement rounds, the curriculum switches tasks.

This is stronger than saving a textual “always do X” rule because a reusable behavior has actually run in an observable world. Verification is nevertheless an LLM judgment and can fail; the paper explicitly describes missed completion signals and cost limits.

Evaluation includes three runs with a160-iteration budget for exploration, and four unseen crafting tasks with three attempts each and a50-iteration cap. Voyager solves all four tasks in3/3 trials; its no-skill ablation still solves three of the four in3/3, while reducing skill reuse efficiency. This is a small controlled demonstration, not broad assistant validation.

**Potential borrow later:** promote a reusable procedure only after its stated postcondition has been observed, preserving dependencies and applicability. **Limit:** automatic executable-skill synthesis, curriculum generation, and repeated world actions constitute substantial new functionality. They should not silently enter the current plugin repair.

Source: [method](https://arxiv.org/html/2305.16291v2#S2), [generalization table](https://arxiv.org/html/2305.16291v2#S3.T2), [limitations](https://arxiv.org/html/2305.16291v2#S4), [author code](https://github.com/MineDojo/Voyager).

### Generative Agents and MemoryBank: useful provenance, different objective

Generative Agents preserves observation objects with creation/access timestamps. Retrieval combines normalized recency, semantic relevance, and LLM-rated importance. Reflections explicitly cite original memory IDs, forming trees of evidence rather than replacing source events outright.

The study's dependent variable is **behavioral believability**, not reliable task completion. It simulates25 agents over two game days and uses100 human evaluators in a within-subject comparison of architecture ablations and human-written responses. The evaluation includes formal statistical tests. More believable behavior must not be reported as improved correctness.

MemoryBank stores timestamped conversations, daily/global summaries, and user profiles, retrieves by embeddings, and uses an exponential forgetting heuristic reinforced by retrieval. Its recall evaluation uses15 synthetic users, ten simulated conversation days, and194 manually written questions,97 per language. SiliconFriend's open-source models additionally receive LoRA tuning on38K psychological dialogues; empathy comparisons therefore mix memory with model adaptation. Its forgetting rule is explicitly an exploratory simplified model.

**Potential borrow:** source-event IDs, dates, selected retrieval, and distinct handling of user-specific information. **Limit:** recently or frequently retrieved does not mean correct or valuable, and inferred personality should not become authoritative procedural guidance. Neither paper establishes outcome-based rule validation.

Sources: [Generative Agents architecture](https://arxiv.org/html/2304.03442v2#S4), [controlled evaluation](https://arxiv.org/html/2304.03442v2#S6), [MemoryBank method/evaluation](https://arxiv.org/html/2305.10250v3#S2).

### ACE: localized edits and accountable advice

ACE uses Generator, Reflector, and Curator with stable bullet IDs and helpful/harmful counters. The Curator proposes compact deltas that deterministic code merges into the existing playbook; periodic semantic deduplication limits growth. This avoids fully rewriting memory each time, preserving detailed operational knowledge.

Current v3 distinguishes offline train/test pass@1 from sequential online prediction-then-update. AppWorld averages across normal/challenge TGC/SGC metrics: base42.4%, offline ACE with labels59.4%, offline without reference labels57.2%, and online without reference labels59.5%. The17.1-point headline is an aggregate across different completion metrics, not one universal task-success percentage. Finance uses ground-truth accuracy; the general no-label claim should not be extended across all settings.

A focused code check confirms the crucial distinction: `no_ground_truth` hides the target answer from the reflector, but `ace/ace.py` still branches on correctness and provides “matches/does not match ground truth” environment feedback. **No revealed reference answer is not the same as no outcome supervision.**

V3 also stress-tests harmful reflector feedback on FiNER: moderate corruption retains benefit, but corruption every iteration drops below baseline. Such stress testing is more relevant than trusting a high self-reported confidence score. The paper does not establish complete defense against hostile external content.

**Potential borrow:** stable IDs, auditable local changes, helpful/harmful/neutral attribution, and explicit stress tests. **Limit:** attribution comes from an LLM interpreting outcome feedback; counters are not causal estimates. Large playbooks can increase inference tokens, and prompt-cache savings depend on actual provider infrastructure.

Sources: [method](https://arxiv.org/html/2510.04618v3#S3), [AppWorld results](https://arxiv.org/html/2510.04618v3#S4.SS3), [harmful-feedback test](https://arxiv.org/html/2510.04618v3#A1.SS4), [pinned correctness feedback](https://github.com/ace-agent/ace/blob/82709de050e1db6e6ef2f07bcb0393560b94992a/ace/ace.py#L498).

## 2026: stronger selection and validation ideas

### MemRL: relevant memories should also have observed utility

MemRL stores Intent–Experience–Utility triplets. Retrieval first selects semantically relevant candidates, then ranks a combination of normalized similarity and learned utility. Retrieved memories' utility values update from real environment rewards using an exponential moving-average/Monte Carlo-style rule. The backbone remains frozen.

The main runtime experiment revisits tasks for ten epochs, distinguishing last-epoch success from cumulative success. On BigCodeBench,48.5% no-memory ->59.5% last epoch and62.7% cumulative. **Held-out transfer is substantially smaller:**48.5% ->50.8% (+2.3 points). OS transfer is67.3% ->74.6%, DB84.1% ->94.2%, and ALFWorld83.6% ->97.9%, with different backbones by benchmark. Frozen-memory transfer is a stronger generalization test than simply improving on repeated questions.

The repository contains benchmark runners, reward-aware updates, and split artifacts; the inspected BigCodeBench full split has1,140 tasks,798 training and342 validation, seed123. These code artifacts improve reproducibility over SCOPE's SDK-only release, but this sprint did not reproduce their scores.

The theoretical argument assumes a frozen inference policy and stationary task distribution. It does not prove stable improvement in a changing personal-assistant environment. Updating each retrieved memory from the whole task's reward also has a credit-assignment confound: useful advice can receive blame for unrelated failure.

**Potential borrow:** task-filtered retrieval followed by outcome-aware ranking, separate confidence from observed usefulness, and report frozen-memory transfer separately from repeated-task gains. **Limit:** actual reward must exist; replacing it with model confidence changes the method. No objective-quality signal should be fabricated for ordinary conversations.

Sources: [method](https://arxiv.org/html/2601.03192v2#S4), [runtime/transfer](https://arxiv.org/html/2601.03192v2#S5), [pinned utility update](https://github.com/MemTensor/MemRL/blob/c1b322ca43de36ddf64c6712f89d0095bfc35ce0/memrl/service/value_driven.py#L181), [split artifact](https://github.com/MemTensor/MemRL/blob/c1b322ca43de36ddf64c6712f89d0095bfc35ce0/configs/bigcodebench/splits/full_seed123.json).

### Live-Evo: measure whether memory actually helped

Live-Evo separates an experience bank from meta-guidelines explaining how to turn retrieved experience into current-task guidance. It runs each task with memory and again without it, then adjusts experience weights by the difference in outcome. For the worst-performing30% of a batch, it proposes new experience and re-evaluates; entries are committed only if outcome improves. Configuration includes a0.05 minimum Brier improvement.

The main forecast study covers500 tasks over ten weeks using strict time-filtered search. With GPT-4.1-mini, memory-free search agent Brier score is0.19 versus0.14 for Live-Evo; lower is better. Xbench-DeepResearch is split into ten sequential folds and reports46% accuracy versus45% MiroFlow,43% Qwen Deep Research, and40% ReMem. This one-point lead over the strongest listed research baseline should not be described as decisive without uncertainty estimates.

The paper calls write-back improvement statistically significant, but the inspected method specifies a score threshold rather than demonstrating a formal repeated-sample significance test. Forecast outcomes are delayed externally known labels; that is unusually strong supervision.

**Potential borrow:** evidence of gain relative to a memory-off baseline before trusting a new reusable lesson. **Limit:** the method needs at least two executions per task plus candidate re-evaluation and eventual ground truth. Replaying arbitrary assistant tasks can duplicate external side effects and cost. This belongs in safe replayable evaluation/sandbox tasks, not the default live assistant loop.

Source: [method and Algorithm1](https://arxiv.org/html/2602.02369v1#S3), [experimental protocol/results](https://arxiv.org/html/2602.02369v1#S4).

### Negative evidence: preserving history matters even with stronger models

“Useful Memories Become Faulty…” v2 studies repeated consolidation in multiple agent-memory systems and a controlled ARC-AGI stream. It compares one-shot whole-pool abstraction, per-task grouping, streamed updates, and raw-episode controls. Evaluation generally averages two repeats per question; the controlled stream exposes known task families and programmatic solutions, permitting attribution of errors to abstraction.

The study finds early improvement followed by regression; it links failures to lost applicability conditions, mixing different task families, and overfitting a narrow stream. Raw trajectory baselines are competitive with or beat several consolidators. Across400-step controlled streams, episodic-only retain/delete can match the more complex automatic retain/delete/consolidate policy and outperform forced consolidation.

The current v2 differs materially from early abstract summaries. Avoid mechanically repeating the initially indexed54% figure; the inspected v2 discussion instead describes roughly46% of previously solvable problems being lost under a repeated-consolidation condition. It is a specific condition, not a universal regression probability.

**Potential borrow:** immutable source episodes, explicit consolidation eligibility, local edits, and an episodic-only diagnostic baseline. **Limit:** evidence criticizes forced/repeated abstraction under tested protocols; it does not show that every abstraction or SCOPE consolidation is harmful. Context cost and privacy make “retain all raw logs forever” an unsuitable conclusion.

Sources: [setup](https://arxiv.org/html/2605.12978v2#S3), [episodic control](https://arxiv.org/html/2605.12978v2#S4.SS2), [mitigation](https://arxiv.org/html/2605.12978v2#S5), [author evaluation repository](https://github.com/DylanZSZ/Memory-Collapse-Eval) (linked by paper; not code-audited this sprint).

## What to discuss after the current plugin design

| Borrowable mechanism | Added value beyond scoped rules/history/rollback/metrics | Applicability boundary |
| --- | --- | --- |
| Evidence-linked lessons | Explains the observations supporting a rule and preserves contradictory evidence | Evidence pointers do not certify validity |
| Local delta edits with stable IDs | Prevents an unrelated memory rewrite from erasing useful advice | Requires structural validation and migration discipline |
| Selective outcome-aware retrieval | Injects relevant useful advice rather than every stored rule | Requires trustworthy outcome observations; small-data uncertainty matters |
| Success/failure contrast | Learns the condition under which a correction worked | Only when outcomes are observed and tasks comparable |
| Memory-off/episodic-only controls | Tests whether rules add value beyond original history | Use offline replayable tasks; account for repeated compute |
| Gated promotion and consolidation | Prevents self-confidence alone from turning a guess into durable authority | Can preserve automatic scoped learning while keeping weak evidence provisional |

Do not confuse repetition with generalization, model confidence with outcome reward, hidden reference answers with absent feedback, or increased recall/believability with task success. These distinctions should drive a later experiment, not expand current product scope.

The wider2026 search surfaced ERL, MemCon, MSCE, APEX-EM, HyperSkill, and related work. This sprint prioritized full-method verification of MemRL and Live-Evo; uninspected abstract-only candidates are not treated as evidence-backed recommendations. The parent research pass separately examines ledger, lifecycle, and rollback papers.
