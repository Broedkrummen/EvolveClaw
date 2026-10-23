# Paid diagnostic handoff — 23 October 2026

This handoff reflects the latest local evidence for the frozen Xiaomi MiMo diagnostic cohort. It does not authorize this agent to start a paid run: the user explicitly said another agent will do the next run because of quota. If you are that assigned agent, check the live process and account state before acting so you do not duplicate a run.

## Current cohort state

- Scope: the exact 250 diagnostic condition/sequence cells; no held-out tasks.
- Paid scores: 44/250; 206 remain unscored.
- Accounted usage: 2,538 native requests, 13,097,930 tokens, 651,658,888 quota credits. Unknown reservations remain included.
- Runtime selected for the recent continuation: OpenClaw 2026.10.6, Node 26.12.1, Xiaomi MiMo `mimo-v2.6-flash`. The native entry hash was `9f5c19fc06fcb592a3ec792ef800d3668da1b504f968bb78b8d6c38ea1c7a72f`.

Continuation23 failed before a completed model reply because its frozen bridge expected a missing OpenClaw 2026.10.5 entry. Continuation24 used an isolated 2026.10.6 bridge and completed two calls (3,485 and 3,691 tokens); request 3 ended with `native-worker-protocol-eof` after the worker had exited with SIGTERM. No cell scored. The cause of the worker exit remains unresolved. Preserve the unknown request reservation and all prior ledgers.

A fresh offline replay completed all 206 missing cells and 824 mock task states with zero failed states, network attempts, live API calls, or denied processes. This validates the local evaluator path only; it does not score paid cells.

## Request-cap approval

The offline replay schedules 11,320 model requests across the remaining cells. The user approved increasing **request caps only** to this demand. The minimum total caps implied by current use plus planned requests are:

| Scope | Planned remaining calls | Minimum total request cap |
|---|---:|---:|
| Global | 11,320 | 13,858 |
| Coding | 2,140 | 4,625 |
| Data | 2,304 | 2,304 |
| Planning | 2,304 | 2,304 |
| Research | 2,268 | 2,321 |
| Writing | 2,304 | 2,304 |

Keep original token and credit caps unchanged: global 100,000,000 tokens / 10,000,000,000 credits; each category 20,000,000 tokens / 2,000,000,000 credits. These request counts come from mock control flow and are estimates of planned calls, not provider usage. They include no retry buffer. Do not exceed the approved request totals, token caps, or credit caps without new user approval.

This approval has not yet been applied to runner code. The current offline bundle's `preflight.py` still enforces old caps, and `prepared_runner.py --execute` remains blocked by the consumed earlier retry authorization. Do not reset the historical two-repair ledger or the consumed continuation23 authorization. Use a separate, dated, single-use authorization record and a fresh exclusive output directory for any new execution.

## Runtime snapshot and safe execution constraints

The last captured snapshot showed OpenClaw Gateway active/running, about 6.5 GiB available RAM, 3.1 GiB free swap, and zero memory PSI avg10. This can change; recheck it and verify the installed native entry hash before starting. No active diagnostic runner was found at that snapshot.

Keep prompts, fixtures, learners, graders, model settings, and source repository unchanged. Skip the 44 already-scored cells, run only the 206 missing cells, preserve accounting and unknown reservations, and never run held-out tasks. Add global and per-category request guards while retaining all token/credit limits. Stop at a budget or infrastructure failure if it cannot be repaired within the approved totals; there is no retry headroom beyond the planned request demand.

## Evidence locations

Detailed supporting evidence is retained in the operator’s local Codex diagnostics bundle; the bundle itself is not included in this repository commit.

Key files:

- `HANDOFF.md` — full chronology and takeover notes.
- `RETRY-RESULTS.md` — detailed continuation23/24 evidence.
- `verification/current-audit.json` — current cohort/accounting audit.
- `verification/matrix-restart-20261023.json` — exact offline replay.
- `verification/request-cap-feasibility.json` — cap calculation and user approval.
- `verification/runtime-health-20261023.json` — last runtime snapshot.

The main source repo is `/home/broedkrumme/projects/EvolveClaw`, branch `feature/evolveclaw-next`. Its evaluator sources remain frozen; only documentation files are being published in this commit.
