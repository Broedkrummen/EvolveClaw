"""Transactional scoped memory. Model proposals never overwrite an unchecked snapshot."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import math
import sqlite3
import uuid


class RevisionConflict(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def normalize(text):
    return " ".join(text.casefold().split())


def checked_scope(scope):
    if not isinstance(scope, dict):
        raise ValueError("Trusted audience and project scope is required")
    result = {}
    for key in ("audience_key", "project_key"):
        value = scope.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > 256 or value == "*":
            raise ValueError(f"Invalid {key}")
        result[key] = value
    return result


class MemoryStore:
    def __init__(self, data_path, max_rules_per_domain=10):
        if not isinstance(max_rules_per_domain, int) or max_rules_per_domain < 1:
            raise ValueError("Strategic domain limit must be positive")
        self.path = Path(data_path) / "memory.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_rules_per_domain = max_rules_per_domain
        with self._transaction() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
                CREATE TABLE IF NOT EXISTS audiences (
                    agent TEXT, audience TEXT, revision INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(agent,audience));
                CREATE TABLE IF NOT EXISTS controls (
                    agent TEXT, audience TEXT, project TEXT, paused INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(agent,audience,project));
                CREATE TABLE IF NOT EXISTS rules (
                    id TEXT PRIMARY KEY, agent TEXT, audience TEXT, project TEXT, payload TEXT);
                CREATE INDEX IF NOT EXISTS rules_scope ON rules(agent,audience,project);
                CREATE TABLE IF NOT EXISTS records (
                    id TEXT PRIMARY KEY, kind TEXT, agent TEXT, audience TEXT, project TEXT,
                    created_at TEXT, payload TEXT);
                CREATE INDEX IF NOT EXISTS records_scope ON records(kind,agent,audience,project);
            """)
        self._import_legacy(Path(data_path) / "strategic_memory" / "global_rules.json")

    @contextmanager
    def _transaction(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("BEGIN IMMEDIATE")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _revision(self, db, agent, scope):
        row = db.execute("SELECT revision FROM audiences WHERE agent=? AND audience=?",
                         (agent, scope["audience_key"])).fetchone()
        return row[0] if row else 0

    def revision(self, agent, scope):
        scope = checked_scope(scope)
        with self._transaction() as db:
            return self._revision(db, agent, scope)

    def _check(self, db, agent, scope, expected_revision):
        if expected_revision is None or self._revision(db, agent, scope) != expected_revision:
            raise RevisionConflict("Memory changed; refresh before applying this operation")

    def _bump(self, db, agent, scope):
        db.execute("INSERT INTO audiences(agent,audience,revision) VALUES (?,?,1) "
                   "ON CONFLICT(agent,audience) DO UPDATE SET revision=revision+1",
                   (agent, scope["audience_key"]))
        return self._revision(db, agent, scope)

    def _put_rule(self, db, rule):
        db.execute("INSERT OR REPLACE INTO rules VALUES (?,?,?,?,?)", (
            rule["id"], rule["agent_name"], rule["audience_key"], rule["project_key"], json.dumps(rule)))

    def _record(self, db, kind, agent, scope, payload):
        record = {"id": str(uuid.uuid4()), "created_at": now(), **payload}
        db.execute("INSERT INTO records VALUES (?,?,?,?,?,?,?)", (
            record["id"], kind, agent, scope["audience_key"], scope["project_key"],
            record["created_at"], json.dumps(record)))
        return record

    def _import_legacy(self, path):
        with self._transaction() as db:
            if db.execute("SELECT 1 FROM meta WHERE key='legacy_imported'").fetchone():
                return
            if path.exists():
                # A malformed file is retained and the import can be retried after repair.
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("Legacy memory must be a JSON object")
                for agent, domains in data.items():
                    for domain, entries in domains.items():
                        for entry in entries:
                            text = entry.get("rule", "")
                            if not isinstance(text, str) or not text.strip():
                                continue
                            rule = self._new_rule(agent, {"audience_key": "", "project_key": ""},
                                                  text[:8000], "strategic", domain,
                                                  entry.get("confidence", 0), entry.get("source_task_id"), None)
                            rule.update(status="legacy", rationale=entry.get("rationale", ""),
                                        imported_from=str(path), legacy=True)
                            self._put_rule(db, rule)
                            self._record(db, "history", agent, {"audience_key": "", "project_key": ""},
                                         {"revision": 0, "operation": "legacy_import", "rule_ids": [rule["id"]],
                                          "summary": "Imported without activation", "before": [], "after": [rule]})
            db.execute("INSERT INTO meta VALUES ('legacy_imported',?)", (str(path),))

    def _new_rule(self, agent, scope, text, type, domain, confidence, task_id, evidence_id):
        return {"id": str(uuid.uuid4()), "agent_name": agent, **scope, "text": text,
                "type": type, "domain": domain, "confidence": float(confidence), "status": "active",
                "task_id": task_id, "revision": 0, "evidence_ids": [evidence_id] if evidence_id else [],
                "created_at": now(), "updated_at": now(), "legacy": False}

    def _rules(self, db, agent, scope, include_legacy=False):
        rows = db.execute("SELECT payload FROM rules WHERE agent=? AND "
                          "((audience=? AND project IN (?, '*')) OR (? AND audience='' AND project=''))",
                          (agent, scope["audience_key"], scope["project_key"], int(include_legacy))).fetchall()
        return [json.loads(row[0]) for row in rows]

    def _visible_rule(self, db, agent, scope, rule_id, authorize_legacy=False):
        for rule in self._rules(db, agent, scope, authorize_legacy):
            if rule["id"] == rule_id:
                return rule
        raise KeyError("Rule not found in this scope")

    def paused(self, agent, scope):
        scope = checked_scope(scope)
        with self._transaction() as db:
            return self._paused(db, agent, scope)

    def _paused(self, db, agent, scope):
        row = db.execute("SELECT paused FROM controls WHERE agent=? AND audience=? AND project=?",
                         (agent, scope["audience_key"], scope["project_key"])).fetchone()
        return bool(row[0]) if row else False

    def add_rule(self, agent, scope, text, type="strategic", domain="general", confidence=.9,
                 task_id=None, evidence_id=None, expected_revision=None, rationale=""):
        scope = checked_scope(scope)
        if type not in ("strategic", "tactical") or not text.strip() or len(text) > 8000:
            raise ValueError("Invalid rule proposal")
        if not isinstance(confidence, (float, int)) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError("Invalid rule confidence")
        with self._transaction() as db:
            self._check(db, agent, scope, expected_revision)
            if self._paused(db, agent, scope):
                return None
            # Only exact text duplicates are suppressed; opposite polarity is never a duplicate.
            existing = [r for r in self._rules(db, agent, scope)
                        if normalize(r["text"]) == normalize(text) and
                        r["status"] in ("active", "disabled", "rolled_back") and
                        (r["type"] == "strategic" or r["task_id"] == task_id)]
            if existing:
                return None  # Disabled rules must not be silently regenerated.
            rule = self._new_rule(agent, scope, text, type, domain, confidence, task_id, evidence_id)
            rule["rationale"] = rationale[:2000]
            rule["revision"] = self._bump(db, agent, scope)
            self._put_rule(db, rule)
            self._record(db, "history", agent, scope, {"revision": rule["revision"],
                         "operation": "learn", "rule_ids": [rule["id"]], "summary": f"Accepted {type} advice",
                         "before": [], "after": [rule]})
            return rule

    def active_rules(self, agent, scope, task_id=None):
        scope = checked_scope(scope)
        with self._transaction() as db:
            rules = [r for r in self._rules(db, agent, scope) if r["status"] == "active" and
                     (r["type"] == "strategic" or (task_id is not None and r["task_id"] == task_id))]
        return self._cap(rules)

    def _cap(self, rules):
        groups = {}
        for rule in sorted(rules, key=lambda r: (-r["confidence"], r["created_at"])):
            group = (rule["type"], rule["domain"])
            groups.setdefault(group, [])
            if rule["type"] == "tactical" or len(groups[group]) < self.max_rules_per_domain:
                groups[group].append(rule)
        return [r for group in groups.values() for r in group]

    def guidance(self, agent, scope):
        """Return advice and its revision from one consistent database snapshot."""
        scope = checked_scope(scope)
        with self._transaction() as db:
            rules = self._cap([r for r in self._rules(db, agent, scope)
                               if r["status"] == "active" and r["type"] == "strategic"])
            return {"revision": self._revision(db, agent, scope), "paused": self._paused(db, agent, scope),
                    "guidelines": [r["text"] for r in rules]}

    def domain_snapshot(self, agent, scope, domain):
        scope = checked_scope(scope)
        with self._transaction() as db:
            return self._revision(db, agent, scope), [r for r in self._rules(db, agent, scope)
                if r["project_key"] == scope["project_key"] and r["status"] == "active" and
                r["type"] == "strategic" and r["domain"] == domain]

    def consolidate(self, agent, scope, domain, replacements, expected_revision):
        scope = checked_scope(scope)
        with self._transaction() as db:
            self._check(db, agent, scope, expected_revision)
            if self._paused(db, agent, scope):
                return None
            before = [r for r in self._rules(db, agent, scope) if r["project_key"] == scope["project_key"]
                      and r["status"] == "active" and r["type"] == "strategic" and r["domain"] == domain]
            revision = self._bump(db, agent, scope)
            after = []
            evidence_ids = list(dict.fromkeys(e for r in before for e in r["evidence_ids"]))
            for rule in before:
                changed = {**rule, "status": "consolidated", "revision": revision, "updated_at": now()}
                self._put_rule(db, changed)
                after.append(changed)
            for replacement in replacements[:self.max_rules_per_domain]:
                text = replacement.get("rule", "")
                if not isinstance(text, str) or not text.strip() or len(text) > 8000:
                    raise ValueError("Invalid consolidated rule")
                # Keep identity when the optimizer retained an unchanged rule.
                retained = next((r for r in before if normalize(r["text"]) == normalize(text)), None)
                rule = dict(retained) if retained else self._new_rule(agent, scope, text, "strategic", domain,
                        replacement.get("confidence", .85), None, None)
                rule.update(status="active", revision=revision, updated_at=now(), evidence_ids=evidence_ids,
                            parent_ids=[r["id"] for r in before], rationale=replacement.get("rationale", "")[:2000])
                self._put_rule(db, rule)
                after = [r for r in after if r["id"] != rule["id"]] + [rule]
            self._record(db, "history", agent, scope, {"revision": revision, "operation": "consolidate",
                         "rule_ids": [r["id"] for r in after], "summary": "Compacted strategic domain",
                         "before": before, "after": after})
            return revision

    def record_evidence(self, agent, scope, task_id, trace):
        scope = checked_scope(scope)
        with self._transaction() as db:
            return self._record(db, "evidence", agent, scope, {"task_id": task_id, "trace": trace})

    def record_analysis(self, agent, scope, evidence_id, result, reason=None):
        scope = checked_scope(scope)
        with self._transaction() as db:
            return self._record(db, "history", agent, scope, {
                "revision": self._revision(db, agent, scope), "operation": "analysis", "rule_ids": [],
                "evidence_id": evidence_id, "result": result, "summary": reason or result,
                "before": [], "after": []})

    def record_usage(self, agent, scope, stage, status="unknown", input_tokens=None,
                     output_tokens=None, model=None, error=None, cost=None):
        scope = checked_scope(scope)
        if status not in ("actual", "estimated", "unknown") or stage not in ("synthesis", "classification", "consolidation"):
            raise ValueError("Invalid usage provenance")
        with self._transaction() as db:
            return self._record(db, "usage", agent, scope, {"stage": stage, "status": status,
                "input_tokens": input_tokens, "output_tokens": output_tokens, "model": model,
                "error": error, "cost": cost})

    def record_outcome(self, agent, scope, task_id, result, source, evidence_id=None, rule_ids=None, details=None):
        scope = checked_scope(scope)
        if result not in ("success", "failure", "unknown") or source not in ("fixture", "user_feedback", "external_verifier", "agent_run"):
            raise ValueError("Invalid outcome provenance")
        with self._transaction() as db:
            for rule_id in rule_ids or []:
                self._visible_rule(db, agent, scope, rule_id)
            if evidence_id:
                if not any(r["id"] == evidence_id for r in self._records(db, "evidence", agent, scope)):
                    raise KeyError("Evidence not found in this scope")
            return self._record(db, "outcome", agent, scope, {"task_id": task_id,
                "result": "unknown" if source == "agent_run" else result, "source": source,
                "validated": source != "agent_run" and result in ("success", "failure"),
                "evidence_id": evidence_id, "rule_ids": rule_ids or [], "details": details or {}})

    def _records(self, db, kind, agent, scope, include_legacy=False):
        rows = db.execute("SELECT payload FROM records WHERE kind=? AND agent=? AND "
            "((audience=? AND project IN (?, '*')) OR (? AND audience='' AND project='')) ORDER BY created_at DESC",
            (kind, agent, scope["audience_key"], scope["project_key"], int(include_legacy))).fetchall()
        return [json.loads(row[0]) for row in rows]

    def _usage(self, records):
        result = {"calls": len(records), "actual": {"calls": 0, "input_tokens": 0, "output_tokens": 0},
                  "estimated": {"calls": 0, "input_tokens": 0, "output_tokens": 0},
                  "unknown": {"calls": 0}, "by_stage": {},
                  "cost": {"status": "unknown", "amount": None, "currency": "USD"}}
        result["failed_calls"] = sum(bool(r.get("error")) for r in records)
        for record in records:
            bucket = result[record["status"]]
            bucket["calls"] += 1
            if record["status"] != "unknown":
                for key in ("input_tokens", "output_tokens"):
                    bucket[key] += record[key] or 0
            stage = record["stage"]
            result["by_stage"][stage] = result["by_stage"].get(stage, 0) + 1
        if records and all(r.get("cost") is not None for r in records):
            result["cost"] = {"status": "estimated", "amount": sum(r["cost"] for r in records), "currency": "USD"}
        return result

    def query(self, agent, scope, operation="list", args=None, authorize_legacy=False):
        scope, args = checked_scope(scope), args or {}
        include_legacy = bool(args.get("include_legacy"))
        if include_legacy and not authorize_legacy:
            raise PermissionError("Legacy memory requires owner authority")
        limit = min(200, max(1, int(args.get("limit", 100))))
        with self._transaction() as db:
            rules = self._rules(db, agent, scope, include_legacy)
            evidence = self._records(db, "evidence", agent, scope)
            visible_evidence = {r["id"] for r in evidence}
            # A broader rule never exposes another project's raw evidence or identifiers.
            visible_rule_ids = {r["id"] for r in rules}
            rules = [{**r, "evidence_ids": [e for e in r["evidence_ids"] if e in visible_evidence],
                      "parent_ids": [p for p in r.get("parent_ids", []) if p in visible_rule_ids],
                      "task_id": None if r["project_key"] == "*" else r["task_id"]} for r in rules]
            history = self._records(db, "history", agent, scope, include_legacy)
            public_history = [{**{k: v for k, v in h.items() if k not in ("before", "after")},
                               "reversible": bool(h.get("before") or h.get("after") or "previous_paused" in h)}
                              for h in history[:limit]]
            result = {"protocol_version": 3, "revision": self._revision(db, agent, scope),
                      "paused": self._paused(db, agent, scope), "rules": rules[:limit], "history": public_history,
                      "usage": self._usage(self._records(db, "usage", agent, scope)),
                      "activity": {"steps": len(evidence), "accepted": sum(h["operation"] == "learn" for h in history),
                                   "outcomes": len(self._records(db, "outcome", agent, scope))}}
            if operation == "detail":
                rule = next((r for r in rules if r["id"] == args.get("rule_id")), None)
                if rule is None:
                    raise KeyError("Rule not found in this scope")
                result["detail"] = {"rule": rule, "evidence": [{**e, "payload": e["trace"]}
                                    for e in evidence if e["id"] in rule["evidence_ids"]][:limit],
                    "outcomes": [o for o in self._records(db, "outcome", agent, scope)
                                 if rule["id"] in o["rule_ids"] or o["evidence_id"] in rule["evidence_ids"]][:limit]}
            elif operation == "export":
                domains = {}
                for rule in rules:
                    if rule["status"] == "active" and rule["type"] == "strategic":
                        domains.setdefault(rule["domain"], []).append({"rule": rule["text"],
                            "confidence": rule["confidence"], "rationale": rule.get("rationale", ""),
                            "source_task_id": rule["task_id"], "added_timestamp": rule["created_at"]})
                result["export"] = {agent: domains}
            elif operation not in ("list", "history", "usage", "status"):
                raise ValueError("Unknown query operation")
            return result

    def mutate(self, agent, scope, operation, args, expected_revision, authorize_legacy=False):
        scope, args = checked_scope(scope), args or {}
        with self._transaction() as db:
            self._check(db, agent, scope, expected_revision)
            before, after = [], []
            control_change = False
            if operation in ("pause", "resume"):
                previous = self._paused(db, agent, scope)
                control_change = True
                db.execute("INSERT INTO controls VALUES (?,?,?,?) ON CONFLICT(agent,audience,project) "
                           "DO UPDATE SET paused=excluded.paused", (agent, scope["audience_key"],
                           scope["project_key"], int(operation == "pause")))
            elif operation == "restore" and args.get("history_id"):
                change = next((h for h in self._records(db, "history", agent, scope)
                               if h["id"] == args["history_id"]), None)
                if not change:
                    raise KeyError("History not found in this scope")
                if not change.get("before") and not change.get("after") and "previous_paused" not in change:
                    raise ValueError("This history entry has no reversible change")
                if "previous_paused" in change:
                    previous = self._paused(db, agent, scope)
                    control_change = True
                    db.execute("INSERT INTO controls VALUES (?,?,?,?) ON CONFLICT(agent,audience,project) "
                        "DO UPDATE SET paused=excluded.paused", (agent, scope["audience_key"], scope["project_key"],
                        int(change["previous_paused"])))
                else:
                    old = {r["id"]: r for r in change["before"]}
                    for prior in change["after"]:
                        current = self._visible_rule(db, agent, scope, prior["id"])
                        before.append(current)
                        restored = old.get(prior["id"], {**current, "status": "rolled_back"})
                        after.append(restored)
            elif operation in ("disable", "restore", "assign_scope", "promote"):
                if operation == "assign_scope" and not authorize_legacy:
                    raise PermissionError("Legacy assignment requires owner authority")
                rule = self._visible_rule(db, agent, scope, args.get("rule_id"), authorize_legacy)
                before = [rule]
                changed = dict(rule)
                if operation == "disable":
                    changed["status"] = "disabled"
                elif operation == "restore":
                    if rule["legacy"] or rule["status"] == "legacy":
                        raise ValueError("Assign a trusted scope before activating legacy advice")
                    changed["status"] = "active"
                elif operation == "assign_scope":
                    if not rule["legacy"]:
                        raise ValueError("Only inactive legacy advice can be assigned")
                    target = checked_scope(args.get("target_scope") or scope)
                    if target != scope:
                        raise PermissionError("Assignment must target the current trusted scope")
                    changed.update(**target, status="active", legacy=False)
                else:
                    self._check_promotion(db, agent, scope, rule)
                    changed["project_key"] = "*"
                after = [changed]
            else:
                raise ValueError("Unknown mutation operation")
            revision = self._bump(db, agent, scope)
            for rule in after:
                rule.update(revision=revision, updated_at=now())
                self._put_rule(db, rule)
            payload = {"revision": revision, "operation": operation,
                       "rule_ids": [r["id"] for r in after], "summary": f"Memory {operation}",
                       "before": before, "after": after}
            if control_change:
                payload["previous_paused"] = previous
            self._record(db, "history", agent, scope, payload)
        return self.query(agent, scope, authorize_legacy=authorize_legacy)

    def _check_promotion(self, db, agent, scope, rule):
        if rule["type"] != "strategic" or rule["status"] != "active":
            raise ValueError("Only active strategic advice can be promoted")
        projects = set()
        candidates = db.execute("SELECT payload FROM rules WHERE agent=? AND audience=?", (agent, scope["audience_key"])).fetchall()
        matching = [json.loads(r[0]) for r in candidates if normalize(json.loads(r[0])["text"]) == normalize(rule["text"])
                    and json.loads(r[0])["status"] == "active" and json.loads(r[0])["type"] == "strategic"]
        for candidate in matching:
            outcomes = db.execute("SELECT payload,project FROM records WHERE kind='outcome' AND agent=? AND audience=? AND project=? ORDER BY created_at DESC",
                                  (agent, scope["audience_key"], candidate["project_key"])).fetchall()
            checked_evidence = set()
            for row in outcomes:
                outcome = json.loads(row[0])
                if not outcome["validated"] or outcome["evidence_id"] in checked_evidence:
                    continue
                checked_evidence.add(outcome["evidence_id"])
                if outcome["validated"] and outcome["result"] == "success" and outcome["evidence_id"] in candidate["evidence_ids"] and candidate["id"] in outcome["rule_ids"]:
                    projects.add(row[1])
        if len(projects - {"*", ""}) < 2:
            raise RevisionConflict("Promotion requires validated evidence from two distinct projects within this audience")

    def reset_tactical(self, agent, scope, task_id=None):
        scope = checked_scope(scope)
        with self._transaction() as db:
            before = [r for r in self._rules(db, agent, scope) if r["type"] == "tactical" and r["status"] == "active"
                      and (task_id is None or r["task_id"] == task_id)]
            if not before:
                return self._revision(db, agent, scope)
            revision = self._bump(db, agent, scope)
            after = [{**r, "status": "expired", "revision": revision, "updated_at": now()} for r in before]
            for rule in after:
                self._put_rule(db, rule)
            self._record(db, "history", agent, scope, {"revision": revision, "operation": "reset",
                "rule_ids": [r["id"] for r in after], "summary": "Expired task-specific advice", "before": before, "after": after})
            return revision
