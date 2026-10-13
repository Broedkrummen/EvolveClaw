import { defineControlUiPlugin, type ControlUiView, type ControlUiComponentHandle, type ControlUiHost } from "openclaw/plugin-sdk/control-ui";
import { createFeatureClient } from "openclaw/plugin-sdk/feature-contract";
import { memoryContract } from "./memory-contract.js";
import type { MemorySnapshot, RuleRecord } from "./types.js";
import "./memory-ui.css";

type ControlUiSelectPickerProps = Parameters<ControlUiHost["components"]["mountSelectPicker"]>[1];

const element = <K extends keyof HTMLElementTagNameMap>(tag: K, text = "", className = ""): HTMLElementTagNameMap[K] => {
  const el = document.createElement(tag); el.textContent = text; el.className = className; return el;
};
const button = (text: string, action: () => void) => { const b = element("button", text); b.type = "button"; b.addEventListener("click", action); return b; };

export const mountMemory: ControlUiView = (container, context) => {
  const { host, signal } = context;
  const feature = createFeatureClient(memoryContract, host);
  const root = element("section", "", "evolveclaw");
  const header = element("header");
  header.append(element("h1", "EvolveClaw"), element("p", "See what your assistant learned, where it applies, and how it changed."));
  const status = element("p", "Loading memory…", "ec-status"); status.setAttribute("role", "status"); status.setAttribute("aria-live", "polite");
  const error = element("p", "", "ec-error"); error.setAttribute("role", "alert");
  const selectors = element("div", "", "ec-toolbar");
  const scopeSlot = element("div", "", "ec-scope-picker");
  const filter = element("select"); filter.setAttribute("aria-label", "Rule status");
  for (const [value, label] of [["all", "All rule statuses"], ["active", "Active"], ["disabled", "Disabled"], ["legacy", "Legacy history"]]) {
    const o = element("option", label); o.value = value; filter.append(o);
  }
  const legacy = element("input"); legacy.type = "checkbox"; legacy.id = `ec-legacy-${crypto.randomUUID()}`;
  const legacyLabel = element("label", "Include unscoped legacy history"); legacyLabel.htmlFor = legacy.id;
  const legacyBox = element("span", "", "ec-legacy"); legacyBox.append(legacy, legacyLabel);
  const refreshButton = button("Refresh", () => void refresh());
  const learningButton = button("Pause learning", () => void mutate(paused ? "resume" : "pause"));
  selectors.append(scopeSlot, filter, legacyBox, refreshButton, learningButton);
  const note = element("p", "Choose a recorded memory scope. These labels come from earlier tasks; changing this selection does not change the assistant's current task.", "ec-note");
  const content = element("div", "", "ec-layout");
  const rulesPanel = element("section", "", "ec-panel"); rulesPanel.append(element("h2", "Learned rules"));
  const rulesList = element("div", "", "ec-rules"); rulesPanel.append(rulesList);
  const side = element("div");
  const detail = element("section", "", "ec-panel"); detail.append(element("h2", "Rule evidence"), element("p", "Choose a rule to inspect its supporting observations."));
  const history = element("section", "", "ec-panel"); history.append(element("h2", "Change history"));
  const usage = element("section", "", "ec-panel"); usage.append(element("h2", "Learning usage"));
  side.append(detail, history, usage); content.append(rulesPanel, side);
  root.append(header, selectors, note, status, error, content); container.append(root);
  let bindingId: string | undefined, revision = 0, paused = false, pending = false, generation = 0, disposed = false;
  let rules: RuleRecord[] = [], scopes: { id: string; label: string }[] = [];
  let picker: ControlUiComponentHandle<ControlUiSelectPickerProps> | undefined;
  const agentId = () => host.agents.selectedId ?? host.agents.defaultId ?? "main";
  const options = () => ({ agentId: agentId() });
  const query = async (operation: "scopes" | "list" | "history" | "detail" | "usage" | "status", ruleId?: string) => JSON.parse((await feature.invoke("query", {
    operation, bindingId, ruleId, limit: 200, includeLegacy: legacy.checked && host.connection.canAdmin,
  }, options())).data) as MemorySnapshot & { scopes?: { id: string; label: string }[] };
  const time = (date: string) => { const d = new Date(date); return Number.isNaN(d.getTime()) ? date : d.toLocaleString(host.locale); };
  function setBusy(value: boolean) {
    pending = value; root.setAttribute("aria-busy", String(value));
    refreshButton.disabled = value || !host.connection.canRead;
    learningButton.disabled = value || !bindingId || !host.connection.canWrite;
    filter.disabled = value; legacy.disabled = value || !host.connection.canAdmin;
    for (const b of root.querySelectorAll<HTMLButtonElement>("button")) {
      if (b === learningButton) continue;
      b.disabled = value || (b.dataset.write === "true" ? !host.connection.canWrite : !host.connection.canRead);
    }
  }
  function renderRules() {
    rulesList.replaceChildren();
    const selected = rules.filter(r => filter.value === "all" || r.status === filter.value);
    if (!selected.length) { rulesList.append(element("p", rules.length ? "No rules match this status. Choose another filter." : "No learned rules here yet. Complete tasks in this scope to begin building history.")); return; }
    for (const r of selected) {
      const row = element("article", "", "ec-rule");
      const meta = element("p", `${r.status} · ${r.domain} · ${r.evidence_ids.length} supporting observations`, "ec-note");
      const text = element("p", r.text, "ec-rule-text");
      const actions = element("div", "", "ec-actions");
      actions.append(button("View evidence", () => void showDetail(r.id)));
      if (r.status === "active") actions.append(writeButton("Disable", () => void mutate("disable", r.id)));
      else if (r.status === "disabled") actions.append(writeButton("Restore", () => void mutate("restore", r.id)));
      else if (r.status === "legacy" && host.connection.canAdmin) actions.append(writeButton("Assign to this scope", () => void mutate("assign_scope", r.id)));
      const id = element("small", `Rule ${r.id}`, "ec-id");
      row.append(meta, text, actions, id); rulesList.append(row);
    }
    setBusy(pending);
  }
  function writeButton(label: string, action: () => void) { const b = button(label, action); b.dataset.write = "true"; b.disabled = pending || !host.connection.canWrite; return b; }
  async function showDetail(id: string) {
    const current = ++generation;
    try {
      const snap = await query("detail", id);
      if (disposed || current !== generation) return;
      detail.replaceChildren(element("h2", "Rule evidence"));
      const value = (snap.detail ?? {}) as Record<string, unknown>;
      const r = (value.rule ?? value) as Partial<RuleRecord>;
      detail.append(element("p", r.text ?? rules.find(x => x.id === id)?.text ?? "Rule details"));
      detail.append(element("p", `Model confidence: ${r.confidence ?? "unknown"}. Confidence is not a measured task-success rate.`, "ec-note"));
      const evidence = (snap.evidence ?? value.evidence ?? []) as Record<string, unknown>[];
      if (!evidence.length) detail.append(element("p", "No supporting observation is available for this rule."));
      for (const e of evidence) {
        const record = element("article", "", "ec-observation");
        const payload = (e.payload ?? e) as Record<string, unknown>;
        record.append(element("p", String(payload.task ?? payload.summary ?? payload.error ?? "Execution observation")),
          element("p", String(payload.error ?? payload.observations ?? payload.model_output ?? "")),
          element("small", time(String(e.created_at ?? ""))));
        detail.append(record);
      }
    } catch (e) { if (!disposed && current === generation) error.textContent = (e as Error).message; }
  }
  async function mutate(operation: "disable" | "restore" | "assign_scope" | "pause" | "resume" | "promote", ruleId?: string, historyId?: string) {
    if (pending || !bindingId || !host.connection.canWrite) return;
    setBusy(true); error.textContent = ""; status.textContent = "Saving memory change…";
    ++generation;
    try {
      await feature.invoke("mutate", { operation, bindingId, ruleId, historyId, expectedRevision: revision }, options());
      if (disposed) return;
      status.textContent = "Memory change saved.";
      await refresh();
    } catch (e) { if (!disposed) { error.textContent = (e as Error).message; status.textContent = "Change was not confirmed. Refresh to inspect the current state."; } }
    finally { if (!disposed) setBusy(false); }
  }
  async function refresh() {
    const current = ++generation;
    setBusy(true); error.textContent = ""; status.textContent = "Loading memory…";
    try {
      if (!host.connection.canRead) throw new Error("Connect with memory read permission to inspect learning.");
      scopes = (await query("scopes")).scopes ?? [];
      if (disposed || current !== generation) return;
      if (!scopes.some(s => s.id === bindingId)) bindingId = scopes[0]?.id;
      const props: ControlUiSelectPickerProps = { options: scopes.map(s => ({ value: s.id, label: s.label })), value: bindingId ?? "",
        accessibleLabel: "Recorded memory scope", disabled: !scopes.length, onSelect: value => {
          bindingId = value;
          detail.replaceChildren(element("h2", "Rule evidence"), element("p", "Choose a rule to inspect its supporting observations."));
          void refresh();
        } };
      if (picker) picker.update(props); else picker = host.components.mountSelectPicker(scopeSlot, props);
      if (!bindingId) { rules = []; renderRules(); status.textContent = "No recorded scopes yet. Run a normal task first."; return; }
      const [snap, changes, consumption] = await Promise.all([query("list"), query("history"), query("usage")]);
      if (disposed || current !== generation) return;
      revision = snap.revision; paused = snap.paused; rules = snap.rules ?? [];
      learningButton.textContent = paused ? "Resume learning" : "Pause learning";
      status.textContent = `Learning ${paused ? "paused" : "active"} · revision ${revision} · ${rules.length} recorded rules${host.connection.canWrite ? "" : " · Read-only access"}`;
      renderRules();
      history.replaceChildren(element("h2", "Change history"));
      if (!changes.history?.length) history.append(element("p", "No recorded changes in this scope."));
      for (const h of changes.history ?? []) {
        const row = element("article", "", "ec-history"); row.append(element("p", h.summary || h.operation), element("small", `${time(h.created_at)} · ${h.operation}`));
        if (h.reversible !== false && !["analysis", "legacy_import", "reset"].includes(h.operation)) row.append(writeButton("Undo this change", () => void mutate("restore", undefined, h.id)));
        history.append(row);
      }
      usage.replaceChildren(element("h2", "Learning usage"));
      const u = consumption.usage ?? {};
      usage.append(element("p", `${u.calls ?? 0} learning model calls`));
      for (const label of ["actual", "estimated", "unknown"]) {
        const group = (u[label] ?? {}) as Record<string, unknown>;
        usage.append(element("p", `${label === "actual" ? "Reported" : label === "estimated" ? "Estimated" : "Unreported"}: ${group.calls ?? 0} calls${label === "unknown" ? "" : ` · ${group.input_tokens ?? 0} input / ${group.output_tokens ?? 0} output tokens`}`));
      }
      const cost = (u.cost ?? {}) as Record<string, unknown>;
      usage.append(element("p", typeof cost.amount === "number" ? `${cost.status} cost: ${new Intl.NumberFormat(host.locale, { style: "currency", currency: "USD" }).format(cost.amount)}` : "Cost is unknown. No pricing has been assigned.", "ec-note"));
    } catch (e) { if (!disposed && current === generation) { error.textContent = (e as Error).message; status.textContent = "Memory could not be refreshed. Try again."; } }
    finally { if (!disposed && current === generation) setBusy(false); }
  }
  filter.addEventListener("change", renderRules); legacy.addEventListener("change", () => void refresh());
  let connectionKey = JSON.stringify([agentId(), host.connection.connected, host.connection.canRead, host.connection.canWrite, host.connection.canAdmin]);
  const unsubscribe = host.subscribe(() => {
    const next = JSON.stringify([agentId(), host.connection.connected, host.connection.canRead, host.connection.canWrite, host.connection.canAdmin]);
    legacyBox.hidden = !host.connection.canAdmin;
    if (!host.connection.canAdmin) legacy.checked = false;
    if (next !== connectionKey) {
      connectionKey = next; bindingId = undefined; rules = []; renderRules();
      detail.replaceChildren(element("h2", "Rule evidence")); history.replaceChildren(element("h2", "Change history")); usage.replaceChildren(element("h2", "Learning usage"));
      void refresh();
    } else setBusy(pending);
  });
  legacyBox.hidden = !host.connection.canAdmin;
  signal.addEventListener("abort", dispose, { once: true });
  void refresh();
  function dispose() { if (disposed) return; disposed = true; ++generation; unsubscribe(); picker?.dispose(); root.remove(); }
  return { dispose, focus: () => refreshButton.focus() };
};

export default defineControlUiPlugin({ id: "evolveclaw", activate(host) {
  const dispose = [host.ui.registerPage({ id: "evolveclaw", label: "EvolveClaw", mount: mountMemory }),
    host.ui.registerNavigation({ id: "evolveclaw", label: "EvolveClaw", page: { id: "evolveclaw" }, icon: "brain", order: 70 }),
    host.ui.registerPanel({ id: "evolveclaw-memory", label: "Learned memory", mount: (container, context) => mountMemory(container, { ...context, props: {} }) })];
  return () => dispose.forEach(fn => fn());
} });
