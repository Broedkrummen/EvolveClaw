# Memory control behavior

Business sources: docs/next-version-plan.md; installed OpenClaw 2026.10.2 feature
and command SDK contracts; server/memory_store.py revision and scope invariants.
Visual context: DESIGN.md.

| Capability | Canonical owner | Source of truth | Allowed variants | Verification |
| --- | --- | --- | --- | --- |
| Select/Listbox | OpenClaw mountSelectPicker; native status select | DESIGN.md | scope picker / platform status filter | tests/ui/memory.spec.mjs |
| Scrollbar | plugin/src/memory-ui.css | DESIGN.md | natural page scroll | tests/ui/memory.spec.mjs |
| Toast | shared inline status and persistent error regions | this contract | success / error | tests/ui/memory.spec.mjs |
| CRUD | memory-controls shared feature handlers | backend revision/scope API | disable / restore / assign / pause | tests/ui/memory.spec.mjs |

Queries require operator.read; mutations require operator.write. Legacy inspection
and assignment require owner/admin authority. Channel commands additionally use
the host's current owner assertion. Client-provided input cannot set an audience
or project scope. Recorded labels support management, never current learning.

All changes use expected revision. A conflict keeps the view available and asks
the operator to refresh. Disable/restore and pause/resume are reversible; they do
not require repeated confirmations. Undo changes uses the specific recorded
history ID, not a broad reset. Assignment places a legacy rule into the selected
recorded scope and leaves an undoable history entry.

Reads preserve the selected scope/status filter. Sensitive labels are not placed
in URLs. Content loads are generation-fenced; disposed or stale reads cannot
replace a newer view. Mutations remain disabled while busy or read-only. Failed
or uncertain mutations show an inline error and direct the user to refresh.
No optimistic success is displayed before confirmation from the backend.

Everyday non-repository tasks use an explicit no-project bucket within their host
audience. Unknown host audience receives no learned context and creates no rules.
Old unscoped records remain inactive history until explicitly assigned by owner.
An empty view directs the user to complete a normal task to establish a scope.

Page and panel share controls, labels, loading, empty, success, and recovery states.
Use native buttons/labels, visible focus, accessible status/error regions, and a
one-column narrow layout. UI language is English; dates/numbers use host locale.
Cost is never inferred to be zero from missing prices. No secrets appear in UI.
