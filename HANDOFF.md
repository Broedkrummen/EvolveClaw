# EvolveClaw handoff — 14 October 2026

## Start here

The user wants an installable OpenClaw plugin preserving EvolveClaw's existing
functionality, scoped automatic learning with history and rollback, and a fair
comparison with the released SCOPE SDK and experimental paper architecture.
The plugin and first actual-model pilot are complete. The active request is:
**write this handoff first, then author runnable tasks for the five proposed
task-specific diagnostic batches and the separate 500-sequence held-out study
so the next account can continue testing.** The user explicitly selected both
diagnostics and held-out authoring after this document was first saved.

Workspace: `/home/broedkrumme/projects/EvolveClaw`.
Repository: https://github.com/Broedkrummen/EvolveClaw
Development branch: `feature/evolveclaw-next`.
Published baseline before this task authoring: `fb75c9620f7205c040dc05009421f7be9a513179`.
Draft PR: https://github.com/Broedkrummen/EvolveClaw/pull/2
The repaired v0.2 was already merged through PR #1. Do not merge PR #2 or
activate the plugin in the user's live Gateway without authorization.

The other Codex account should open this workspace and read this file, then
inspect `git status --short`. Preserve all local changes. At handoff creation,
`docs/simulation-evaluation-plan.md` has an uncommitted task-category proposal
from the preceding turn. Do not overwrite it. New task work is recorded in the
progress section below; inspect the files instead of assuming it finished.

## Completed work and evidence

- v0.3: transactional SQLite rule/evidence/history storage; trusted OpenClaw
  audience/project scoping; revision checks; disable/undo/pause/resume/promotion;
  bounded prompts/traces; session isolation; cache invalidation. Both original
  injection modes, the Python sidecar, model configuration, tactical/strategic
  learning, traces and statistics are retained. Legacy JSON imports stay
  inactive pending deliberate review, with the original preserved.
- Shared authenticated controls in `/evolveclaw`, `/evolveclaw-change` and the
  native OpenClaw dashboard. Permission and revision checks are shared.
- Installable archive: `artifacts/evolveclaw-0.3.0.tgz`, SHA-256
  `b7fc11df89ee2a8208e050b0530ab1dfb8d27fba803fdea0b58bc70312f54d16`.
  `artifacts/package-verification.json` matches that archive. Isolated OpenClaw
  2026.10.2 installation registered seven hooks, the sidecar and controls;
  denying conversation permission retained three hooks. No live config changed.
  This verified archive predates the new task fixtures. Production plugin source
  is unchanged by task authoring; use the source checkout for the new evaluations.
- 112 Python tests and 45 subtests passed before new task authoring. Full GitHub
  compatibility workflow passed for `fb75c96`, including TypeScript/plugin,
  four browser UI tests and package installation. Recheck relevant tests after
  implementing new evaluation code; do not confuse old proof with new coverage.
- Research: `docs/research-assessment.md`, `docs/memory-systems-literature-review.md`
  and `docs/research/memory-systems/`. Source paper is arXiv 2512.15374v2;
  upstream SCOPE snapshot is `4dc0da5e7843dce84a851bd7a53e4e45932b27d0`.
  The SDK is pinned to `scope-optimizer==0.1.3`.

## First complete live comparison

Frozen implementation commit: `67ebdd579b99e26cb8f50f6558ce513ee835b962`.
Local artifacts:
`artifacts/evaluation/native-mimo-json-complete-pilot-20261013/`.
Public summary and numeric evidence:
`docs/mimo-first-pilot-results.md` and `.json`.

| Condition | Future success | Native execution requests |
| --- | ---: | ---: |
| Learning disabled | 2/4 | 20 |
| Exact repaired v0.2 | 3/4 | 20 |
| Improved v0.3 | 3/4 | 21 |
| Released SDK | 3/4 | 31 |
| Experimental paper, fixed efficiency primary | 3/4 | 309 |

Paper thoroughness scored 2/4; the non-deployable oracle union scored 3/4.
All learning conditions missed the corrected same-user dietary preference.
The baseline's extra miss was JSON with extra function text appended, rather
than demonstrated reasoning failure. Thoroughness's extra miss put a caveated
sentence in an exact-value field, rather than demonstrating cross-user leakage.
Only two task families and one repetition were tested: **no efficacy winner**.

The complete cohort used 401 successful native requests, 1,525,843 known tokens
and 52,055,492 conservative estimated Xiaomi credits. All completed envelopes
had the expected provider/model and one assistant turn. Actual lower-level
provider attempts and dollar cost remain unknown. Historical failed cohorts,
unknown reservations and reconciliation are retained; cumulative accounting is
820 requests, 3,127,648 known tokens, 3,735,904 accounted tokens and 174,566,396
accounted credits. The 608,256-token difference is historical uncertainty.

The remaining **local safeguards** were 264,096 raw tokens and 75,433,604
credits. These are not the provider account balance. The user's earlier report
was an 11-billion-credit Xiaomi plan with 239,002,660 used; that report is not a
current authenticated balance. Do not silently reuse the pilot's small remaining
local guard for a larger experiment or claim the subscription is exhausted.

## Active task-category design

Read `docs/simulation-evaluation-plan.md`, especially “Proposed task-specific
batches”. Five categories: coding; research; writing/documents; planning/admin;
data/analysis. The next deliverable is **five diagnostic batches of ten
sequences each**, ideally five reviewed families with two variants per category.
Each sequence runs against all five conditions: 50 sequence-condition runs per
batch, 250 across the five diagnostic batches. Development diagnostics are not
held-out efficacy evidence. The larger 500-sequence held-out study uses 50
ten-sequence batches. Its authoring is now part of this request; keep it disjoint
from diagnostics and do not tune against held-out model outcomes while developing
the harness.

Each sequence needs observable public learning opportunities, feedback and fresh
probes. Keep grader keys out of the learner. Make required output fields and
enums public; avoid the previous hidden initial preference target and grading
reasonable prose as a wrong value without a public schema. Distinguish factual
recall, procedural reuse and formatting. Balance tool errors, evidence changes,
scope and rollback inside categories, rather than making them a sixth category.
Verify populated memory before interpreting scope/undo scores. Match model,
tools, state and histories across conditions. Freeze paper efficiency before
grading; secondary answers cannot choose the primary with answer keys.

Existing fixtures: 20 pilot sequences in ten families, and 100 development
sequences in 20 families. Current development families are six planning, three
communication, four document, four shopping, two research and one structured-data.
There is no coding family; most document cases are metadata checks, not writing.
Do not relabel them as a complete role-specific benchmark. New diagnostic and
held-out fixtures live separately in `evaluation/coding_tasks.py` and
`evaluation/role_tasks.py`; the former 500 placeholders are replaced by actual
authored fixtures. Check the final proof below before running them.

Coding needs independently checked code behavior in disposable isolation;
“fake tool says tests passed” is not sufficient. Research can use frozen authored
sources with explicit provenance; distinguish synthetic sources from real web
research. Writing needs a declared factual/instruction rubric, not only exact
string equality. Do not promise all five batches ready until each is executable
and its scoring/learning isolation has been checked.

## Runtime and commands

- Python with dependencies:
  `/home/broedkrumme/evolveclaw-research/test-venv/bin/python`.
- Node/OpenClaw:
  `/home/broedkrumme/.nvm/versions/node/v26.11.1/bin/{node,openclaw}`.
- Relevant Python proof:
  `PYTHONPATH=server:. /home/broedkrumme/evolveclaw-research/test-venv/bin/python -m pytest -q`.
- Package proof: `npm run verify:package` (isolated install, zero model calls).
- CLI planning: `python -m evaluation.run_models --help`; planning never starts
  a model. Live execution requires `--execute` and concrete caps/profile paths.
- `evaluation/scenarios.py`: Task/Sequence/FakeWorld and private ScoringKey.
  `evaluation/development_scenarios.py`: authored current development fixtures.
  `evaluation/run_models.py`: all five actual learning adapters and coordinator.
  `evaluation/real_agent.py`: flat and hierarchical fake-tool executor.
  `evaluation/scoring.py`: exact structured fields/types, coding execution and
  deterministic writing constraints. `evaluation/batches.py`: batch selection
  and public/scorer-only export.
  `evaluation/models.py`: shared reservation/accounting ledger.
  `evaluation/openclaw_transport.py`: native managed-auth execution.

## Provider, credentials and evaluation limits

User-selected model: Xiaomi `MiMo-V2.6-Flash`, native provider
`xiaomi-token-plan/mimo-v2.6-flash`, endpoint
`https://token-plan-ams.xiaomimimo.com/v1`. Credentials stay in the existing
OpenClaw managed authentication store. Never print/export keys or ask for them
in chat. Direct automated Token Plan HTTP is blocked before key lookup; use
native OpenClaw. No silent PAYG/model/provider fallback. The user offered
DeepSeek if Xiaomi capacity is insufficient; any provider change is a separate
matched cohort, not a substitution for individual cells.

Thinking disabled, temperature 0.3, input cap 65,536, output cap 2,048, JSON mode
enabled, up to four native workers/two sequence jobs in the complete pilot.
Flash credit estimate: cached input 2, uncached input 100, output 200 per token;
omit the off-peak discount conservatively. Budget every actor/learning call.
Unknown usage retains reservations; trusted known failures reconcile usage.
Provider/budget/persistence failures abort and retain traces. Typed top-level
solver step-cap failures count incorrect and continue; never let `{}` pass a
negative/nullable answer key after a failed execution.

Native execution pins OpenClaw 2026.10.2 and private entry
`agent-exec-DcSrtj25.mjs`, SHA-256
`a638bf91efbd775ab4b2d66fd0d6e124074b6edcbad8f85a487e07dab25b8504`.
Native system instructions remain; serialized fixture roles are a fidelity
limitation. Native retry/overhead bounds cannot be independently guaranteed.
Offline proof confirmed unknown tools can cause extra native model invocations
even with tools disabled; this does not prove prior timeout causes. JSON-mode
propagation is verified but does not guarantee schema adherence. An old exit137
remains unexplained; no OOM evidence and no integrity guard was disabled.

The paper controller reproduces documented algorithmic structure with actual SDK
primitives, K2/N2, role/perspective stores and published thresholds. Original
hierarchy instructions, benchmark assets and full reset/seed protocol were not
released; do not call this exact paper-benchmark reproduction. Paper stores use
sequence-only experiment isolation, not EvolveClaw's audience/project routing.

## Codex-account handoff and Git

User reported 11% Codex allowance remaining and has another account. The earlier
“two to five batches fit” estimate was unsupported. MiMo experiment tokens and
Codex authoring/debugging/analysis allowance are separate; no measured conversion
exists. Minimize unnecessary repeated monitoring. Save progress before lengthy
work so a new account can continue from disk without rerunning complete trials.

GitHub `gh` was unavailable and local Git author/auth was not configured.
Previous publishing used connected GitHub create_tree/create_commit/update_ref
with expected head SHA, then fetched and verified the local index/tree before
`reset --soft` to the matching remote commit. Do not configure global identity,
force-push, hard-reset or disclose credentials. If publishing is authorized and
the other account has a different connector, inspect its access first. PR #2
is attached to this chat; attach it to a new chat if working on that PR there.

## Latest checkpoint — urgent account handoff

The user is about to exhaust Codex credit and explicitly requested this update.
**All 550 requested sequences are authored and exported; no new paid evaluation
has run. Source changes are saved locally but NOT committed or pushed yet.**
Remote `feature/evolveclaw-next` was checked and still points to `fb75c96`.
Do not assume GitHub already contains this handoff or these new fixtures: open
this same workspace or transfer the uncommitted files before switching machines.

Resume in this order:

1. Read `git status --short`; preserve all changes. Both agents have finished
   and released their files. No agent work remains to wait for.
2. Full-suite verification **completed successfully just before handoff**:
   **134 tests and 45 subtests passed in 140.39 seconds**. Session 50789 exited
   zero. `git diff --check` passed. No test process remains to collect and no
   repeat is needed unless source changes. The focused authoring tests also passed.
3. Inspect the saved export and 55 zero-call plans. Counts and file hashes were
   verified. The new batches are ready for real-model diagnostics, subject to
   concrete execution guards/protocol review; no new model results exist yet.
4. Commit/publish the 17 changed/new source, test and documentation files to the
   existing development branch/draft PR #2 once verification passes. Follow the
   GitHub lease workflow above if local Git auth/author remains unavailable.
   No merge or live activation. The user previously authorized repository work.
5. Start real-model diagnostics only after selecting concrete current guards
   and reviewing the execution protocol. This authoring turn did not start new
   paid calls. Do not reuse the pilot's tiny leftover local guards as a balance.
   Preserve any failed/incomplete trials and keep held-out outcomes out of tuning.

Saved artifacts (ignored by Git, present on this machine):

- `artifacts/evaluation/task-batches-20261014/manifest.json` — all 55 batches;
  `public/sequences.json` and `scorer-only/scoring_keys.json` are separate.
- `artifacts/evaluation/task-batch-plans-20261014/` — **55 completed zero-call
  MiMo plans**, ten sequences/all five conditions each: 2,750 total scheduled
  sequence-condition runs. Plan caps are illustrative, not spending approval.
- Public file SHA-256:
  `29287c6434c51e5ec67e06d3f2756eb63a41535f69f4f016a51575bfabd28db0`.
- Scorer-only file SHA-256:
  `f11fd9b27499038bd926571a57a97e0c6aa982b454dccfa68d9e1c78f96d00d0`.

Useful continuation commands from `/home/broedkrumme/projects/EvolveClaw`:

```sh
git status --short
PYTHONPATH=server:. /home/broedkrumme/evolveclaw-research/test-venv/bin/python -m pytest -q
PYTHONPATH=server:. /home/broedkrumme/evolveclaw-research/test-venv/bin/python -m evaluation.batches
```

See `docs/task-batches.md` for complete export and zero-call CLI planning
commands, batch IDs and live-run requirements. The export directories already
exist; use a new name if regenerating and compare the hashes. Do not overwrite.

### Detailed implementation checkpoint

- Handoff created before new diagnostic task implementation.
- The five diagnostic batches and 50 held-out batches are authored (550
  sequences). Both authoring agents released their files and passed their tests.
  The full regression suite passed (134 tests, 45 subtests); all 55 offline plans
  are saved. No authoring or offline-validation work remains.
- No new paid evaluation has been started for them.
- Next: publish the saved repository changes, then review diagnostics execution
  guards/protocol and run the planned real-model evaluation as a new cohort.
- Preserve the completed pilot artifacts and do not retune using held-out data.

Implementation checkpoint (authoring and offline verification complete):

- Root added `evaluation/batches.py`: five diagnostic/50 held-out ten-sequence
  batches, variant spreading, public/scorer-only export, zero-call preparation.
- Root extended ToolFixture with optional input_schema/handler, ScoringKey with
  grading, and FakeWorld with the coding-check seam. Old static tools stay strict.
  `real_agent.py` explains dynamic code arguments only for tasks advertising them.
- Root added coding/writing grading dispatch, diagnostic/heldout and `--batch-id`
  selection in run_models, updated obsolete held-out-placeholder tests, and added
  `tests/test_batches.py` for no-spend planning/export and mocked all-adapter flows.
- `/root/openclaw_compatibility` owns only NEW `evaluation/coding_tasks.py` and
  `tests/test_coding_tasks.py` (coding fixtures and constrained execution).
- `/root/simulation_eval` owns only NEW `evaluation/role_tasks.py` and
  `tests/test_role_tasks.py` (research/writing/planning/data fixtures and oracle).
  Both agents have completed and released their files in this same filesystem.
- APIs: coding_sequences(split), noncoding_sequences(split), coding_response(task),
  noncoding_response(task), public_code_check(public_spec,args),
  grade_code(response,private_grading)->failed-field list. Splits diagnostic/heldout.
- Coding is complete: six tests passed, 440 correct repairs pass actual private
  regression execution and all 440 original snippets fail a real regression.
  All four task states have fresh inputs within each sequence.
- Root batch integration: five tests passed (54.23s), including all 55 zero-call
  plans, exported file hashes/private-key separation, independent writing gates,
  and all five actual learning adapters for one sequence in each category with
  a mocked provider. Coding adapters also use actual dynamic public code.check.
- Writing scorer now checks token boundaries and adjacent negation, in addition
  to structured facts/word/content limits. This is still not a semantic judge.
- Noncoding is complete: ten tests passed, all 1,760 task states have an
  independently derived public-observation answer, and each family's raw data
  is fresh across variants/task states after record IDs are removed. Includes
  88 noncoding scope-switch and 88 recovery sequences. These labels alone do
  not establish populated-memory scope protection or learning benefits.
- Export completed at `artifacts/evaluation/task-batches-20261014/`: 550
  sequences, 55 batches, separate public fixtures and scorer-only keys.
  All 55 persisted zero-call plans completed successfully. The full regression
  suite passed: 134 tests and 45 subtests. No paid model calls started.
  No paid model calls started.

## Continuation checkpoint — 14 October 2026

The next account read this handoff and preserved all 17 changed/new files.
Export hashes match the checkpoint above. All 55 saved plans were inspected:
55 unique batch IDs, 50 sequence-condition runs each, 2,750 total, zero calls,
complete selections and no spending authorization. `git diff --check` passed.
The recorded full-suite result remains applicable: evaluation source is unchanged
since that verification. Only this continuation note was added.

Publication is being completed on `feature/evolveclaw-next` and draft PR #2,
using the connected GitHub account and an expected-head lease against `fb75c96`.
Verify the current branch/PR head before continuing. No merge or live activation.

The native execution protocol was reviewed against
`docs/native-openclaw-evaluation.md`, `docs/task-batches.md` and the runner:
use matched MiMo Flash identity, disabled thinking, temperature 0.3, JSON mode,
65,536 input/2,048 output caps and isolated deny-all native profile; use one
shared accounting ledger for every condition and learner call. Keep efficiency
as the fixed paper primary, grader keys private, and sequence memories isolated.
Record exact execution settings, preserve failed runs and unknown reservations,
and keep held-out model outcomes out of tuning. Native operational limits do not
guarantee lower-level provider spending.

**Next required input: concrete diagnostic spending allowances** (raw-token,
Xiaomi-credit and request caps, and whether caps cover one batch or all five).
The illustrative saved plans do not authorize spending; the pilot's leftover
guards do not establish current account balance. No new paid calls have run.
After selecting allowances, prepare a fresh isolated native profile/output
directory and execute diagnostic batches as a new recorded cohort.
