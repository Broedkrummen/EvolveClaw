# First MiMo pilot results

The fresh all-five comparison completed: repaired v0.2, improved v0.3, the released SDK and the experimental full-paper method each passed **3/4 future probes**; learning disabled passed **2/4**. The original four completed conditions each answered **3 of 4 future probes correctly**. Their observed outputs were identical: two correct booking answers, one incorrect same-user preference answer, and one correct separate-user preference answer. This two-family operational pilot shows no measured learning benefit and cannot establish that the versions are equally effective.

The experiment used `xiaomi-token-plan/mimo-v2.6-flash` through isolated native OpenClaw execution, thinking disabled and temperature 0.3. Task tools were fake and each condition had separate state. It exercised the actual historical/current sidecar algorithms and released SDK, rather than scripted learning rules, but it did not activate or evaluate the plugin in the user's ordinary OpenClaw conversations. The [pilot protocol](mimo-pilot-protocol.md) records the execution route, restarts, limits and changes. Raw artifact links below refer to local Git-ignored files and are not public GitHub downloads.

## Original completed results

| Condition | Booking: failed operation | Booking: completed operation | Preference: same user | Preference: separate user | Future-task success |
| --- | --- | --- | --- | --- | --- |
| Learning disabled | Correct | Correct | Incorrect | Correct | 3/4 |
| Repaired EvolveClaw v0.2 | Correct | Correct | Incorrect | Correct | 3/4 |
| Improved EvolveClaw v0.3 | Correct | Correct | Incorrect | Correct | 3/4 |
| Released SCOPE SDK 0.1.3 | Correct | Correct | Incorrect | Correct | 3/4 |

The two booking probes were `pilot.booking-failure.01.failure` and `.success`; the preference probes were `pilot.user-preference.01.same-scope` and `.separate-scope`. An initial learning task and authored feedback preceded the probes. Initial tasks and feedback are not part of the four-probe success denominator.

The first three conditions completed together in the initial attempt. SDK booking and preference completed in explicitly identified diagnostic continuations, using the same model, sampling settings and tasks. Native scheduling and diagnostic instrumentation changed, so these are preserved results across continuations, not a single uninterrupted run or a fair comparative latency study. No completed paper-method sequence score exists from the original attempts; those partial runs remain in the consumption accounting below.

| Source result artifact | Complete cells used here | SHA-256 |
| --- | --- | --- |
| [Initial comparison results](../artifacts/evaluation/native-mimo-first-pilot-20261013/comparison/sequence_results.json) | Learning disabled, repaired and improved; both sequences | `a71bcc135c92e6d8248aea30ad73d917cc4b956856a5719b867ec18f926994f4` |
| [SDK booking continuation](../artifacts/evaluation/native-mimo-sdk-diagnostic-20261013/comparison/sequence_results.json) | SDK booking | `0bde16ba1fd4f75f21c40adf5da1bae0d247e305b1699eaa0647a540cfa71bc5` |
| [SDK preference continuation](../artifacts/evaluation/native-mimo-reference-continuation-20261013/sdk-preference/comparison/sequence_results.json) | SDK preference | `7d36dd6b6f99f2eefdc9b2f840f023aac35b0dc8d8e1e90badf75559c8c7dad1` |

These eight sequence-condition cells contain sixteen future-task measurements, but only **two authored families and four distinct future probes**. Repeating a probe across conditions does not create an independent task. Improved-versus-repaired has zero observed paired differences here; an efficacy confidence claim would be unjustified.

## What the preference result measures

The [preference fixture](../evaluation/scenarios.py) starts by asking for the user's usual diet while exposing only an `omnivore` tool default. Its private initial target is `plant-based`, which has not yet been supplied to any solver. That initial miss is an unavailable fact, rather than an observed avoidable reasoning mistake.

The authored feedback then explicitly supplies the plant-based preference. The same-user probe measures recall of that fact across a fresh solver history; the separate-user probe expects the omnivore default for another user. All four conditions returned `omnivore` on both probes. The separate-user answer is correct, but it does not demonstrate a scoped-memory advantage: none of the conditions had retained the specific plant-based fact to leak into that answer.

Application terminal synthesis receives bounded prior conversation context, while the next solver and SDK step reflection do not receive native chat history. The application quality-analysis frequency of three skipped reflection on the feedback turn. After the same-user miss, repaired and improved EvolveClaw accepted general advice to respect a stated preference; neither lesson contained the plant-based fact, and no later same-user probe tested that new advice. The SDK preference continuation recorded seven step reflections and accepted no guideline. See the [SDK learning events](../artifacts/evaluation/native-mimo-reference-continuation-20261013/sdk-preference/comparison/run-001/scope_sdk_reference/pilot.user-preference.01/memory/learning_events.json) and [improved preference trace](../artifacts/evaluation/native-mimo-first-pilot-20261013/comparison/run-001/improved/pilot.user-preference.01/scorer_only_trace.json).

This is a boundary test of semantic recall, history delivery and reflection timing. It cannot establish that procedural SCOPE learning is ineffective or that ordinary OpenClaw conversation memory fails. The booking probes also offer little room for improvement: the base assistant instructions already require checking tool results, and learning disabled solved both.

## Consumption before the new matched cohort

The following table includes every completed or stopped live attempt documented in the protocol before the fresh frozen-source cohort. It excludes the fresh completed cohort reported below. Each source ledger is included once; completed rows are not charged again as a separate report.

“Known tokens” means native-reported input-plus-output usage, including reported failed executions. “Accounted tokens” includes unresolved reservations and the one historical correction. Credits retain conservative rates and historical guards; they are not authenticated provider billing. Reserved execution requests do not establish the number of underlying provider attempts. Dollar cost remains unknown.

| Attempt and source | Reserved/issued execution requests | Known tokens | Accounted tokens | Accounted credits | Disposition |
| --- | ---: | ---: | ---: | ---: | --- |
| [Three transport smokes](mimo-pilot-protocol.md#first-live-transport-smoke) | 3 | 8,172 | 8,172 | 431,636 | Completed |
| [Initial matched comparison](../artifacts/evaluation/native-mimo-first-pilot-20261013/comparison/incomplete.json) | 78 | 240,343 | 510,679 | 33,762,220 | Worker response lost; six cells completed |
| [SDK booking diagnostic](../artifacts/evaluation/native-mimo-sdk-diagnostic-20261013/comparison/summary.json) | 20 | 69,094 | 69,094 | 2,248,136 | Completed |
| [SDK preference continuation](../artifacts/evaluation/native-mimo-reference-continuation-20261013/sdk-preference/comparison/summary.json) | 14 | 49,563 | 49,563 | 1,611,764 | Completed |
| [First paper pair](../artifacts/evaluation/native-mimo-reference-continuation-20261013/paper-pair/comparison/incomplete.json) | 175 | 635,962 | 703,546 | 28,004,160 | Interrupted for confirmed harness defects |
| [Repaired paper pair](../artifacts/evaluation/native-mimo-paper-repaired-harness-20261013/comparison/incomplete.json), with [historical correction](../artifacts/evaluation/native-mimo-paper-repaired-harness-20261013/historical-failed-usage-reconciliation.json) | 109 | 539,122 | 741,874 | 47,931,208 | Interrupted after native timeouts; correction included once |
| [Ad hoc JSON checks](../artifacts/evaluation/native-mimo-json-gate-20261013/usage.json) | 2 | 6,247 | 6,247 | 215,848 | One response failed JSON parsing |
| [Exact-prompt JSON gate](../artifacts/evaluation/native-mimo-json-exact-gate-20261013/usage.json) | 3 | 9,263 | 9,263 | 271,068 | Three checks passed |
| [First JSON matched attempt](../artifacts/evaluation/native-mimo-json-matched-pilot-20261013/comparison/incomplete.json) | 15 | 44,039 | 111,623 | 8,034,864 | Stopped at a bounded solver failure; no complete cell |
| **Total before the current cohort** | **419** | **1,601,805** | **2,210,061** | **122,510,904** | **608,256 tokens remain without confirmed usage** |

The repaired-paper original snapshot records 385,899 known successful tokens and 723,819 accounted tokens. Two failed envelopes additionally report 153,223 tokens, replacing two 67,584-token reservations for raw-token reconciliation: only the **18,055-token excess** is added to the original accounted total. Thus the table's 741,874 already includes the correction; neither the failed totals nor the correction should be added again. The original snapshot is preserved, and its 47,931,208-credit guard is not refunded.

The initial raw-token cap was raised from two million to four million during the documented diagnostic phase; the total credit cap remained 250 million. Before the current cohort, the remaining local allowances were **1,789,939 raw tokens and 127,489,096 credits**. These are local conservative allowances, not a verified subscription balance. The complete fresh cohort is added once in the cumulative totals below.

## Completed fresh all-five cohort

All ten sequence-condition cells completed from frozen commit `67ebdd579b99e26cb8f50f6558ce513ee835b962`, with the same model, temperature, JSON mode, fake tools and nested-answer protocol. The four-worker pool ran two sequence jobs; paper paths were parallel and independent. Its [source manifest](../artifacts/evaluation/native-mimo-json-complete-pilot-20261013/source-manifest.json) and [plan](../artifacts/evaluation/native-mimo-json-complete-pilot-20261013/comparison/plan.json) preserve provenance. Report this cohort separately from the earlier continuations.

| Condition | Future success | Assistant requests | Learning requests | Known tokens | Estimated credits | Format-error steps | Accepted lessons |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Learning disabled | 2/4 | 20 | 0 | 65,876 | 1,708,780 | 9 | 0 |
| Repaired v0.2 | 3/4 | 14 | 6 | 67,446 | 1,729,592 | 0 | 2 |
| Improved v0.3 | 3/4 | 15 | 6 | 70,600 | 1,931,596 | 1 | 2 |
| Released SCOPE SDK | 3/4 | 14 | 17 | 113,075 | 3,754,072 | 0 | 2 |
| Paper K2/N2, efficiency primary | 3/4 | 74 | 235 | 1,208,846 | 42,931,452 | 11 | 35 |

Usage includes initial tasks, feedback and future probes. Execution requests are native wrapper requests, not independently measured provider attempts. Accepted-lesson counts are applications' terminal reflections, SDK step reflections, or paper role-step reflections respectively; these have different boundaries and are not comparable effectiveness measures. Format errors include invalid JSON and simulator-contract errors.

The paper's **fixed efficiency primary scored 3/4**; thoroughness scored **2/4**, and the benchmark-style oracle union scored **3/4**. The union is not a deployable answer selector and is not compared to the single-attempt flat baselines. The paper method used 309 requests, including 235 learning requests, versus improved v0.3's 21 requests and six learning requests. It accepted 35 lessons without exceeding the other learning conditions' future score. This overhead is specific to short synthetic tasks, recovery loops, this model and the native wrapper; do not transfer it to the original paper benchmarks or a monthly learning budget.

All primary learning conditions passed both booking probes, failed the same-user preference probe and passed the separate-user probe. Learning disabled additionally failed the completed-booking probe after repeated correct-looking JSON answers had extra function text appended; its warmup also reached the five-step cap. Those two unfinished attempts remain incorrect, with raw traces preserved. The baseline's additional miss is a format failure, not evidence that learning improved reasoning. Improved-versus-repaired has zero paired differences on this sample.

Thoroughness's additional preference miss returned a caveated sentence in `value` and put the correct `omnivore` category in a different field. The strict exact-field grader rejects it. This is not evidence of cross-user memory leakage. These scores measure authored structured-output contracts; a larger everyday-assistant study needs public output contracts and separate semantic, procedural and formatting diagnostics. No primary learner retained the corrected plant-based fact for the same-user probe. Scope isolation, stale-advice handling and rollback efficacy are not established by this pilot's outcomes.

The complete cohort recorded **401 successful native requests, 1,525,843 known/accounted tokens and 52,055,492 conservative estimated credits**, with zero unknown usage, provider-limit violations or blocked ledger status. Dollar cost and lower-level provider-attempt count remain unknown. Every reported completed envelope had one assistant turn; real tools stayed disabled. The [machine-readable results](mimo-first-pilot-results.json) contain numerical diagnostics and final artifact hashes. Raw evidence remains local:

- [Complete summary](../artifacts/evaluation/native-mimo-json-complete-pilot-20261013/comparison/summary.json), SHA-256 `1d5c2e8c940ddebf0d5a9171bbd8fd7888ad8aa3f5b28ed9a4906c529bc9f481`.
- [Complete sequence scores](../artifacts/evaluation/native-mimo-json-complete-pilot-20261013/comparison/sequence_results.json), SHA-256 `678d4d160e671cecf8f345b28704fa9e80e833521187d595743d0ef87d68e7c7`.
- [Native execution evidence](../artifacts/evaluation/native-mimo-json-complete-pilot-20261013/comparison/native_execution.json), SHA-256 `eb158e69a875cb1f255e22726f89ece0994239debc9b4b2d7ea81f9e1501ee4c`.

Including every earlier smoke, stopped attempt and historical correction once, cumulative accounting is **820 execution requests, 3,127,648 reported known tokens, 3,735,904 conservatively accounted tokens and 174,566,396 accounted credits**. The remaining local guards are **264,096 raw tokens and 75,433,604 credits**. The 608,256-token difference remains unconfirmed historical usage; it is not new consumption from this completed cohort. These totals are not an authenticated subscription balance.

The operational all-five gate is complete. It establishes runnable comparison mechanics and a first cost measurement, not superior reliability or readiness to make a held-out efficacy claim. Larger evaluation needs the fixture changes below.

## Changes needed before a larger learning-benefit study

These are evaluation design implications, not measured benefits or changes to the running cohort:

1. **Use observable, avoidable mistakes.** The learning opportunity must expose enough public evidence to establish the mistake. Remove unavailable initial targets from reasoning-error counts, or score appropriate uncertainty. Audit for a baseline ceiling before scaling; do not weaken ordinary assistant instructions merely to manufacture an advantage.
2. **Separate procedural reuse, factual recall and output-format failures.** Tool verification, normalization and error recovery test procedural lessons; remembering a diet or project fact tests semantic memory. JSON/schema errors, extra function-call text, and consequent step-limit failures need a separate diagnostic stratum. Format changes require a new matched cohort; configured native JSON mode does not guarantee schema adherence. Keep these failures in overall task-success denominators; do not count a negative completion answer as correct when no required tool was executed. Report explicit information-admission and retrieval contracts. A procedural optimizer's general advice is not evidence that it stored a specific fact.
3. **Pair history and reflection ablations.** Compare matched fresh-state and continuous-history executions, including a history-only control, so ordinary conversation recall is distinguishable from learned memory. Keep frequency-one and default frequency-three learning runs as separately identified configurations. Run enough learning turns to exercise the configured reflection boundary before future probes; never tune frequency using held-out outcomes.
4. **Verify memory before interpreting scope and undo.** Preserve accepted/rejected proposals, the stored rule or fact, its scope, and what was retrieved before the probe. Test an actual populated memory against a different user/project, changed evidence and targeted rollback. Empty-memory success cannot establish scope isolation, and failed or rejected learning opportunities must remain in the overall denominator.
5. **Test transfer after sufficient learning.** Include longer public learning histories and fresh tasks after a lesson can actually be available. Test both continuing adaptation and a frozen-memory transfer condition. The current fresh directory per short sequence cannot by itself establish strategic improvement accumulated across a user's longer history.
6. **Increase independent task families and freeze the comparison.** The authored development split has 100 sequences in 20 families, not 100 independent families; the 500 held-out slots still require authoring and review. Match model, tools, prompt/protocol, initial history and budgets across conditions, preserve all bounded failures, and analyze family/sequence dependence. Prespecify improved-versus-repaired, a worthwhile improvement, regression tolerance and stopping rules; determine sample size from measured paired disagreements rather than a desired headline task count.

Infrastructure diagnosis and prompt repairs should produce a new frozen matched cohort, as here. They should not replace inconvenient task outputs or silently alter a learner while an efficacy cohort is running. The [larger evaluation plan](simulation-evaluation-plan.md) remains a design proposal; the results above supply operational evidence and fixture warnings, not proof of superior task reliability.
