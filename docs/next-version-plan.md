# EvolveClaw next version — working design

Status: implementation authorized on 13 October 2026; delivery verification in progress.
The user requested completion of the improved version and parallel evaluation work.
Routine engineering decisions follow the accepted scope below.
Baseline: repaired version 0.2.0, merged through PR #1. Development branch:
`feature/evolveclaw-next`.

## Accepted choices

- Primary purpose: more reliable task completion and fewer repeated mistakes.
- Learning remains automatic, with visible history, scoping, and rollback.
- Evaluation covers a mix of everyday assistant tasks, not only coding.
- New rules default to the current user and project. Broader application needs
  evidence that the rule applies across projects.
- Measure learning usage before selecting a spending budget. Unknown usage or
  pricing must remain explicitly unknown; estimates must be labeled.
- Provide both chat commands and an OpenClaw dashboard interface.
- Improve later tasks first. Extra final-answer correction passes and general
  same-task adaptation are outside the first release.
- Keep the existing SCOPE learning mechanisms and plugin functionality unless
  the agreed migration policy explicitly changes legacy rule activation.
- Live installation/activation remains a separate step; the previous request
  authorized a tested repository change, not changes to the running Gateway.

## Proposed first release

### 1. Reliable, reversible memory

Use a transactional, versioned store behind the pinned SCOPE integration, with
stable rule IDs, recorded source/evidence IDs, scope, status, and revision lineage.
Keep import/export compatibility with existing strategic JSON.

Changes from generation, consolidation, disablement, and rollback enter the same
history. Slow model-based consolidation uses a checked base revision: it cannot
overwrite a concurrent accepted rule. Exact duplicates and contradictions are
different cases; opposite instructions must not be dismissed merely because
their wording overlaps.

The database choice and adapter structure are engineering decisions. The purpose
is atomic changes, traceable history, scoped retrieval, and reliable rollback.

### 2. Scope and evidence

Use trusted OpenClaw context, including its memory audience and prepared project
keys. Its current memory audience identifies either an owner-private agent or a
conversation/session; it does not provide an arbitrary universal user ID.
Unknown identity must not silently turn a rule into global advice.

Record bounded evidence and validation results rather than relying on an LLM's
self-reported confidence as proof of usefulness. Apply eligible guidance within
a bounded prompt budget and preserve the current immediate cached injection path.
Broader promotion requires evidence from distinct relevant contexts and remains
inside the authorized audience.

### 3. Measure learning and task outcomes

Meter synthesis, classification, and consolidation separately from the agent's
normal work. Record provider usage when supplied and labeled estimates otherwise;
do not interpret OpenClaw's default zero pricing for custom providers as proof
that an API is free. Collect enough data to support a later budget decision.

Add outcome records and an evaluator for everyday-task scenarios: sourced
research, planning/constraints, writing/transformation, structured file/data work,
and recovery from failed tools. Verify observable outcomes against independent
fixtures/rubrics. A successful agent run or an increasing rule count is not proof
of a correct answer.

Offline and mocked verification establishes mechanics and reporting. Real model
comparisons must use an explicitly selected evaluation configuration and spending
limit; no claim of real-world quality improvement follows from mocked tests.

The [simulation evaluation proposal](simulation-evaluation-plan.md) separates a
20-scenario simulator pilot from an initially 500-sequence held-out comparison.
Final sizing depends on the improvement being measured, paired outcomes, and
correlation between tasks. These are proposed research targets, not approved
evaluation spending or confirmed implementation requirements. The user subsequently authorized building the simulator and SDK/paper reference
runners in parallel. Model-based evaluation spending is still explicitly configured.
The current release requires its mechanical and integration checks.

### 4. Shared controls in chat and the dashboard

Both interfaces use the same authenticated operations and revision checks:

- inspect active rules, scope, evidence summaries, and change history;
- disable a rule and undo/restore a recorded change;
- show learning activity, measured/estimated usage, and known failures;
- pause/resume learning without uninstalling the plugin.

The native dashboard should provide a rule list with scope/status filters, a rule
detail/history view, and usage/activity information. Rollback should identify the
specific revision being restored. Mutations require write authority; read-only
views remain usable without it.

OpenClaw 2026.10.2 supports native plugin pages, panels, and widgets. Native custom
UI requires its disabled-by-default Labs setting and the authenticated Control UI
served by the same Gateway over HTTPS or trusted loopback. Chat controls should
continue to work when native UI is unavailable. Do not toggle live settings during
repository development.

## Legacy migration policy

On the instruction to finish implementation, use the previously recommended
policy: preserve older unscoped rules as inactive history until an owner assigns
them to a recorded scope. This keeps the agreed user/project boundaries effective.
Original JSON is retained. Assignment and subsequent rule changes are visible,
revision-checked, and reversible through both interfaces.

## Proof required before delivery

- Preserve registration, both injection modes, trace capture, filtering,
  configuration, sidecar lifecycle, tactical reset, and existing API behavior.
- Prove user/project isolation, unknown-scope behavior, evidence-based broadening,
  and the selected legacy migration policy.
- Reproduce and prevent contradictory-rule deduplication and concurrent-write loss.
- Prove atomic history/rollback and suppression of stale cached revisions.
- Verify that usage reporting distinguishes actual, estimated, and unknown values.
- Verify chat and dashboard against the same operations, permissions, and revisions.
- Run representative everyday-task fixtures without giving evaluator answers to
  the learning system. Label mechanical results separately from real model efficacy.
- Type-check/build against the pinned OpenClaw host, inspect the packaged plugin
  in isolated state, run integration checks, and verify the dashboard in a browser.
- Deliver a reviewable PR and built package; do not merge the next version or
  activate it live without the appropriate user instruction.

## Deferred

Best-of-N generation, parallel efficiency/thoroughness executions, arbitrary
mid-tool prompt mutation, and extra current-answer correction passes. Evaluate
these only after the first pipeline has trustworthy measurements and budget policy.

## Evidence

- [Existing research assessment](research-assessment.md)
- [OpenClaw feature plugin UI](https://docs.openclaw.ai/plugins/feature-plugins)
- [Hook reference](https://docs.openclaw.ai/plugins/hooks/reference)
- [Custom provider pricing defaults](https://docs.openclaw.ai/concepts/model-providers/custom-providers)

## Reference experiments added to the authorized work

Keep the unmodified released SDK as a distinct reproducible baseline. Add the
paper architecture separately, including K=2 full perspective executions, N=2
guideline candidates/selector, and hierarchical role budgets. These are isolated
evaluation runners; they do not change the production plugin's future-task-only
learning policy. See scope-paper-implementation.md and evaluation-readiness.md.
