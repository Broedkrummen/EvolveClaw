# Project review — EvolveClaw

Reviewed 20 October 2026 (Europe/Copenhagen).

Branch: `feature/evolveclaw-next`. HEAD: `8ddbf638cc9cb8dd2d1d33997d374fd25f7a98aa`. Pre-review status entries: 1.

## Assessment

The v0.3 plugin and evaluation harness are implemented, but the current diagnostic study is incomplete and explicitly stopped. The most important next work is diagnosis and experiment redesign, followed by documentation and evidence preservation. There is no evidence of an efficacy winner.

## Plan compared with actual state

| Intended outcome | Evidence inspected | Actual position / work needed |
| --- | --- | --- |
| Scoped automatic learning, controls and native dashboard | `plugin/src/index.ts`, `memory-controls.ts`, `server/memory_store.py`, `server/task_optimizer.py`, README, migration and handoff | Real implementation exists, including scoped SQLite history and revision controls. Earlier package/runtime receipts are historical, not a fresh compatibility certification. |
| Five diagnostic categories and 500 held-out sequences | `evaluation/batches.py`, `coding_tasks.py`, `role_tasks.py`, `docs/task-batches.md`, exported manifest | 50 diagnostic + 500 held-out sequences are authored; 5 + 50 batches exist. Both exported public/scorer hashes match the saved manifest. All 55 zero-call plan JSON files exist. |
| Complete 250-cell diagnostic comparison | Saved `sequence_results.json` files across original and continuation outputs | Exactly **40 unique scored cells**, all coding: 10 each for learning-off, repaired-v0.2, improved and SDK reference. Paper condition has no completed scored cell; **210 cells remain**. Other categories are unfinished. |
| Reliable long-running native experiment | Latest local `HANDOFF.md`; continuation 18 `status.json`; native transport source | Repeated setup/SQLite-related failures and very expensive unfinished paper sequences remain material. Continuation 18 ended `aborted`, 74 completed responses / 76 accounted requests, 466,467 accounted tokens and 27,374,928 estimated credits, with zero new scores. These are C18 totals, not whole-study totals or account balance. |
| Valid efficacy conclusion | `docs/mimo-first-pilot-results.md`, readiness and task-batch docs | Earlier small five-condition pilot exists; it cannot establish improved everyday reliability. Partial diagnostics cannot be reported as a completed cohort. Held-out execution remains excluded. |

## Findings and next steps, in order

1. **Preserve the explicit paid-testing stop.** The last local handoff section, “Current diagnostic stop — 15 October 2026,” overrides older running labels. The user stopped paid testing and required review of the long paper sequence before further spending. This review authorizes no restart. The C19 continuation is an unlaunched, unvalidated draft; its output directory is absent.
2. **Diagnose before another continuation.** Inspect the paper controller's call growth/termination and native SQLite cleanup path with offline instrumentation and bounded reproduction. The updater-contention explanation is a hypothesis: C18 saw no cleanup error before cancellation, which does not prove the cause. Preserve unknown-usage reservations and original failures.
3. **Reconcile documentation with disk.** README still says the 500 held-out slots need authoring; readiness/task-batch docs still say new paid diagnostics have not started. Both are outdated. `chat-checkpoint.json` says running but dates from October 14; original `cohort-status.json` is aborted and later continuation state is authoritative. Keep the full chronology rather than deleting failures.
4. **Preserve the unpublished handoff and ignored evidence.** `HANDOFF.md` had 305 added lines before this review. The fixture/harness commit is published, but these later diagnostic notes and ignored attempt artifacts are local. Create a deliberate backup/checkpoint before moving accounts or machines. Do not publish private evaluator traces without review.
5. **Only after a revised protocol and applicable explicit authorization**, run bounded diagnostics with fresh concrete guards, retaining completed cells and all accounting. Freeze the full-study protocol before held-out outcomes. Requalify the actual package against its selected host before release; current development dependencies pin OpenClaw 2026.10.2.

## Evidence and limitations

Read: README, complete HANDOFF including its local continuation history, evaluation readiness, task batches, next-version/evaluation plans, manifests, package metadata and the implementation areas above. Saved diagnostic rows were counted directly; fixture and scorer exports were hashed independently. Historical test counts (including 134 Python tests / 45 subtests at authoring) were not rerun. This is a source/evidence assessment, not new model, browser, package or production acceptance.

GitHub `feature/evolveclaw-next` matches local `8ddbf638cc9cb8dd2d1d33997d374fd25f7a98aa`. GitHub main is `f2bb6bba282590f92dc15ec706b4178304577b1f`; local development is nine commits ahead of main. No newer same-branch remote version was found. Local handoff changes are additional to that comparison.

## Diagnostic status update — 23 October 2026

This dated update supersedes the earlier 40/250 and 210-missing snapshot above.
The current paid cohort is 44/250 scored with 206 unscored. The latest two
continuations produced no new scored cells: continuation24 completed two native
calls, then ended with `native-worker-protocol-eof`; the native worker had exited
with SIGTERM, whose cause remains unresolved. Total accounted usage is 2,538
requests, 13,097,930 tokens and 651,658,888 quota credits, with unknown
reservations retained.

A fresh offline replay completed 206/206 missing cells and 824/824 mock task
states with no failures or network/API calls. It is infrastructure evidence, not
paid efficacy evidence.

The user approved request-cap increases only to the offline demand: minimum
total caps global 13,858; coding 4,625; data 2,304; planning 2,304; research
2,321; writing 2,304. Original token and credit caps remain unchanged. The
runner/preflight have not yet been updated to apply this approval. The user
explicitly directed the current agent not to restart the paid test; another
agent will handle it due to quota. See
[PAID-DIAGNOSTIC-HANDOFF-2026-10-23.md](PAID-DIAGNOSTIC-HANDOFF-2026-10-23.md)
for the current execution constraints and evidence paths.
