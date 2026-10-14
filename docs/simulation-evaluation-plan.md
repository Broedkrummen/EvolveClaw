# Simulation evaluation: proposed size and comparison design

Status: isolated real-model MiMo pilots began on 13 October 2026 after the offline scaffold. Four original conditions each passed 3/4 future probes in two families; stopped attempts and a fresh all-five cohort are recorded in [the pilot results](mimo-first-pilot-results.md). Larger efficacy comparisons remain a later phase. This refines the evaluation approach in the [working improvement plan](next-version-plan.md).
The [literature brief](memory-systems-literature-review.md) motivates
the mechanisms to compare.

On 14 October 2026, the user proposed separating research, coding and other task
types before further evaluation. The category and batch design below now has
550 authored runnable sequences: 50 diagnostics and 500 held-out sequences.
See [task batches](task-batches.md) for preparation and validation. This authoring
starts no paid evaluation and does not change accounts.

The [simulation scaffold](../evaluation/README.md) provides isolated fake-world
fixtures, independently held scoring keys, paired reports, and an offline pilot.
Its scripted assistant/memory adapters establish mechanics only, not actual AI
efficacy. An additional smoke check uses the actual production MemoryStore for
scope, evidence, history undo, revision fencing, and outcome provenance, without
model calls. Native MiMo operational comparisons now exercise the actual learning algorithms; they have not established a reliability improvement.

The pilot contains 20 authored sequences in 10 template-family clusters, with
40 future task probes per condition and 60 sequence runs across three conditions.
Template variants are grouped; family identifiers do not establish statistical
independence. Development contains 100 authored sequences in 20 families. The new
diagnostics contain 25 families and the held-out suite contains 100 separate
families; neither authored fixtures nor offline reference answers count as model-quality evidence.
The [configured model runner](../evaluation/README.md#real-model-execution-explicit-opt-in-fake-tools-only)
now wires a bounded fake-tool assistant to actual historical, current, released-SDK,
and paper-method learning conditions. Offline integration checks and native MiMo pilot attempts are recorded separately. Native plugin integration and a valid broader learning-benefit study remain separate requirements. The operational pilot does not establish benchmark superiority or deployed reliability.

## Pilot versus evidence

Twenty scenarios are a smoke-test pilot: check fixtures, scoring, learning flow,
isolation, and usage measurement. They are not the proposed sample for declaring
one version better. One changed result in a 20-task suite moves the aggregate by
five percentage points.

Proposed progression:

| Stage | Size | Purpose |
| --- | --- | --- |
| Simulator pilot | 20 scenario sequences | Find broken mechanics and ambiguous scoring; measure consumption |
| Development | Around 100 separate sequences | Refine scenarios, rules, and evaluation configuration |
| Main comparison | Initially 500 held-out sequences | Compare versions on fresh mixed everyday tasks |
| Smaller-effect study | Recalculate; potentially 1,000–1,500 or more | Investigate improvements too small for the initial comparison |

These are planning targets, not statistical guarantees or a spending commitment.
Finalize sample size from the minimum worthwhile improvement and measured paired
outcome disagreements, allowing for clustering and evaluator error. Choose the
API budget after measuring pilot usage.

## Proposed task-specific batches

Report results within each task category as well as an equally weighted average
across categories. An overall average can conceal a version that performs well
on coding and poorly on research. These categories describe the user's work;
they are separate from the paper controller's internal Planner, Web Search,
Analyzer and Browser roles.

| Task category | Representative tasks | Independent outcome checks | Proposed held-out sequences |
| --- | --- | --- | ---: |
| Coding | Bug fixes, small features, behavior-preserving changes and test-driven recovery | Actual code and regression tests in disposable isolated workspaces; a fake tool saying that tests passed is insufficient | 100 |
| Research | Source comparison, cited answers, conflicting evidence and changed facts | Frozen source snapshots; claim support, citation accuracy, completeness and appropriate uncertainty | 100 |
| Writing and documents | Grounded summaries, editing and constrained document transformations | Prespecified factual and instruction-following rubrics; public output requirements, with style scored separately | 100 |
| Planning and administration | Scheduling, preferences, coordination and constrained choices | Constraint satisfaction, current user/project context and independently checked proposed actions | 100 |
| Data and analysis | Calculations, units, joins, extraction and data cleaning | Independently computed values, schema checks and coverage of edge cases | 100 |
| **Total** | | | **500** |

These are provisional balanced allocations, not a power calculation. Aim for
about 20 reviewed family clusters per category with five variants each, while
allowing reviewers to combine related families into coarser clusters. One
hundred sequences per category does not mean 100 independent tasks or guarantee
that a small improvement can be detected. Final category sample sizes depend
on paired disagreements, the worthwhile effect and the reviewed dependence
structure.

A proposed operational batch contains **10 sequences from one category**, each
run against all five conditions: learning disabled, exact repaired v0.2,
improved v0.3, released SDK and the experimental paper method. That is 50
sequence-condition runs per batch. The 500-sequence main study would therefore
have **50 batches: 10 per category**. Batch boundaries are scheduling units,
not independent statistical samples or units of Codex allowance.

Before the main study, use **five diagnostic batches, one per category**, drawn
from separately authored development cases: ideally five reviewed families
with two variants each. These 50 development sequences test coverage, grading,
observable learning opportunities and usage. They do not justify declaring a
category winner, and do not count toward the 500 held-out sequences. The
proposed progression is thus five diagnostic batches followed by 50 main
batches, subject to fixture review and measured usage.

The current development set contains six planning, three communication, four
document, four shopping, two research and one structured-data family. It has
no coding family. Many document cases check metadata or permissions rather
than writing quality, and its research cases do not provide broad evidence
synthesis coverage. Existing fixtures remain labeled and reported as authored;
they must not be relabeled as a complete five-category benchmark. Coding needs
an actual isolated execution harness. The new category suite supplies constrained
Python execution and separate research, writing, planning and data mechanisms;
the older development set retains its original labels.

Within every category, match the model, tools, public sources, starting state,
history policy and per-task limits across versions. Isolate memory by condition
and sequence. Preserve the complete learning history within each sequence;
reset boundaries must follow the prespecified protocol rather than arbitrary
batch boundaries. Randomize or counterbalance condition order, preserve all
bounded task failures and abort explicitly on infrastructure or budget errors.
Keep output contracts public and scoring keys private. Do not rewrite grading
rules after inspecting held-out answers.

Tool/error recovery, conflicting or malicious observations, scope changes,
stale advice and rollback should be balanced **within each category** and
reported as additional tags. They are not a sixth task category. Separately
identify procedural transfer, factual recall and output-format errors. Scope
and rollback probes must verify that relevant memory was actually stored and
retrieved; include memory admission failures in the overall success rate.

For each category report future-task success, improved-minus-repaired paired
differences with uncertainty, error types, regressions, latency and all learning
usage. Keep paper efficiency fixed as primary; report thoroughness and the
non-deployable oracle union separately. An equal-category overall average and
an explicitly labeled everyday-use-weighted average may both be useful, but
neither replaces the category results. Predeclare the category comparisons and
account for multiple comparisons before claiming task-specific winners.

If one version appears better for coding and another for research, test that
finding on fresh families before adopting a task-dependent routing policy.
Use separate development data to choose the routing policy and an untouched
evaluation set to test it. Also evaluate mixed-task histories and cross-category
advice transfer: isolated category scores alone cannot establish safe everyday
memory reuse.

The pilot measures MiMo evaluation usage; it does not measure Codex preparation,
debugging or analysis usage per batch. The previously suggested conversion of
11% remaining Codex allowance into two to five batches was unmeasured and must
not be used as a capacity estimate. Likewise, the remaining local Xiaomi guard
is not an authenticated subscription balance. Prefer evaluator jobs that save
results and stop on failure, with concise summaries for later review, rather
than requiring an assistant turn for every model request. New authoring,
execution-harness work and account-specific usage still need to be measured.

The executable development split now contains 100 authored synthetic sequences:
20 different everyday task families with five variants per family, 300 scored
tasks and 200 fresh probes. Variants share a family cluster; this is not 100
independent families. Structural tests establish reachable tool-backed answers,
scope changes, rollback cases, and separation from pilot fixtures. They do not
establish task difficulty or model quality. The 500 new held-out fixtures are
authored and checked offline, with variants clustered by family. They still need
prespecified real-model evaluation and a dependence review before claims of improvement.
The [MiMo pilot protocol](mimo-pilot-protocol.md)
records the selected model, native execution, token/credit accounting, and all live pilot attempts.

## Why the required size varies

Success/failure on identical tasks is a paired comparison. Its information depends
on tasks where the two versions disagree, not just their separate success rates.
See the primary [McNemar matched-pairs methods study](https://pmc.ncbi.nlm.nih.gov/articles/PMC3716987/).

For illustration, assume independent paired tasks, a single prespecified
comparison, two-sided 5% significance, 80% power, and disagreements on 20–40% of
tasks. A normal approximation gives roughly 150–310 paired tasks for a
10-percentage-point improvement, and roughly 620–1,250 for five points. These
are calculations under assumptions, not empirical estimates for EvolveClaw.
Smaller gains, correlated task variants, subgroup claims, and imperfect scoring
can require more.

## Comparison and independence

Compare learning disabled, repaired EvolveClaw, and the improved version using
matched models, tools, starting histories, and normal task budgets. Prespecify
improved-versus-repaired as the primary comparison; the memory-off condition is
an additional diagnostic. Five hundred sequences across three conditions means
at least 1,500 evaluated sequence runs, with multiple turns and learning/model
calls inside each. Repeated runs add to consumption.

A sequence contains learning opportunities followed by fresh tasks and controlled
state changes. Score future-task completion, repeated mistakes, stale advice,
scope leakage, and rollback recurrence independently. Keep expected answers and
evaluation labels out of the learner; simulated users can give ordinary
corrections. Preserve separate isolated memory stores for each version and run.

Cover planning, research, writing/documents, structured data, and tool/error
recovery. Balance representative cases with explicit scope/update/rollback stress
cases and report these groups separately. A 500-case overall study does not
automatically support a precise claim about every task category.

Paraphrases of one template and repeated stochastic runs are correlated evidence,
not hundreds of independent tasks. Split development and evaluation by underlying
task families and histories. Analyze learning sequences as clusters; estimate
confidence intervals accordingly. A frozen-memory transfer test can separately
measure generalization after learning, while sequential runs measure adaptation.

Report paired improvement with uncertainty, regressions, task-level results,
latency, and full learning consumption. A higher mean alone is not enough to
establish a reliable improvement. Any later extension of the evaluation should
follow a prespecified sample-size/adaptive protocol rather than repeatedly
checking results and stopping when significance first appears.
