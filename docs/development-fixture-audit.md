# Development fixture audit

The development split has 100 authored sequences in 20 template families, with five variants per family. It is synthetic assistant reliability coverage, not a published benchmark or 100 independent task families. Structural tests check all 300 scoring keys against answers reachable from advertised fake tools.

A separate read-only review before model evaluation found substantial ceiling risk:

- Every scored development answer is recoverable from that task's current instructions and fresh tool output. Prior memory is not required to solve these cases.
- Instructions repeat the relevant procedure. Nineteen families need one tool; pagination advertises the next-page call arguments in advance.
- Scope-leakage and stale-advice labels identify failing probes, rather than isolating memory as the cause of failure. Rollback probes also change source facts and explicitly restate policy, so their aggregate scores do not establish a causal rollback effect.

These properties avoid manufacturing an advantage for the learning condition. They can also produce nearly perfect learning-disabled scores and little room to measure improvement. Report the development scores as reliability coverage and diagnose the ceiling before spending the full evaluation allowance.

For a later memory-specific development cohort, predeclare three additions before running it:

1. Provide a user/project convention during an earlier ordinary interaction; subsequent requests require that convention without repeating it, paired with different-scope requests that must use a different convention. Necessary information must remain available through authorized history or learned memory, rather than an evaluator-only answer key.
2. Use several observations, uncertain or transient outcomes, and dependent tools. Realistic procedural errors should require applying a lesson to a changed situation, rather than copying one field. Do not inject failures only into a baseline condition.
3. Give rollback paired probes with the same public facts and task, changing only the owner's history-undo action. This separates rollback from source refresh, prompt reminders, and unrelated memory changes.

The pilot's preference cases already test some history dependence. Native OpenClaw adds its own system policy and serializes role messages; the comparison must document that transport difference and hold it constant across conditions. Held-out fixtures remain separate and unopened; no held-out outcomes informed this audit.
