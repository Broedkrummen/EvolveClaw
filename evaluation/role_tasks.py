"""Frozen synthetic non-coding tasks; private keys never enter observations.

This is authored simulator material, not real publications, correspondence,
travel advice, or an independently sampled benchmark. Variants share a family.
The offline oracle consumes only advertised FakeWorld observations; it never
receives a Sequence or ScoringKey. Writing has a limited deterministic rubric.
"""
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from math import ceil
from statistics import median

from .scenarios import FakeWorld, Feedback, Scope, ScoringKey, Sequence, Task, ToolFixture


@dataclass(frozen=True)
class Family:
    category: str
    name: str
    split: str
    lesson: str
    stratum: str = "procedural"
    stress: str = "source-change"


def _families(category, split, rows):
    return tuple(Family(category, name, split, lesson, stratum, stress)
                 for name, lesson, stratum, stress in rows)


FAMILIES = (
    *_families("research", "diagnostic", (
        ("evidence-window", "Check the declared observation-validity interval, not the newest publication date.", "procedural", "source-change"),
        ("measurement-conflict", "Compare independent measurements against the declared tolerance and preserve disagreement.", "procedural", "source-change"),
        ("causal-language", "Randomized allocation can support the declared causal contrast; an observational association cannot.", "procedural", "scope-switch"),
        ("event-denominator", "Pool event counts and sample sizes; averaging percentages loses denominators.", "procedural", "source-change"),
        ("archive-recovery", "A failed source read is not evidence of its contents; inspect the advertised frozen archive.", "error-recovery", "tool-recovery"),
    )),
    *_families("research", "heldout", (
        ("study-weighting", "Weight study means by their sample counts, rather than giving unequal samples equal weight.", "procedural", "source-change"),
        ("interval-direction", "An interval spanning zero leaves direction unresolved even if the point estimate is positive.", "procedural", "source-change"),
        ("retraction-chain", "Follow explicit withdrawal notices before including a study in an evidence list.", "procedural", "tool-recovery"),
        ("observation-recency", "Rank evidence by when the observation was made, not when a later article repeated it.", "procedural", "source-change"),
        ("population-boundary", "A study of one population does not directly establish a result for an excluded population.", "procedural", "scope-switch"),
        ("registered-endpoint", "Use the endpoint named in the registered protocol; label later substitutions separately.", "factual", "source-change"),
        ("compatible-units", "Convert each observation to the requested unit before combining measurements.", "procedural", "scope-switch"),
        ("syndication-lineage", "Count distinct originating studies, not repeated news copies of one study.", "procedural", "tool-recovery"),
        ("attrition-warning", "Compare attrition rates by assigned group; a pooled rate can hide unequal loss.", "procedural", "source-change"),
        ("absolute-risk", "Distinguish percentage-point reduction from relative percentage reduction.", "procedural", "source-change"),
        ("correlation-interpretation", "Report the sign of association without turning correlation into a causal assertion.", "procedural", "scope-switch"),
        ("multiple-testing", "Apply the explicitly stated familywise threshold to each reported p-value.", "procedural", "source-change"),
        ("bias-sensitivity", "Recompute the requested estimate after excluding the declared high-bias studies.", "procedural", "tool-recovery"),
        ("method-match", "Use measurements from the method requested, even when another method has a larger sample.", "procedural", "scope-switch"),
        ("erratum-crosswalk", "Apply a linked correction to its exact field and original study, not every nearby value.", "factual", "source-change"),
        ("evidence-absence", "When no supplied source supports the claim, report unresolved rather than guessing.", "procedural", "tool-recovery"),
        ("speaker-attribution", "Attribute a statement to the named speaker, not to the host or publisher.", "factual", "source-change"),
        ("marginal-identification", "Marginal totals alone do not identify the overlap of two groups.", "procedural", "source-change"),
        ("funding-disclosure", "Report the supplied commissioning relationship without inventing independence.", "factual", "source-change"),
        ("paired-change", "Compute changes within matched participants before averaging the paired effect.", "procedural", "source-change"),
    )),
    *_families("writing", "diagnostic", (
        ("incident-brief", "Distinguish mitigation and monitoring from a permanent resolution claim.", "procedural", "source-change"),
        ("public-excerpt", "Use the public brief and omit explicitly internal identifiers and amounts.", "procedural", "scope-switch"),
        ("tentative-announcement", "Label an unapproved proposal as proposed; an announcement cannot approve it.", "procedural", "source-change"),
        ("minutes-open-question", "Preserve an open question and its action owner rather than inventing a decision.", "factual", "source-change"),
        ("plain-language", "Apply the supplied plain-language glossary without adding a new product claim.", "error-recovery", "tool-recovery"),
    )),
    *_families("writing", "heldout", (
        ("correction-notice", "State both the replaced and corrected value in a labeled correction.", "factual", "source-change"),
        ("disputed-brief", "Preserve both reported counts and the fact that the reports disagree.", "procedural", "source-change"),
        ("quoted-speaker", "Keep the supplied quotation exact and attribute it to its speaker.", "factual", "source-change"),
        ("observable-alt-text", "Describe visible objects and actions without inferring emotion or identity.", "procedural", "tool-recovery"),
        ("invitation-details", "Include time, zone and agenda without claiming invitees confirmed attendance.", "factual", "scope-switch"),
        ("bounded-product-claim", "Limit a product claim to the measured scenario; remove unsupported superlatives.", "procedural", "source-change"),
        ("refund-review", "An approved review is not proof that a refund was issued.", "procedural", "tool-recovery"),
        ("decision-risk-brief", "Report the recorded decision and unresolved risk as distinct facts.", "procedural", "source-change"),
        ("anonymized-story", "Retain the allowed segment description while excluding direct identifiers.", "procedural", "scope-switch"),
        ("work-status", "Starting work is different from delivering its outcome.", "procedural", "source-change"),
        ("release-limitation", "Mention both the changed behavior and the supplied remaining limitation.", "procedural", "source-change"),
        ("dated-comparison", "Name the historical periods; a historical trend is not a current forecast.", "procedural", "source-change"),
        ("conditional-guide", "Preserve the branch condition and corresponding action when rewriting a procedure.", "procedural", "tool-recovery"),
        ("alternative-decline", "Decline the unsupported action while describing an available alternative without claiming execution.", "procedural", "scope-switch"),
        ("uncertain-range", "Keep the estimated range and uncertainty rather than promising an exact outcome.", "procedural", "source-change"),
        ("rounded-measurement", "Round the supplied measurement by the declared rule while retaining its unit.", "procedural", "source-change"),
        ("opt-in-draft", "Draft for the opted-in audience and omit the excluded person's identifiers.", "procedural", "scope-switch"),
        ("transit-notice", "An estimated arrival does not establish delivery; report the observed transit state.", "procedural", "tool-recovery"),
        ("attributed-review", "Separate a reviewer's opinion from a measured result and identify their different sources.", "procedural", "source-change"),
        ("glossary-translation", "Use the supplied target-language glossary consistently instead of improvising terminology.", "procedural", "source-change"),
    )),
    *_families("planning", "diagnostic", (
        ("dependency-frontier", "Select ready tasks only after every prerequisite has completed.", "procedural", "source-change"),
        ("uninterrupted-slot", "A task must fit one uninterrupted interval; do not add separated free minutes.", "procedural", "source-change"),
        ("minimum-budget", "Fund declared minimum requirements before optional extras.", "procedural", "scope-switch"),
        ("receipt-confirmation", "A queued reservation is not confirmed without the matching completion receipt.", "error-recovery", "tool-recovery"),
        ("holiday-recurrence", "Move a recurrence past declared closed dates to the next permitted open date.", "procedural", "source-change"),
    )),
    *_families("planning", "heldout", (
        ("critical-path", "A dependency network's finish is its longest prerequisite path, not the sum of every task.", "procedural", "source-change"),
        ("travel-gap", "Allow travel time between locations before selecting a following appointment.", "procedural", "scope-switch"),
        ("capacity-packing", "Respect the shared capacity across all selected items and apply the stated priority order.", "procedural", "source-change"),
        ("cancellation-boundary", "Apply the exact inclusive or exclusive cancellation boundary in the fictional policy.", "procedural", "scope-switch"),
        ("lead-time", "Work backward by the declared preparation days rather than choosing the delivery date as the start.", "procedural", "source-change"),
        ("consent-invitation", "Eligibility for an invitation requires the supplied consent, not merely group membership.", "procedural", "scope-switch"),
        ("local-day", "Apply the provided fixed offset and preserve a date rollover.", "procedural", "source-change"),
        ("resource-collision", "Check overlaps for the same resource using half-open intervals.", "procedural", "tool-recovery"),
        ("energy-rest", "Insert the declared rest requirement between demanding activities.", "procedural", "source-change"),
        ("release-gates", "Publication requires every named gate, not a single approval.", "procedural", "tool-recovery"),
        ("batch-setup", "Count setup once per batch, not once per item, under the supplied processing policy.", "procedural", "source-change"),
        ("closed-route", "Exclude closed edges when finding the shortest available path.", "procedural", "tool-recovery"),
        ("parallel-handoff", "Parallel teams finish at the slower team time before the common handoff can begin.", "procedural", "source-change"),
        ("fair-rotation", "Choose the available member with the lowest assignment count; break ties by ID.", "procedural", "scope-switch"),
        ("retry-escalation", "At the declared retry threshold, escalate instead of promising another completed attempt.", "error-recovery", "tool-recovery"),
        ("priority-aging", "Recompute priority from base score and waiting time rather than trusting arrival order.", "procedural", "source-change"),
        ("contingency-trigger", "Activate a prepared contingency only when the stated trigger threshold is met.", "procedural", "source-change"),
        ("single-vendor-kit", "Choose a complete available kit from one supplier when mixed suppliers are forbidden.", "procedural", "source-change"),
        ("delegate-chain", "Follow the authorized delegate chain and stop at the first available delegate.", "procedural", "source-change"),
        ("workday-capacity", "Normalize hours to minutes and compare against the current scope's working-day capacity.", "procedural", "source-change"),
    )),
    *_families("data", "diagnostic", (
        ("join-cardinality", "Count each order once after a one-to-many line-item join.", "procedural", "source-change"),
        ("null-zero", "Exclude null observations from the denominator but retain measured zeros.", "procedural", "source-change"),
        ("locale-decimal", "Interpret separators using the supplied locale, not a remembered project convention.", "procedural", "scope-switch"),
        ("credit-sign", "Credits reduce a balance; debit and credit amounts cannot all be added positively.", "procedural", "source-change"),
        ("page-retry", "Replace a failed page attempt with its successful retry; do not duplicate successful page rows.", "error-recovery", "tool-recovery"),
    )),
    *_families("data", "heldout", (
        ("weighted-average", "Use quantities as weights instead of averaging line prices equally.", "procedural", "source-change"),
        ("nearest-rank", "Use the declared nearest-rank percentile convention and one-based rank.", "procedural", "source-change"),
        ("even-median", "Sort the observations and average the two central values for an even sample.", "procedural", "source-change"),
        ("sample-variance", "The specified sample variance divides squared deviations by n minus one.", "procedural", "source-change"),
        ("counter-reset", "A lower cumulative counter starts a new segment; count the reset reading as new increments.", "procedural", "source-change"),
        ("overlap-dedup", "Union overlapping extracts by event ID before aggregating.", "procedural", "tool-recovery"),
        ("fiscal-quarter", "Use the current fiscal start month rather than the calendar quarter.", "procedural", "scope-switch"),
        ("offset-bucket", "Apply the provided fixed timezone offset before grouping events by local day.", "procedural", "scope-switch"),
        ("concentration-units", "Multiply liters by milligrams per liter, then convert milligrams to grams.", "procedural", "source-change"),
        ("index-baseline", "A zero baseline makes the requested index undefined; do not divide by zero or reuse an old baseline.", "procedural", "source-change"),
        ("row-permissions", "Only aggregate rows readable by the current audience/project scope.", "procedural", "scope-switch"),
        ("outer-join", "Keep unmatched fact rows in the explicitly requested unmapped group.", "procedural", "tool-recovery"),
        ("full-window", "A rolling average is defined only after a full window of the declared width is available.", "procedural", "source-change"),
        ("numeric-identifiers", "Sort identifiers by their numeric values while preserving their string representation.", "procedural", "source-change"),
        ("subtotal-level", "Aggregate leaf rows once; do not add their parent subtotal again.", "procedural", "tool-recovery"),
        ("dated-price-join", "Join each transaction to the price effective on its transaction date.", "procedural", "source-change"),
        ("exchange-direction", "Invert a foreign-per-home rate when converting foreign amounts into home units.", "procedural", "source-change"),
        ("successive-discounts", "Apply percentage discounts successively rather than adding their percentages.", "procedural", "source-change"),
        ("competition-rank", "Equal scores share a rank and consume positions under competition ranking.", "procedural", "tool-recovery"),
        ("rounding-stage", "Follow the current policy's line-level or invoice-level rounding stage.", "procedural", "scope-switch"),
    )),
)


def _research(name, v, p):
    n = 10 * v + p
    a, b = f"study-{v}-{p}-a", f"study-{v}-{p}-b"
    if name == "evidence-window":
        d = {"as_of_day": 12 + p, "sources": [{"id": a, "from_day": 1, "until_day": 10, "value": 40},
             {"id": b, "from_day": 10, "until_day": 30, "value": 50 + n}]}
        return d, {"value": 50 + n, "source_id": b}, "Select the source whose half-open [from_day,until_day) interval contains as_of_day. Return value (integer) and source_id (string)."
    if name == "measurement-conflict":
        d = {"tolerance": 3, "reports": [{"id": a, "value": 20 + n}, {"id": b, "value": 22 + n + 3 * (p % 2)}]}
        return d, {"state": "agree" if p % 2 == 0 else "conflict"}, "Compare the absolute measurement difference to tolerance (inclusive). Return state: agree or conflict."
    if name == "causal-language":
        randomized = p % 2 == 0
        d = {"id": a, "randomized": randomized, "association_observed": True, "measured_population": "adult volunteers", "sample_size": 40 + n}
        return d, {"claim": "causal" if randomized else "associative"}, "For this fictional study, randomized allocation permits the stated causal contrast; otherwise only association is supported. Return claim: causal or associative."
    if name == "event-denominator":
        d = {"groups": [{"events": 2 + n, "sample": 100}, {"events": 8 - p, "sample": 900}]}
        return d, {"events": 10 + 10 * v, "sample": 1000, "percent": 1 + v}, "Pool event counts and samples. Return events, sample and percent as integers; the combined sample is 1000."
    if name == "archive-recovery":
        d = {"archive": {"id": a, "verified": True, "reading": 60 + n}, "stale_snippet": {"reading": 30}}
        return d, {"value": 60 + n, "source_id": a}, "After a failed read, use the verified frozen archive rather than the stale snippet. Return value (integer) and source_id (string)."
    if name == "study-weighting":
        d = {"studies": [{"mean": 10 + n, "sample": 10}, {"mean": 30 + n, "sample": 30}]}
        return d, {"weighted_mean": 25 + n}, "Compute the sample-weighted study mean. Return weighted_mean as an integer."
    if name == "interval-direction":
        lower, upper = ((-2, 5), (1, 6), (-6, -1), (-1, 2))[p]
        lower, upper = lower * v, upper * v
        d = {"id": a, "estimate": (lower + upper) / 2, "lower": lower, "upper": upper}
        return d, {"direction": ("unresolved", "positive", "negative", "unresolved")[p]}, "Return direction: positive if the whole interval is above zero, negative if below zero, otherwise unresolved."
    if name == "retraction-chain":
        withdrawn = a if p % 2 == 0 else b
        d = {"studies": [{"id": a}, {"id": b}], "notices": [{"withdraws": withdrawn}]}
        return d, {"included_ids": [b if withdrawn == a else a]}, "Exclude study IDs named by withdrawal notices. Return included_ids as a sorted string list."
    if name == "observation-recency":
        d = {"sources": [{"id": a, "publication_day": 30, "observed_day": 5, "reading": 90},
                        {"id": b, "publication_day": 20, "observed_day": 15 + p, "reading": 30 + n}]}
        return d, {"value": 30 + n, "source_id": b}, "Select the latest observation, irrespective of publication date. Return value (integer) and source_id (string)."
    if name == "population-boundary":
        requested = "adults" if p % 2 == 0 else "children"
        d = {"requested_population": requested, "studied_populations": ["adults"], "id": a,
             "sampled_age_range": [18 + v, 65 + p]}
        return d, {"applicability": "direct" if requested == "adults" else "extrapolation"}, "Return applicability: direct when the requested population was studied, otherwise extrapolation."
    if name == "registered-endpoint":
        endpoint = ("attendance", "completion", "retention", "participation")[p]
        d = {"registration": {"endpoint": endpoint, "minimum_sample": 40 + n}, "later_article": {"headline_endpoint": "satisfaction"}}
        return d, {"endpoint": endpoint}, "Read the registered endpoint rather than the later headline. Return endpoint as a string."
    if name == "compatible-units":
        d = {"observations": [{"amount": 2 + p, "unit": "km"}, {"amount": 400 + v, "unit": "m"}]}
        return d, {"total_meters": (2 + p) * 1000 + 400 + v}, "Combine observations in meters; 1 km is 1000 m. Return total_meters as an integer."
    if name == "syndication-lineage":
        d = {"reports": [{"id": "wire-copy", "origin": a}, {"id": "news-copy", "origin": a if p % 2 == 0 else "third-study"}, {"id": "independent", "origin": b}]}
        return d, {"independent_studies": 2 if p % 2 == 0 else 3}, "Count distinct originating study IDs rather than report copies. Return independent_studies as an integer."
    if name == "attrition-warning":
        lost = 2 + n + (5 if p % 2 == 0 else 30)
        d = {"threshold_percentage_points": 10, "groups": [{"assigned": 100, "lost": 2 + n}, {"assigned": 100, "lost": lost}]}
        return d, {"imbalanced": p % 2 == 1}, "Return imbalanced (boolean) when group attrition percentages differ by more than the declared threshold."
    if name == "absolute-risk":
        risk = 6 * v + p
        d = {"control_events": 20 + 2 * risk, "control_total": 100, "treated_events": 10 + risk, "treated_total": 100}
        return d, {"percentage_points": 10 + risk, "relative_percent": 50}, "Return absolute percentage_points and relative_percent reduction as integers. Use control risk as the relative denominator."
    if name == "correlation-interpretation":
        coefficient = (-.4, .6, 0., -.2)[p]
        d = {"coefficient": coefficient, "design": "observational", "sample_size": 60 + n}
        return d, {"association": ("negative", "positive", "none", "negative")[p], "causal": False}, "Return association: negative, positive or none from coefficient sign, and causal=false for this observational design."
    if name == "multiple-testing":
        d = {"family_alpha": .05 + .001 * p, "test_count": 5 + v, "tests": [{"id": a, "p_value": .005}, {"id": b, "p_value": .02 if p % 2 == 0 else .005}]}
        return d, {"significant_ids": [a] if p % 2 == 0 else [a, b]}, "Use Bonferroni threshold family_alpha/test_count (inclusive). Return significant_ids as a sorted string list."
    if name == "bias-sensitivity":
        d = {"studies": [{"id": a, "effect": 2 + n, "high_bias": False}, {"id": b, "effect": 50, "high_bias": True},
                         {"id": "clean-third", "effect": 4 + n, "high_bias": False}]}
        return d, {"clean_mean": 3 + n}, "Exclude high_bias studies and average remaining effects equally. Return clean_mean as an integer."
    if name == "method-match":
        d = {"requested_method": "counter" if p % 2 == 0 else "survey", "reports": [
             {"id": a, "method": "counter", "value": 10 + n}, {"id": b, "method": "survey", "value": 20 + n}]}
        return d, {"value": (10 if p % 2 == 0 else 20) + n, "source_id": a if p % 2 == 0 else b}, "Use the requested measurement method. Return value (integer) and source_id (string)."
    if name == "erratum-crosswalk":
        d = {"study": {"id": a, "capacity": 40, "cost": 20}, "erratum": {"study_id": a, "field": "capacity", "replacement": 50 + n}}
        return d, {"capacity": 50 + n, "cost": 20}, "Apply the linked erratum only to its named field. Return capacity and cost as integers."
    if name == "evidence-absence":
        supported = p % 2 == 1
        d = {"requested_claim": "shade increases yield", "sources": [{"id": a, "observation_count": 20 + n,
             "claims": ["shade increases yield"] if supported else ["shade changes temperature"]}]}
        return d, {"state": "supported" if supported else "unresolved", "source_ids": [a] if supported else []}, "Return state: supported or unresolved, and source_ids (sorted string list) of sources explicitly making the requested claim."
    if name == "speaker-attribution":
        d = {"host": "Fictional Panel Host", "publisher": "Synthetic Bulletin", "transcript": {"speaker": f"Speaker {n}", "statement": "We measured the greenhouse."}}
        return d, {"speaker": f"Speaker {n}"}, "Attribute the transcript statement to its speaker. Return speaker as a string, not the publisher or host."
    if name == "marginal-identification":
        d = {"population": 100, "uses_bus": 30 + n, "uses_bike": 20 + n, "joint_counts_available": False}
        return d, {"overlap": None, "state": "unidentified"}, "Marginal totals do not identify overlap. Return overlap=null and state=unidentified when joint counts are unavailable."
    if name == "funding-disclosure":
        d = {"study_id": a, "commissioner": f"Fictional Cooperative {n}", "researcher": "Synthetic Lab", "independent_funding": False}
        return d, {"commissioner": f"Fictional Cooperative {n}", "independently_funded": False}, "Return commissioner (string) and independently_funded (boolean) from the declared funding relationship. A named lab does not imply independent funding."
    if name == "paired-change":
        d = {"pairs": [{"person": "a", "before": 10 + n, "after": 14 + n}, {"person": "b", "before": 30, "after": 36 + 2 * p}]}
        return d, {"mean_change": 5 + p}, "Average each matched participant's after-minus-before change. Return mean_change as an integer."
    raise ValueError(name)


def _planning(name, v, p):
    n = 10 * v + p
    if name == "dependency-frontier":
        d = {"done": ["draft"] if p % 2 == 0 else ["draft", "review"], "tasks": [
             {"id": "review", "needs": ["draft"], "duration_minutes": 10 + n}, {"id": "publish", "needs": ["review"], "duration_minutes": 5 + n}]}
        return d, {"ready_ids": ["review"] if p % 2 == 0 else ["publish"]}, "Return ready_ids (sorted strings) for unfinished tasks whose prerequisites are all done."
    if name == "uninterrupted-slot":
        d = {"duration_minutes": 35 + 2 * v + p, "free_intervals": [{"id": "short", "start": 0, "end": 20 if p < 2 else 50}, {"id": "long", "start": 60 + n, "end": 110 + n}]}
        return d, {"slot_id": "long" if p < 2 else "short"}, "Select the earliest single free interval fitting duration_minutes. Return slot_id (string); separated intervals cannot be added together."
    if name == "minimum-budget":
        d = {"budget": 60 + n % 23, "minimums": {"room": 40, "materials": 20}, "optional_extra": 15}
        return d, {"minimum_total": 60, "extra_affordable": n % 23 >= 15}, "Sum minimum allocations first. Return minimum_total (integer) and extra_affordable (boolean) for adding the optional extra afterward."
    if name == "receipt-confirmation":
        confirmed = p % 2 == 1
        d = {"request": {"id": f"reservation-{n}", "accepted": True, "requested_slots": 3 + n},
             "receipt": {"request_id": f"reservation-{n}", "status": "confirmed" if confirmed else "queued", "allocated_slots": 3 + n if confirmed else 0}}
        return d, {"confirmed": confirmed}, "Return confirmed (boolean) only when the matching receipt status is confirmed and allocated_slots matches requested_slots; accepted or queued alone is insufficient."
    if name == "holiday-recurrence":
        d = {"scheduled_day": 10 + n, "closed_days": [10 + n, 11 + n], "allowed_days": list(range(10 + n, 16 + n))}
        return d, {"day": 12 + n}, "Move the scheduled occurrence to the first allowed day on or after it that is not closed. Return day as an integer."
    if name == "critical-path":
        d = {"tasks": [{"id": "a", "duration": 3 + n, "needs": []}, {"id": "b", "duration": 2, "needs": ["a"]},
                       {"id": "c", "duration": 5, "needs": ["a"]}, {"id": "d", "duration": 1, "needs": ["b", "c"]}]}
        return d, {"finish_minutes": 9 + n}, "Tasks run in parallel once all prerequisites finish. Return finish_minutes (integer) for the whole dependency graph."
    if name == "travel-gap":
        d = {"previous_end": 60, "travel_minutes": 15 + v + 5 * p, "candidates": [{"id": "tight", "start": 80}, {"id": "reachable", "start": 110}]}
        return d, {"appointment_id": "tight" if p == 0 else "reachable"}, "Select the earliest appointment starting no earlier than previous_end+travel_minutes. Return appointment_id as a string."
    if name == "capacity-packing":
        d = {"capacity": (10 + p) * v, "items_priority_order": [{"id": "first", "size": 6 * v}, {"id": "second", "size": 5 * v}, {"id": "third", "size": 3 * v}]}
        return d, {"item_ids": ["first", "third"] if p == 0 else ["first", "second"], "used_capacity": (9 if p == 0 else 11) * v}, "Greedily consider items in the supplied priority order; include an item only if it fits remaining capacity. Return item_ids in selection order and used_capacity (integer)."
    if name == "cancellation-boundary":
        inclusive = p % 2 == 0
        d = {"requested_minute": 60 + n, "cutoff_minute": 60 + n, "inclusive": inclusive, "policy_notice": "Fictional policy only"}
        return d, {"allowed": inclusive}, "Return allowed (boolean): request must be earlier than cutoff, or equal only when inclusive=true."
    if name == "lead-time":
        d = {"delivery_day": 25 + n, "preparation_days": 3 + p, "days_are_calendar_days": True}
        return d, {"start_day": 22 + 10 * v}, "Subtract preparation_days from delivery_day using these fictional calendar-day indices. Return start_day as an integer."
    if name == "consent-invitation":
        d = {"as_of_day": 10 + n, "people": [{"id": f"member-{n}", "member": True, "consent": True, "consent_until": 30 + n},
             {"id": "opted-out", "member": True, "consent": False, "consent_until": 30 + n},
             {"id": "expired", "member": True, "consent": True, "consent_until": 9 + n}]}
        return d, {"invitee_ids": [f"member-{n}"]}, "Draft only IDs of members who consented and whose consent_until includes as_of_day (inclusive). Return invitee_ids as a sorted string list; do not send anything."
    if name == "local-day":
        offset = 2 if p % 2 == 0 else -3
        d = {"utc_day_index": 10 + v, "utc_minute": 23 * 60 + 5 * p, "fixed_offset_hours": offset}
        return d, {"local_day_index": 11 + v if offset > 0 else 10 + v, "local_minute": (60 if offset > 0 else 20 * 60) + 5 * p}, "Apply the supplied fixed offset; 1440 minutes makes one day. Return local_day_index and local_minute as integers. No real timezone lookup is needed."
    if name == "resource-collision":
        d = {"requested_resource": "room-a", "bookings": [{"resource": "room-a", "start": 10 + n, "end": 30 + n}, {"resource": "room-b", "start": 30 + n, "end": 60 + n}],
             "candidates": [{"id": "overlap", "start": 20 + n, "end": 40 + n}, {"id": "adjacent", "start": 30 + n, "end": 50 + n}]}
        return d, {"slot_id": "adjacent", "start_minute": 30 + n}, "Intervals are half-open: sharing only an endpoint is allowed. Select the earliest candidate not overlapping a booking of requested_resource. Return slot_id (string) and start_minute (integer)."
    if name == "energy-rest":
        d = {"first_duration": 20 + n, "required_rest": 10, "second_duration": 30}
        return d, {"second_start": 30 + n, "finish": 60 + n}, "Start at minute zero and insert required_rest between the two demanding activities. Return second_start and finish as integers."
    if name == "release-gates":
        ready = p % 2 == 1
        gate = ("access", "privacy", "license", "availability")[p]
        d = {"required_gates": ["review", "test", gate], "passed": ["review", "test", gate] if ready else ["review", "test"], "minimum_reviewers": v}
        return d, {"ready": ready, "missing_gates": [] if ready else [gate]}, "Return ready (boolean) only if all required gates passed, and missing_gates as sorted strings. The passed review gate has already satisfied minimum_reviewers."
    if name == "batch-setup":
        d = {"items": 4 + v, "batch_capacity": 3, "setup_minutes": 5, "per_item_minutes": 2 + p}
        batches = ceil((4 + v) / 3)
        return d, {"batches": batches, "total_minutes": batches * 5 + (4 + v) * (2 + p)}, "Use full batches plus any partial batch. Charge setup once per batch and processing per item. Return batches and total_minutes as integers."
    if name == "closed-route":
        d = {"start": "A", "end": "C", "edges": [{"from": "A", "to": "C", "minutes": 2, "closed": True},
             {"from": "A", "to": "B", "minutes": 3 + n, "closed": False}, {"from": "B", "to": "C", "minutes": 4, "closed": False}]}
        return d, {"route": ["A", "B", "C"], "minutes": 7 + n}, "Find the shortest directed route excluding closed edges. Return route as node IDs in order and minutes as an integer."
    if name == "parallel-handoff":
        d = {"team_minutes": [10 + n, 15 + n], "handoff_minutes": 5}
        return d, {"finish_minutes": 20 + n}, "Teams start together; common handoff starts only after every team finishes. Return finish_minutes as an integer."
    if name == "fair-rotation":
        d = {"members": [{"id": "a", "assignments": 0, "available": False}, {"id": "b", "assignments": 2 * v, "available": True}, {"id": "c", "assignments": v + p, "available": True}]}
        return d, {"member_id": "c" if p < v else "b"}, "Among available members choose fewest assignments, breaking ties by lexicographic ID. Return member_id."
    if name == "retry-escalation":
        d = {"failed_attempts": v + p, "maximum_attempts": v + 2, "next_operation_status": "not attempted"}
        return d, {"action": "escalate" if p >= 2 else "retry"}, "At maximum_attempts failed attempts or beyond return action=escalate; otherwise action=retry. No new live attempt is performed."
    if name == "priority-aging":
        d = {"aging_per_hour": 2, "queue": [{"id": "new", "base": 8, "waiting_hours": 0}, {"id": "old", "base": 3 + v, "waiting_hours": 4 + p}]}
        return d, {"item_id": "old", "score": 11 + v + 2 * p}, "Score each item as base+waiting_hours*aging_per_hour. Choose the maximum, breaking ties by ID. Return item_id and score (integer)."
    if name == "contingency-trigger":
        chance = (20, 45, 70, 30)[p] + v
        d = {"trigger_percent": 45 + v, "forecast_percent": chance, "backup_prepared": True}
        return d, {"activate": chance >= 45 + v}, "Return activate (boolean) only when forecast reaches the inclusive trigger and backup is prepared."
    if name == "single-vendor-kit":
        d = {"needed": ["lamp", "stand"], "suppliers": [{"id": "cheap-partial", "available": ["lamp"] if p < 2 else ["lamp", "stand"], "kit_price": 10},
             {"id": "complete", "available": ["lamp", "stand"], "kit_price": 30 + n}]}
        return d, {"supplier_id": "complete" if p < 2 else "cheap-partial", "price": 30 + n if p < 2 else 10}, "Mixing suppliers is forbidden. Choose the cheapest supplier with every needed item; return supplier_id and price (integer)."
    if name == "delegate-chain":
        d = {"owner": "member-0", "people": [{"id": f"member-{i}", "available": i >= p + 1,
             "delegate": f"member-{i + 1}" if i < 3 + v else None} for i in range(4 + v)]}
        return d, {"delegate_id": f"member-{p + 1}"}, "Follow the owner-to-delegate chain to its first available person. Return delegate_id (string), or null if no authorized available person exists."
    if name == "workday-capacity":
        capacity = 240 + 10 * n if p % 2 == 0 else 600 + 10 * n
        d = {"working_day_minutes": capacity, "tasks_hours": [2 + v, 3], "minutes_per_hour": 60}
        return d, {"load_minutes": 300 + 60 * v, "fits": capacity >= 300 + 60 * v}, "Normalize task hours to minutes using the supplied conversion. Return load_minutes (integer) and fits (boolean) within current working_day_minutes."
    raise ValueError(name)


def _data(name, v, p):
    n = 10 * v + p
    if name == "join-cardinality":
        d = {"joined_rows": [{"order_id": "a", "order_total": 20 + n, "line_id": "one"}, {"order_id": "a", "order_total": 20 + n, "line_id": "two"}, {"order_id": "b", "order_total": 30, "line_id": "three"}]}
        return d, {"order_count": 2, "order_total": 50 + n}, "Each order_total belongs to the order, not its line. Return distinct order_count and order_total as integers."
    if name == "null-zero":
        d = {"measurements": [None, 0, 6 + 2 * n, 6 + 2 * n]}
        return d, {"count": 3, "mean_numerator": 12 + 4 * n, "mean_denominator": 3}, "Exclude null values but include zeros. Return count, mean_numerator (sum) and mean_denominator (valid count) as integers, expressing the unrounded mean as a fraction."
    if name == "locale-decimal":
        decimal_mark = "," if p % 2 == 0 else "."
        d = {"decimal_separator": decimal_mark, "thousands_separator": "." if decimal_mark == "," else ",",
             "amount": f"1{'.' if decimal_mark == ',' else ','}234{decimal_mark}{50 + 5 * v + p:02d}"}
        return d, {"minor_units": 123450 + 5 * v + p}, "Parse amount using the supplied separators and exactly two decimal digits. Return minor_units as an integer."
    if name == "credit-sign":
        d = {"entries": [{"kind": "debit", "amount": 100 + n}, {"kind": "credit", "amount": 30}, {"kind": "debit", "amount": 10}]}
        return d, {"net": 80 + n}, "Add debits and subtract credits. Return net as an integer."
    if name == "page-retry":
        d = {"attempts": [{"page": 1, "status": "completed", "rows": [1 + n, 2]}, {"page": 2, "status": "failed", "rows": []},
                          {"page": 2, "status": "completed", "rows": [3]}], "required_pages": [1, 2]}
        return d, {"total": 6 + n, "complete": True}, "Use one successful attempt per required page, never both failed and retry rows. Return total (integer) and complete (boolean)."
    if name == "weighted-average":
        d = {"lines": [{"price": 10 + n, "quantity": 1}, {"price": 30 + n, "quantity": 3}]}
        return d, {"average": 25 + n}, "Weight prices by quantities. Return average as an integer; these inputs produce a whole-number average."
    if name == "nearest-rank":
        d = {"values": [8 + n, 2 + n, 6 + n, 4 + n], "percentile": 75}
        return d, {"percentile_value": 6 + n}, "Sort values, use one-based ceil(percentile/100*n) rank. Return percentile_value as an integer."
    if name == "even-median":
        d = {"values": [8 + n, 2 + n, 6 + n, 4 + n]}
        return d, {"median": 5 + n}, "Return median as an integer, averaging the two central sorted observations for this even sample; these inputs give a whole number."
    if name == "sample-variance":
        d = {"values": [1 + n, 1 + n + 2 * (p + 1), 1 + n + 4 * (p + 1)], "variance_kind": "sample"}
        return d, {"variance": 4 * (p + 1) ** 2}, "Return variance as an integer for these whole-number cases: sample variance is squared deviations from the mean divided by n-1."
    if name == "counter-reset":
        d = {"counter": [5 + n, 8 + n, 2, 6], "initial_count_included": True}
        return d, {"increments": 14 + n}, "Count the initial reading, positive differences, and the new reading after each downward reset. Return increments as an integer."
    if name == "overlap-dedup":
        d = {"extracts": [[{"id": "a", "value": 2 + n}, {"id": "b", "value": 3}], [{"id": "b", "value": 3}, {"id": "c", "value": 4}]]}
        return d, {"total": 9 + n, "event_count": 3}, "Union extracts by event ID; repeated IDs have the same value. Return total and event_count as integers."
    if name == "fiscal-quarter":
        start = v + 1 if p == 3 else v
        d = {"fiscal_start_month": start, "month": 6 + p}
        return d, {"quarter": ((6 + p - start) % 12) // 3 + 1}, "Quarter is floor(((month-fiscal_start_month) mod 12)/3)+1. Return quarter as an integer."
    if name == "offset-bucket":
        offset = 2 if p % 2 == 0 else -2
        d = {"fixed_offset_minutes": offset * 60, "events": [{"utc_day": 10 + n, "utc_minute": 23 * 60}, {"utc_day": 11 + n, "utc_minute": 60}]}
        return d, {"day_counts": {str(11 + n): 2} if offset > 0 else {str(10 + n): 2}}, "Apply the supplied fixed offset (1440 minutes/day), then count by local day. Return day_counts as an object mapping string day indices to integer counts."
    if name == "concentration-units":
        d = {"liters": 2 + p, "milligrams_per_liter": 500 + 100 * v, "milligrams_per_tenth_gram": 100}
        return d, {"grams_tenths": (2 + p) * (5 + v)}, "Multiply volume by concentration and convert mg to tenths of a gram. Return grams_tenths as an integer."
    if name == "index-baseline":
        baseline = 0 if p % 2 == 0 else 20
        d = {"baseline": baseline, "current": 40 + 2 * n}
        return d, {"index": None if baseline == 0 else 200 + 10 * n, "state": "undefined" if baseline == 0 else "defined"}, "Index is 100*current/baseline. Return state: defined or undefined and index (integer for these inputs, or null for zero baseline)."
    if name == "row-permissions":
        audience = "a" if p % 2 == 0 else "b"
        d = {"current_audience": audience, "rows": [{"readers": ["a"], "amount": 10 + n}, {"readers": ["b"], "amount": 20 + n}, {"readers": ["a", "b"], "amount": 5}]}
        return d, {"total": (15 if audience == "a" else 25) + n}, "Aggregate only rows whose readers include current_audience. Return total as an integer."
    if name == "outer-join":
        d = {"facts": [{"dimension_id": "known", "amount": 10 + n}, {"dimension_id": "missing", "amount": 5}], "dimensions": {"known": "group-a"}}
        return d, {"groups": {"group-a": 10 + n, "unmapped": 5}}, "Left-join all facts; use group 'unmapped' for absent dimensions. Return groups mapping group strings to integer totals."
    if name == "full-window":
        d = {"values": [1 + n, 3 + n, 5 + n, 7 + n], "window": 3}
        return d, {"averages": [None, None, 3 + n, 5 + n]}, "Return averages in original order, using null until a full trailing window exists, then arithmetic mean."
    if name == "numeric-identifiers":
        d = {"ids": [str(10 + n), str(2 + n), str(100 + n)]}
        return d, {"ordered_ids": [str(2 + n), str(10 + n), str(100 + n)]}, "Sort IDs by integer value, preserving their original strings. Return ordered_ids as a string list."
    if name == "subtotal-level":
        d = {"rows": [{"level": "leaf", "amount": 10 + n}, {"level": "leaf", "amount": 20}, {"level": "subtotal", "amount": 30 + n}]}
        return d, {"total": 30 + n}, "Sum leaf rows only; a subtotal already includes its children. Return total as an integer."
    if name == "dated-price-join":
        d = {"transactions": [{"day": 4, "quantity": 2}, {"day": 12, "quantity": 1}],
             "prices": [{"from_day": 0, "until_day": 10, "price": 10 + n}, {"from_day": 10, "until_day": 30, "price": 20 + n}]}
        return d, {"revenue": 40 + 3 * n}, "Use each transaction day's half-open effective price interval and multiply by quantity. Return revenue as an integer."
    if name == "exchange-direction":
        d = {"foreign_amount": 60 + 6 * n, "foreign_per_home": 3}
        return d, {"home_amount": 20 + 2 * n}, "The quote is foreign units per one home unit. Divide foreign_amount by foreign_per_home; return home_amount as an integer for these exactly divisible inputs."
    if name == "successive-discounts":
        d = {"starting_cents": 10000 + 1000 * n, "discount_percentages": [20, 10]}
        return d, {"final_cents": 7200 + 720 * n}, "Apply each discount to the remaining amount successively. Return final_cents as an integer; these inputs need no rounding."
    if name == "competition-rank":
        d = {"scores": [{"id": "a", "score": 9 + n}, {"id": "b", "score": 9 + n if p % 2 == 0 else 8 + n}, {"id": "c", "score": 5}]}
        return d, {"ranks": {"a": 1, "b": 1 if p % 2 == 0 else 2, "c": 3}}, "Higher scores rank first. Equal scores share rank and consume positions (competition ranking). Return ranks mapping IDs to integer ranks."
    if name == "rounding-stage":
        line = p % 2 == 0
        d = {"amounts": [f"{n}.005", f"{n}.005"], "decimal_places": 2, "rounding": "half-up", "stage": "line" if line else "invoice"}
        return d, {"minor_units": 200 * n + (2 if line else 1)}, "Round half-up to two decimal places at the specified stage: each line before summing, or summed invoice once. Return minor_units as an integer."
    raise ValueError(name)


def _writing(name, v, p):
    """Private facts and phrase rubric are separate from public source records."""
    n = 10 * v + p
    person, date = f"Person {n}", f"{2026 + v}-02-{1 + (7 * v + 3 * p) % 28:02d}"
    if name == "incident-brief":
        d = {"incident_id": f"INC-{n}", "state": "monitoring", "affected_services": 2 + n, "permanent_fix_verified": False}
        facts = {"incident": f"INC-{n}", "state": "monitoring", "affected_services": 2 + n}
        phrases, forbidden = [[f"INC-{n}"], ["monitoring"]], ["permanently fixed"]
        rule = "Write a monitoring update; mention the incident and service count. Do not claim a permanent fix."
    elif name == "public-excerpt":
        d = {"audience": "public", "product": f"Lamp {n}", "release_date": date, "internal_owner": f"Private Owner {n}", "internal_budget": f"EUR {900 + n}"}
        facts = {"audience": "public", "release_date": date}
        phrases, forbidden = [[f"Lamp {n}"], [date]], [d["internal_owner"], d["internal_budget"]]
        rule = "Write a public release brief using product/date only. Omit the internal owner and budget."
    elif name == "tentative-announcement":
        approved = p % 2 == 1
        d = {"project": f"Garden {n}", "approval": approved, "target_date": date}
        state = "confirmed" if approved else "proposed"
        facts = {"status": state, "target_date": date}
        phrases, forbidden = [[state], [date]], ["guaranteed"] + (["confirmed"] if not approved else [])
        rule = "Use status confirmed only if approval=true, otherwise proposed. State the target date without a guarantee."
    elif name == "minutes-open-question":
        d = {"action": "check lighting", "owner": person, "question": "Is evening access available?", "question_resolved": False}
        facts = {"owner": person, "action": "check lighting", "question_state": "open"}
        phrases, forbidden = [[person], ["check lighting"], ["open question"]], ["question resolved", "access approved"]
        rule = "Write minutes naming the action/owner and labeling the unresolved access question as an open question."
    elif name == "plain-language":
        d = {"technical_copy": "The device sustains battery utilization for the tested interval.", "tested_hours": 8 + n,
             "glossary": {"battery utilization": "battery lasts", "tested interval": "hours"}}
        facts = {"tested_hours": 8 + n}
        phrases, forbidden = [["battery lasts"], [f"{8 + n} hours"]], ["utilization", "unlimited"]
        rule = "Rewrite in plain language using the supplied glossary and tested duration; do not promise unlimited use."
    elif name == "correction-notice":
        d = {"original_count": 40 + n, "corrected_count": 50 + n, "unit": "seats"}
        facts = {"old_count": 40 + n, "new_count": 50 + n, "unit": "seats"}
        phrases, forbidden = [["correction"], [str(40 + n)], [str(50 + n)], ["seats"]], ["unchanged"]
        rule = "Write a labeled correction that gives the old and corrected seat counts."
    elif name == "disputed-brief":
        d = {"report_a": {"count": 20 + n}, "report_b": {"count": 30 + n}, "reconciliation_available": False}
        facts = {"reported_counts": [20 + n, 30 + n], "resolved": False}
        phrases, forbidden = [["reports disagree"], [str(20 + n)], [str(30 + n)]], ["verified total", "dispute resolved"]
        rule = "Summarize both counts and say the reports disagree. Do not select a verified total."
    elif name == "quoted-speaker":
        quote = "The room needs more light."
        d = {"speaker": person, "publisher": "Synthetic Notebook", "quote": quote}
        facts = {"speaker": person, "quote": quote}
        phrases, forbidden = [[person], [quote]], ["publisher said"]
        rule = "Quote the supplied sentence exactly and attribute it to the speaker, not the publisher."
    elif name == "observable-alt-text":
        obj = ("cup", "bowl", "jar", "mug", "plate")[v - 1]
        surface = ("wooden desk", "stone shelf", "metal table", "painted bench")[p]
        visible = f"{('red', 'blue', 'green', 'yellow')[p]} {obj}"
        d = {"visible_objects": [visible, surface], "visible_action": f"{obj} rests on {surface}", "people_visible": 0}
        facts = {"objects": [visible, surface], "people": 0}
        phrases, forbidden = [[visible], [surface]], ["happy", "sad", "owner"]
        rule = "Write alt text describing only the supplied visible objects. Infer no emotion or ownership."
    elif name == "invitation-details":
        d = {"start": "14:30", "zone": "fictional UTC+02 fixed offset", "agenda": "garden layout", "date": date, "attendance_confirmed": False}
        facts = {"start": "14:30", "zone": d["zone"], "date": date}
        phrases, forbidden = [["14:30"], ["UTC+02"], ["garden layout"], [date]], ["attendance confirmed"]
        rule = "Draft an invitation with date, time, supplied fixed-offset zone and agenda; do not claim attendance confirmation."
    elif name == "bounded-product-claim":
        d = {"tested_scenario": "indoor desk", "measured_hours": 6 + n, "market_comparison_performed": False}
        facts = {"scenario": "indoor desk", "measured_hours": 6 + n}
        phrases, forbidden = [["measured"], ["indoor desk"], [f"{6 + n} hours"]], ["best", "guaranteed"]
        rule = "Write only the measured duration for the tested indoor desk scenario; omit market rankings and guarantees."
    elif name == "refund-review":
        review = "approved" if p % 2 == 1 else "pending"
        d = {"review_status": review, "refund_issued": False, "case_id": f"case-{n}", "requested_cents": 500 + 10 * n}
        facts = {"review_status": review, "refund_issued": False, "requested_cents": 500 + 10 * n}
        phrases, forbidden = [[review], [f"case-{n}"], ["not issued"], [str(500 + 10 * n)]], ["refund issued", "refund completed"]
        rule = "Write a case update naming the review state and stating that the refund is not issued. Approval is not execution."
    elif name == "decision-risk-brief":
        decision = ("pilot only", "pause rollout", "limit access", "review first")[p]
        risk = (f"limited sample of {5 * v} users", f"pending audit of {v} sites",
                f"missing consent from {v} groups", f"uncertain timing over {v} days")[p]
        d = {"decision": decision, "risk": risk, "risk_resolved": False}
        facts = {"decision": decision, "risk": risk, "risk_resolved": False}
        phrases, forbidden = [[decision], [risk]], ["risk resolved", "full rollout"]
        rule = "Briefly report the recorded decision and unresolved risk; do not announce a full rollout."
    elif name == "anonymized-story":
        d = {"segment": "small workshop", "experience": "shorter setup", "name": person, "email": f"person{n}@example.invalid"}
        facts = {"segment": "small workshop", "experience": "shorter setup"}
        phrases, forbidden = [["small workshop"], ["shorter setup"]], [person, d["email"]]
        rule = "Write an anonymized story retaining the segment and reported experience, omitting name and email."
    elif name == "work-status":
        delivered = p % 2 == 1
        d = {"started": True, "delivered": delivered, "project": f"Workshop {n}"}
        state = "completed" if delivered else "in progress"
        facts = {"status": state}
        phrases, forbidden = [[f"Workshop {n}"], [state]], ["delivered"] if not delivered else ["not started"]
        rule = "Use status completed only if delivered=true, otherwise in progress. Name the project."
    elif name == "release-limitation":
        d = {"revision": 100 * v + p, "change": "offline export", "limitation": "images excluded"}
        facts = {"revision": 100 * v + p, "change": "offline export", "limitation": "images excluded"}
        phrases, forbidden = [["offline export"], ["images excluded"]], ["all media"]
        rule = "Write a release note with the new export behavior and its stated image limitation."
    elif name == "dated-comparison":
        d = {"earlier_year": 2024, "earlier_count": 20 + n, "later_year": 2025, "later_count": 30 + n, "current_measurement_available": False}
        facts = {"earlier": 20 + n, "later": 30 + n, "change": 10}
        phrases, forbidden = [["2024"], ["2025"], [str(20 + n)], [str(30 + n)]], ["currently", "will continue"]
        rule = "Describe the historical comparison with both years and counts; make no current or future claim."
    elif name == "conditional-guide":
        d = {"gateway_online": p % 2 == 1, "procedure": {"online": "submit once", "offline": f"wait for connection for {5 + n} minutes"}}
        action = d["procedure"]["online"] if d["gateway_online"] else d["procedure"]["offline"]
        facts = {"gateway_online": d["gateway_online"], "action": action}
        phrases, forbidden = [["if"], ["online"], ["submit once"], ["offline"], ["wait for connection"]], ["retry forever"]
        rule = "Rewrite both conditional branches: if online submit once; if offline wait for connection. State the current branch in facts."
    elif name == "alternative-decline":
        d = {"requested_action": "send message", "available_action": f"draft message for review within {n} minutes", "send_permission": False}
        facts = {"permitted_action": d["available_action"], "sent": False}
        phrases, forbidden = [["cannot send"], ["draft message"]], ["message sent"]
        rule = "Say cannot send and offer to draft message. Do not claim any message was sent."
    elif name == "uncertain-range":
        d = {"lower_hours": 3 + n, "upper_hours": 6 + n, "kind": "estimate"}
        facts = {"lower_hours": 3 + n, "upper_hours": 6 + n, "certain": False}
        phrases, forbidden = [["estimate"], ["range"], [str(3 + n)], [str(6 + n)]], ["exactly", "guaranteed"]
        rule = "Write an estimated range using both bounds, preserving uncertainty."
    elif name == "rounded-measurement":
        d = {"measurement": f"{12 + n}.65", "unit": "meters", "decimal_places": 1, "rounding": "half-up"}
        rounded = f"{12 + n}.7"
        facts = {"rounded": rounded, "unit": "meters"}
        phrases, forbidden = [[rounded], ["meters"]], ["exactly"]
        rule = "Write the measurement rounded half-up to one decimal place with its unit. Rounded is a string in facts."
    elif name == "opt-in-draft":
        d = {"allowed_group": "subscribers", "excluded_person": person, "excluded_email": f"exclude{n}@example.invalid", "topic": "garden notes"}
        facts = {"audience": "subscribers", "topic": "garden notes"}
        phrases, forbidden = [["subscribers"], ["garden notes"]], [person, d["excluded_email"]]
        rule = "Draft for the opted-in subscriber group about garden notes; omit the excluded person's identifiers."
    elif name == "transit-notice":
        d = {"shipment": f"parcel-{n}", "observed_status": "in transit", "estimated_arrival": date, "delivery_receipt": None}
        facts = {"status": "in transit", "estimated_arrival": date, "delivered": False}
        phrases, forbidden = [[f"parcel-{n}"], ["in transit"], ["estimated"], [date]], ["delivered"]
        rule = "Write a transit notice with estimated arrival; without a delivery receipt do not claim delivered."
    elif name == "attributed-review":
        d = {"reviewer": person, "opinion": "comfortable", "test_source": "Synthetic Counter Study", "measured_minutes": 20 + n}
        facts = {"reviewer": person, "opinion": "comfortable", "measured_minutes": 20 + n}
        phrases, forbidden = [[person], ["comfortable"], ["Synthetic Counter Study"], [str(20 + n)]], ["comfort proven"]
        rule = "Attribute comfort to the reviewer and minutes to the named test source; do not say comfort was proven."
    elif name == "glossary-translation":
        d = {"source_terms": ["gate", "garden"], "target_language": "supplied Spanish glossary",
             "glossary": {"gate": "puerta", "garden": "jardín"}, "quantity": 1 + n}
        facts = {"gate_term": "puerta", "garden_term": "jardín", "quantity": 1 + n}
        phrases, forbidden = [["puerta"], ["jardín"], [str(1 + n)]], ["portal"]
        rule = "Use exactly the supplied glossary terms in a short target-language label, with the quantity. No external translation source is needed."
    else:
        raise ValueError(name)
    max_words = 45
    rubric = {"kind": "writing", "text_field": "text", "max_words": max_words,
              "required_phrases": phrases, "forbidden_phrases": forbidden}
    contract = ", ".join(f"{key}:{_type(value)}" for key, value in facts.items())
    instructions = (f"{rule} Return one structured answer with text (your draft, at most {max_words} words) and facts "
        f"(exact keys/types: {contract}). These phrases must appear in text: "
        + "; ".join(" or ".join(group) for group in phrases)
        + ". Omit these phrases/identifiers from text: " + "; ".join(forbidden) + ".")
    return d, {"facts": facts}, instructions, rubric


def _type(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "string"


def _sequence(family, variant):
    seq_id = f"{family.split}.{family.category}.{family.name}.{variant:02d}"
    family_id = f"role:{family.split}:{family.category}:{family.name}"
    topic = f"{family.category}:{family.name}"
    scope = Scope(f"synthetic:{family.split}:user-{variant}", f"synthetic:{family.category}:{family.name}:project-a")
    tasks, keys = [], {}
    for phase, suffix in enumerate(("learn-1", "learn-2", "probe-1", "probe-2")):
        if family.category == "writing":
            data, expected, instruction, grading = _writing(family.name, variant, phase)
        else:
            factory = {"research": _research, "planning": _planning, "data": _data}[family.category]
            data, expected, instruction = factory(family.name, variant, phase)
            grading = None
        task_scope = Scope(scope.audience_key, scope.project_key.replace("project-a", "project-b")) if phase == 3 and family.stress == "scope-switch" else scope
        args = {"record": f"{family.name}-{variant}", "snapshot": phase + 1}
        bundle = {"notice": "Explicitly synthetic fictional fixture; not a real source, person, policy, or live account.",
                  "source_id": f"synthetic:{seq_id}:{suffix}", "snapshot": phase + 1,
                  "scope": task_scope.to_dict(), "data": deepcopy(data)}
        tools = [ToolFixture(f"synthetic.{family.category}.{family.name}.read", args, bundle)]
        if family.stress == "tool-recovery":
            tools.insert(0, ToolFixture(f"synthetic.{family.category}.{family.name}.attempt", args,
                {"status": "failed", "error": "Fictional source temporarily unavailable", "retryable": True}))
            instruction = "Observe the first advertised failed attempt and use the supplied frozen fallback read. " + instruction
        task = Task(f"{seq_id}.{suffix}", instruction + " All source material and policies are fictional and fixed.",
                    task_scope, tuple(tools), topic, "learning" if phase < 2 else "future")
        tags = (family.stratum,) + (("scope_leakage",) if phase == 3 and family.stress == "scope-switch" else
                                  ("tool_recovery",) if family.stress == "tool-recovery" else ("stale_advice",))
        keys[task.task_id] = ScoringKey(deepcopy(expected), tags if phase >= 2 else (), topic, grading=deepcopy(grading))
        tasks.append(task)
    feedback = Feedback("For the next fresh tasks, remember this procedure: " + family.lesson,
                        scope, topic, f"procedure:{family.name}")
    return Sequence(seq_id, family_id, family_id, family.category, family.split,
                    (tasks[0], tasks[1], feedback, tasks[2], tasks[3]), keys)


def noncoding_sequences(split):
    """40 diagnostic or 400 held-out sequences, with disjoint family IDs."""
    if split not in ("diagnostic", "heldout"):
        raise ValueError("Select diagnostic or heldout")
    variants = range(1, 3) if split == "diagnostic" else range(1, 6)
    return tuple(_sequence(family, variant) for family in FAMILIES if family.split == split for variant in variants)


def noncoding_metadata(split):
    families = [family for family in FAMILIES if family.split == split]
    sequences = noncoding_sequences(split)
    return {"split": split, "synthetic": True, "sequence_count": len(sequences),
            "family_count": len(families), "scored_tasks": len(sequences) * 4,
            "future_probes": len(sequences) * 2,
            "independence_note": "Variants and task states share authored family mechanisms; no empirical independence claim.",
            "writing_note": "Structured facts and a bounded phrase/word rubric; no semantic model judge or prose-quality claim."}


def noncoding_response(task):
    """Independent offline answer from actual advertised public observations.

    No private key, Sequence, family constructor, grading rubric or feedback is
    consulted. Reading each fixture also proves its advertised arguments work.
    This is a mechanical reachability oracle, not an efficacy baseline.
    """
    world = FakeWorld(task)
    observations = [(tool.name, world.call(tool.name, tool.arguments)) for tool in task.tools]
    reads = [(name, result["data"]) for name, result in observations if "data" in result]
    if len(reads) != 1:
        raise ValueError("Exactly one frozen source bundle is required")
    tool_name, data = reads[0]
    _, category, name, operation = tool_name.split(".")
    if operation != "read":
        raise ValueError("Unsupported source operation")
    if category == "writing":
        return _write_from_source(name, data)
    if category == "research":
        return _research_from_source(name, data)
    if category == "planning":
        return _plan_from_source(name, data)
    if category == "data":
        return _compute_from_source(name, data)
    raise ValueError("Unsupported non-coding category")


def _research_from_source(name, d):
    if name == "evidence-window":
        row = next(r for r in d["sources"] if r["from_day"] <= d["as_of_day"] < r["until_day"])
        return {"value": row["value"], "source_id": row["id"]}
    if name == "measurement-conflict":
        difference = abs(d["reports"][0]["value"] - d["reports"][1]["value"])
        return {"state": "agree" if difference <= d["tolerance"] else "conflict"}
    if name == "causal-language":
        return {"claim": "causal" if d["randomized"] else "associative"}
    if name == "event-denominator":
        events, sample = sum(r["events"] for r in d["groups"]), sum(r["sample"] for r in d["groups"])
        return {"events": events, "sample": sample, "percent": events * 100 // sample}
    if name == "archive-recovery":
        if d["archive"]["verified"] is not True:
            raise ValueError("Unverified archive cannot establish the requested fact")
        return {"value": d["archive"]["reading"], "source_id": d["archive"]["id"]}
    if name == "study-weighting":
        weighted = sum(r["mean"] * r["sample"] for r in d["studies"])
        return {"weighted_mean": weighted // sum(r["sample"] for r in d["studies"])}
    if name == "interval-direction":
        return {"direction": "positive" if d["lower"] > 0 else "negative" if d["upper"] < 0 else "unresolved"}
    if name == "retraction-chain":
        withdrawn = {r["withdraws"] for r in d["notices"]}
        return {"included_ids": sorted(r["id"] for r in d["studies"] if r["id"] not in withdrawn)}
    if name == "observation-recency":
        row = max(d["sources"], key=lambda r: r["observed_day"])
        return {"value": row["reading"], "source_id": row["id"]}
    if name == "population-boundary":
        return {"applicability": "direct" if d["requested_population"] in d["studied_populations"] else "extrapolation"}
    if name == "registered-endpoint":
        return {"endpoint": d["registration"]["endpoint"]}
    if name == "compatible-units":
        return {"total_meters": sum(r["amount"] * (1000 if r["unit"] == "km" else 1) for r in d["observations"])}
    if name == "syndication-lineage":
        return {"independent_studies": len({r["origin"] for r in d["reports"]})}
    if name == "attrition-warning":
        percentages = [100 * r["lost"] / r["assigned"] for r in d["groups"]]
        return {"imbalanced": max(percentages) - min(percentages) > d["threshold_percentage_points"]}
    if name == "absolute-risk":
        control = 100 * d["control_events"] / d["control_total"]
        treated = 100 * d["treated_events"] / d["treated_total"]
        return {"percentage_points": int(control - treated), "relative_percent": int(100 * (control - treated) / control)}
    if name == "correlation-interpretation":
        return {"association": "positive" if d["coefficient"] > 0 else "negative" if d["coefficient"] < 0 else "none", "causal": False}
    if name == "multiple-testing":
        return {"significant_ids": sorted(r["id"] for r in d["tests"] if r["p_value"] <= d["family_alpha"] / d["test_count"])}
    if name == "bias-sensitivity":
        values = [r["effect"] for r in d["studies"] if not r["high_bias"]]
        return {"clean_mean": sum(values) // len(values)}
    if name == "method-match":
        row = next(r for r in d["reports"] if r["method"] == d["requested_method"])
        return {"value": row["value"], "source_id": row["id"]}
    if name == "erratum-crosswalk":
        values = dict(d["study"])
        if d["erratum"]["study_id"] == values["id"]:
            values[d["erratum"]["field"]] = d["erratum"]["replacement"]
        return {"capacity": values["capacity"], "cost": values["cost"]}
    if name == "evidence-absence":
        ids = sorted(r["id"] for r in d["sources"] if d["requested_claim"] in r["claims"])
        return {"state": "supported" if ids else "unresolved", "source_ids": ids}
    if name == "speaker-attribution":
        return {"speaker": d["transcript"]["speaker"]}
    if name == "marginal-identification":
        return {"overlap": None, "state": "unidentified"}
    if name == "funding-disclosure":
        return {"commissioner": d["commissioner"], "independently_funded": d["independent_funding"]}
    if name == "paired-change":
        return {"mean_change": sum(r["after"] - r["before"] for r in d["pairs"]) // len(d["pairs"])}
    raise ValueError(name)


def _plan_from_source(name, d):
    if name == "dependency-frontier":
        done = set(d["done"])
        return {"ready_ids": sorted(r["id"] for r in d["tasks"] if r["id"] not in done and set(r["needs"]) <= done)}
    if name == "uninterrupted-slot":
        row = min((r for r in d["free_intervals"] if r["end"] - r["start"] >= d["duration_minutes"]), key=lambda r: r["start"])
        return {"slot_id": row["id"]}
    if name == "minimum-budget":
        minimum = sum(d["minimums"].values())
        return {"minimum_total": minimum, "extra_affordable": minimum + d["optional_extra"] <= d["budget"]}
    if name == "receipt-confirmation":
        return {"confirmed": d["receipt"]["request_id"] == d["request"]["id"] and d["receipt"]["status"] == "confirmed"
                and d["receipt"]["allocated_slots"] == d["request"]["requested_slots"]}
    if name == "holiday-recurrence":
        return {"day": min(day for day in d["allowed_days"] if day >= d["scheduled_day"] and day not in d["closed_days"])}
    if name == "critical-path":
        tasks = {r["id"]: r for r in d["tasks"]}
        def finish(task_id):
            task = tasks[task_id]
            return task["duration"] + max((finish(parent) for parent in task["needs"]), default=0)
        return {"finish_minutes": max(finish(task_id) for task_id in tasks)}
    if name == "travel-gap":
        threshold = d["previous_end"] + d["travel_minutes"]
        return {"appointment_id": min((r for r in d["candidates"] if r["start"] >= threshold), key=lambda r: r["start"])["id"]}
    if name == "capacity-packing":
        selected, capacity = [], 0
        for row in d["items_priority_order"]:
            if capacity + row["size"] <= d["capacity"]:
                selected.append(row["id"])
                capacity += row["size"]
        return {"item_ids": selected, "used_capacity": capacity}
    if name == "cancellation-boundary":
        return {"allowed": d["requested_minute"] < d["cutoff_minute"] or
                          (d["requested_minute"] == d["cutoff_minute"] and d["inclusive"])}
    if name == "lead-time":
        return {"start_day": d["delivery_day"] - d["preparation_days"]}
    if name == "consent-invitation":
        return {"invitee_ids": sorted(r["id"] for r in d["people"] if r["member"] and r["consent"] and r["consent_until"] >= d["as_of_day"])}
    if name == "local-day":
        days, minutes = divmod(d["utc_minute"] + d["fixed_offset_hours"] * 60, 1440)
        return {"local_day_index": d["utc_day_index"] + days, "local_minute": minutes}
    if name == "resource-collision":
        def available(row):
            return all(row["end"] <= booked["start"] or row["start"] >= booked["end"] for booked in d["bookings"]
                       if booked["resource"] == d["requested_resource"])
        row = min((r for r in d["candidates"] if available(r)), key=lambda r: r["start"])
        return {"slot_id": row["id"], "start_minute": row["start"]}
    if name == "energy-rest":
        start = d["first_duration"] + d["required_rest"]
        return {"second_start": start, "finish": start + d["second_duration"]}
    if name == "release-gates":
        missing = sorted(set(d["required_gates"]) - set(d["passed"]))
        return {"ready": not missing, "missing_gates": missing}
    if name == "batch-setup":
        batches = ceil(d["items"] / d["batch_capacity"])
        return {"batches": batches, "total_minutes": batches * d["setup_minutes"] + d["items"] * d["per_item_minutes"]}
    if name == "closed-route":
        from heapq import heappop, heappush
        queue = [(0, [d["start"]])]
        while queue:
            distance, path = heappop(queue)
            if path[-1] == d["end"]:
                return {"route": path, "minutes": distance}
            for edge in d["edges"]:
                if not edge["closed"] and edge["from"] == path[-1] and edge["to"] not in path:
                    heappush(queue, (distance + edge["minutes"], path + [edge["to"]]))
        raise ValueError("No advertised route")
    if name == "parallel-handoff":
        return {"finish_minutes": max(d["team_minutes"]) + d["handoff_minutes"]}
    if name == "fair-rotation":
        row = min((r for r in d["members"] if r["available"]), key=lambda r: (r["assignments"], r["id"]))
        return {"member_id": row["id"]}
    if name == "retry-escalation":
        return {"action": "escalate" if d["failed_attempts"] >= d["maximum_attempts"] else "retry"}
    if name == "priority-aging":
        ranked = [(r["base"] + r["waiting_hours"] * d["aging_per_hour"], r["id"]) for r in d["queue"]]
        score, item_id = sorted(ranked, key=lambda pair: (-pair[0], pair[1]))[0]
        return {"item_id": item_id, "score": score}
    if name == "contingency-trigger":
        return {"activate": d["backup_prepared"] and d["forecast_percent"] >= d["trigger_percent"]}
    if name == "single-vendor-kit":
        row = min((r for r in d["suppliers"] if set(d["needed"]) <= set(r["available"])), key=lambda r: r["kit_price"])
        return {"supplier_id": row["id"], "price": row["kit_price"]}
    if name == "delegate-chain":
        people, person, visited = {r["id"]: r for r in d["people"]}, d["owner"], set()
        while person is not None and person not in visited:
            visited.add(person)
            row = people[person]
            if row["available"]:
                return {"delegate_id": person}
            person = row["delegate"]
        return {"delegate_id": None}
    if name == "workday-capacity":
        load = sum(d["tasks_hours"]) * d["minutes_per_hour"]
        return {"load_minutes": load, "fits": load <= d["working_day_minutes"]}
    raise ValueError(name)


def _compute_from_source(name, d):
    if name == "join-cardinality":
        orders = {row["order_id"]: row["order_total"] for row in d["joined_rows"]}
        return {"order_count": len(orders), "order_total": sum(orders.values())}
    if name == "null-zero":
        values = [value for value in d["measurements"] if value is not None]
        return {"count": len(values), "mean_numerator": sum(values), "mean_denominator": len(values)}
    if name == "locale-decimal":
        amount = d["amount"].replace(d["thousands_separator"], "").replace(d["decimal_separator"], ".")
        return {"minor_units": int(Decimal(amount) * 100)}
    if name == "credit-sign":
        return {"net": sum(row["amount"] * (-1 if row["kind"] == "credit" else 1) for row in d["entries"])}
    if name == "page-retry":
        pages = {row["page"]: row["rows"] for row in d["attempts"] if row["status"] == "completed"}
        return {"total": sum(sum(pages.get(page, [])) for page in d["required_pages"]),
                "complete": set(d["required_pages"]) <= pages.keys()}
    if name == "weighted-average":
        return {"average": sum(row["price"] * row["quantity"] for row in d["lines"]) // sum(row["quantity"] for row in d["lines"])}
    if name == "nearest-rank":
        values = sorted(d["values"])
        return {"percentile_value": values[ceil(d["percentile"] * len(values) / 100) - 1]}
    if name == "even-median":
        return {"median": int(median(d["values"]))}
    if name == "sample-variance":
        mean = sum(d["values"]) / len(d["values"])
        return {"variance": int(sum((value - mean) ** 2 for value in d["values"]) / (len(d["values"]) - 1))}
    if name == "counter-reset":
        readings = d["counter"]
        return {"increments": readings[0] + sum(current - previous if current >= previous else current
                                                 for previous, current in zip(readings, readings[1:]))}
    if name == "overlap-dedup":
        rows = {row["id"]: row["value"] for extract in d["extracts"] for row in extract}
        return {"total": sum(rows.values()), "event_count": len(rows)}
    if name == "fiscal-quarter":
        return {"quarter": ((d["month"] - d["fiscal_start_month"]) % 12) // 3 + 1}
    if name == "offset-bucket":
        counts = {}
        for row in d["events"]:
            day = row["utc_day"] + (row["utc_minute"] + d["fixed_offset_minutes"]) // 1440
            counts[str(day)] = counts.get(str(day), 0) + 1
        return {"day_counts": counts}
    if name == "concentration-units":
        return {"grams_tenths": d["liters"] * d["milligrams_per_liter"] // d["milligrams_per_tenth_gram"]}
    if name == "index-baseline":
        return {"index": d["current"] * 100 // d["baseline"] if d["baseline"] else None,
                "state": "defined" if d["baseline"] else "undefined"}
    if name == "row-permissions":
        return {"total": sum(row["amount"] for row in d["rows"] if d["current_audience"] in row["readers"])}
    if name == "outer-join":
        groups = {}
        for row in d["facts"]:
            group = d["dimensions"].get(row["dimension_id"], "unmapped")
            groups[group] = groups.get(group, 0) + row["amount"]
        return {"groups": groups}
    if name == "full-window":
        k, values = d["window"], d["values"]
        return {"averages": [None if i + 1 < k else sum(values[i + 1 - k:i + 1]) // k for i in range(len(values))]}
    if name == "numeric-identifiers":
        return {"ordered_ids": sorted(d["ids"], key=int)}
    if name == "subtotal-level":
        return {"total": sum(row["amount"] for row in d["rows"] if row["level"] == "leaf")}
    if name == "dated-price-join":
        total = 0
        for transaction in d["transactions"]:
            price = next(row["price"] for row in d["prices"] if row["from_day"] <= transaction["day"] < row["until_day"])
            total += transaction["quantity"] * price
        return {"revenue": total}
    if name == "exchange-direction":
        return {"home_amount": d["foreign_amount"] // d["foreign_per_home"]}
    if name == "successive-discounts":
        amount = Decimal(d["starting_cents"])
        for discount in d["discount_percentages"]:
            amount *= Decimal(100 - discount) / 100
        return {"final_cents": int(amount)}
    if name == "competition-rank":
        ordered = sorted(d["scores"], key=lambda row: -row["score"])
        return {"ranks": {row["id"]: 1 + sum(other["score"] > row["score"] for other in ordered) for row in ordered}}
    if name == "rounding-stage":
        amounts = [Decimal(value) for value in d["amounts"]]
        quantize = lambda value: value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total = sum(quantize(value) for value in amounts) if d["stage"] == "line" else quantize(sum(amounts))
        return {"minor_units": int(total * 100)}
    raise ValueError(name)


def _write_from_source(name, d):
    if name == "incident-brief":
        facts = {"incident": d["incident_id"], "state": d["state"], "affected_services": d["affected_services"]}
        text = f"{d['incident_id']}: monitoring {d['affected_services']} affected services."
    elif name == "public-excerpt":
        facts = {"audience": d["audience"], "release_date": d["release_date"]}
        text = f"{d['product']} is scheduled for release on {d['release_date']}."
    elif name == "tentative-announcement":
        status = "confirmed" if d["approval"] else "proposed"
        facts = {"status": status, "target_date": d["target_date"]}
        text = f"{d['project']}: {status} target date {d['target_date']}."
    elif name == "minutes-open-question":
        facts = {"owner": d["owner"], "action": d["action"], "question_state": "open"}
        text = f"{d['owner']} will {d['action']}. Open question: {d['question']}"
    elif name == "plain-language":
        facts = {"tested_hours": d["tested_hours"]}
        text = f"In the test, the {d['glossary']['battery utilization']} {d['tested_hours']} hours."
    elif name == "correction-notice":
        facts = {"old_count": d["original_count"], "new_count": d["corrected_count"], "unit": d["unit"]}
        text = f"Correction: replace {d['original_count']} with {d['corrected_count']} {d['unit']}."
    elif name == "disputed-brief":
        values = [d["report_a"]["count"], d["report_b"]["count"]]
        facts = {"reported_counts": values, "resolved": False}
        text = f"The reports disagree: one counts {values[0]}, the other {values[1]}."
    elif name == "quoted-speaker":
        facts = {"speaker": d["speaker"], "quote": d["quote"]}
        text = f"{d['speaker']} said: {d['quote']}"
    elif name == "observable-alt-text":
        facts = {"objects": d["visible_objects"], "people": d["people_visible"]}
        text = f"A {d['visible_objects'][0]} rests on a {d['visible_objects'][1]}."
    elif name == "invitation-details":
        facts = {"start": d["start"], "zone": d["zone"], "date": d["date"]}
        text = f"Invitation: {d['agenda']} on {d['date']} at {d['start']}, {d['zone']}."
    elif name == "bounded-product-claim":
        facts = {"scenario": d["tested_scenario"], "measured_hours": d["measured_hours"]}
        text = f"Measured {d['measured_hours']} hours in the {d['tested_scenario']} scenario."
    elif name == "refund-review":
        facts = {"review_status": d["review_status"], "refund_issued": d["refund_issued"], "requested_cents": d["requested_cents"]}
        text = f"{d['case_id']}: review {d['review_status']}; requested {d['requested_cents']} cents, refund not issued."
    elif name == "decision-risk-brief":
        facts = {"decision": d["decision"], "risk": d["risk"], "risk_resolved": d["risk_resolved"]}
        text = f"Decision: {d['decision']}. Unresolved risk: {d['risk']}."
    elif name == "anonymized-story":
        facts = {"segment": d["segment"], "experience": d["experience"]}
        text = f"A {d['segment']} reported {d['experience']}."
    elif name == "work-status":
        status = "completed" if d["delivered"] else "in progress"
        facts = {"status": status}
        text = f"{d['project']}: {status}."
    elif name == "release-limitation":
        facts = {"revision": d["revision"], "change": d["change"], "limitation": d["limitation"]}
        text = f"Revision {d['revision']}: {d['change']}; {d['limitation']}."
    elif name == "dated-comparison":
        facts = {"earlier": d["earlier_count"], "later": d["later_count"], "change": d["later_count"] - d["earlier_count"]}
        text = f"In {d['earlier_year']}, {d['earlier_count']} were counted; in {d['later_year']}, {d['later_count']} were counted."
    elif name == "conditional-guide":
        action = d["procedure"]["online" if d["gateway_online"] else "offline"]
        facts = {"gateway_online": d["gateway_online"], "action": action}
        text = f"If online, {d['procedure']['online']}; if offline, {d['procedure']['offline']}."
    elif name == "alternative-decline":
        facts = {"permitted_action": d["available_action"], "sent": False}
        text = f"I cannot send; I can {d['available_action']}."
    elif name == "uncertain-range":
        facts = {"lower_hours": d["lower_hours"], "upper_hours": d["upper_hours"], "certain": False}
        text = f"Estimate range: {d['lower_hours']} to {d['upper_hours']} hours."
    elif name == "rounded-measurement":
        quantum = Decimal(1).scaleb(-d["decimal_places"])
        value = str(Decimal(d["measurement"]).quantize(quantum, rounding=ROUND_HALF_UP))
        facts = {"rounded": value, "unit": d["unit"]}
        text = f"Rounded measurement: {value} {d['unit']}."
    elif name == "opt-in-draft":
        facts = {"audience": d["allowed_group"], "topic": d["topic"]}
        text = f"For {d['allowed_group']}: an update about {d['topic']}."
    elif name == "transit-notice":
        facts = {"status": d["observed_status"], "estimated_arrival": d["estimated_arrival"], "delivered": False}
        text = f"{d['shipment']} is {d['observed_status']}; estimated arrival {d['estimated_arrival']}."
    elif name == "attributed-review":
        facts = {"reviewer": d["reviewer"], "opinion": d["opinion"], "measured_minutes": d["measured_minutes"]}
        text = f"{d['reviewer']} described it as {d['opinion']}. {d['test_source']} measured {d['measured_minutes']} minutes."
    elif name == "glossary-translation":
        facts = {"gate_term": d["glossary"]["gate"], "garden_term": d["glossary"]["garden"], "quantity": d["quantity"]}
        text = f"{d['quantity']} {d['glossary']['gate']} del {d['glossary']['garden']}."
    else:
        raise ValueError(name)
    return {"text": text, "facts": facts}
