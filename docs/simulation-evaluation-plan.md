# Simulation evaluation: proposed size and comparison design

Status: offline scaffold started in parallel with the plugin improvements at the
user's request, 13 October 2026. Larger efficacy comparisons remain a later phase.
This refines the evaluation approach in the
[working improvement plan](next-version-plan.md). No paid evaluation has been run.
The [literature brief](memory-systems-literature-review.md) motivates
the mechanisms to compare.

The [simulation scaffold](../evaluation/README.md) provides isolated fake-world
fixtures, independently held scoring keys, paired reports, and an offline pilot.
Its scripted assistant/memory adapters establish mechanics only, not actual AI
efficacy. An additional smoke check uses the actual production MemoryStore for
scope, evidence, history undo, revision fencing, and outcome provenance, without
model calls. No paid or real-model version comparison has been run.

The pilot contains 20 authored sequences in 10 template-family clusters, with
40 future task probes per condition and 60 sequence runs across three conditions.
Template variants are grouped; family identifiers do not establish statistical
independence. Development/held-out manifests reserve 100/500 authoring slots;
these are clearly marked planned, are not runnable cases, and count as no evidence.
The [configured model runner](../evaluation/README.md#real-model-execution-explicit-opt-in-fake-tools-only)
now wires a bounded fake-tool assistant to actual historical, current, released-SDK,
and paper-method learning conditions. It has been tested only with injected model
responses. Native OpenClaw hook integration, independent authoring of the larger
fixtures, and the selected real-model spending configuration remain separate
requirements. No benchmark superiority or real-model task quality has been measured.

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
