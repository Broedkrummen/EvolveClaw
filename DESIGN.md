---
version: alpha
name: EvolveClaw memory controls
description: Inspectable learned guidance within the OpenClaw dashboard
colors:
  background: "#ffffff"
  text: "#17243a"
  muted: "#526079"
  border: "#d6deeb"
  primary: "#2457b8"
  danger: "#b42335"
typography:
  sans:
    fontFamily: "system-ui, sans-serif"
  mono:
    fontFamily: "ui-monospace, monospace"
rounded:
  DEFAULT: "0.5rem"
  panel: "0.75rem"
spacing:
  panel: "1.25rem"
  gap: "1.5rem"
---

# EvolveClaw memory controls

## Overview

An inspection notebook for the OpenClaw owner: the rule, its supporting observation,
and the change that can be undone. This is a product/admin surface for managing
learned guidance. It inherits the host's visual identity, rather than adding a
marketing identity or performance claims. The signature is evidence and dated
changes placed beside each rule. User choices come from docs/next-version-plan.md.
English labels are the first release language; numbers and dates follow the host
locale. No Japan-specific market or data flows are in scope.

## Colors

Model B token ownership: OpenClaw theme variables are canonical. The values above
are fallbacks only, implemented once in plugin/src/memory-ui.css. Host --card,
--text, --muted, --border, --accent, and --destructive map to the corresponding
--ec-* roles. Both native page and panel consume the same CSS and mount function.
Colors supplement text labels; status, scope, and errors remain readable without
color. Host-provided light/dark themes retain their meaning.

## Typography

Inherit the host font for guidance and labels, with a system fallback. IDs use a
monospace utility face. No external font downloads or font swaps. Guidance wraps;
identifiers remain selectable. Dates use the active locale and user's local zone.

## Layout

Two columns on wide screens: rules on the left; evidence, history, and usage on
the right. At 800px the layout becomes one column. The page scrolls naturally.
Scope selection and refresh stay above the content. Loading and errors reserve
text space. The page shows a bounded 200-record view, not an unbounded table.

## Elevation & Depth

Flat host surfaces and borders. Avoid decorative shadows and animated counters.
Use visible scrollbars for owned overflow regions. Forced colors stay system owned.

## Shapes

Half-rem control corners; three-quarter-rem panels. Maintain the host picker shape.

## Components

Canonical select owner: host.components.mountSelectPicker for recorded scopes;
native select for the simple status filter, accepting operating-system popup
geometry. Canonical command/service behavior: plugin/src/memory-controls.ts.
Canonical notifications: one inline live region and persistent error region in
the shared mount. Canonical scrollbar: plugin/src/memory-ui.css, scoped to all
plugin-owned surfaces. No forms, dates, or bulk-selection flows are introduced.

## Do's and Don'ts

- Show whether evidence is an observation or a model confidence estimate.
- Preserve operator read-only access, failed-change recovery, and revision checks.
- Present historical scope labels as recorded scope; they confer no learning authority.
- Keep cost unknown when rates or provider usage are missing.
- Never show a mocked benchmark result as a real task-reliability improvement.
