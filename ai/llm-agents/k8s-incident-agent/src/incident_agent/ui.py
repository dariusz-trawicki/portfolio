"""The approval page served at GET / by `incident-agent serve` (step 5b, instead of Slack).

One self-contained HTML file: no build step, no external assets, works offline. It polls
GET /incidents and calls POST /incidents/{id}/approve|reject — the same API the CLI uses.
Everything coming from the agent (LLM text included) is inserted with textContent, never innerHTML.
"""

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Incident Agent</title>
<link rel="icon" href="data:,">
<style>
:root {
  --bg: #f6f7f9; --panel: #ffffff; --ink: #14171c; --muted: #5d6673; --line: #dde1e7;
  --accent: #2f5bea; --ok: #1d7a46; --ok-bg: #e5f4ec; --warn: #9a5b00; --warn-bg: #fdf1dc;
  --bad: #b42318; --bad-bg: #fde8e6; --info-bg: #e8eefd; --code-bg: #f0f2f5; --on-ok: #ffffff;
  --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0f1216; --panel: #171b21; --ink: #e7eaee; --muted: #98a1ad; --line: #2a3039;
    --accent: #7f9cff; --ok: #5fd08f; --ok-bg: #12301f; --warn: #f0b456; --warn-bg: #36270d;
    --bad: #ff8a80; --bad-bg: #3a1513; --info-bg: #19223b; --code-bg: #0b0e12; --on-ok: #08210f;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink);
  font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, sans-serif; }
header { display: flex; flex-wrap: wrap; align-items: baseline; gap: 12px 24px; padding: 20px 24px 12px;
  border-bottom: 1px solid var(--line); background: var(--panel); }
h1 { font-size: 18px; margin: 0; letter-spacing: -0.01em; }
h1 span { color: var(--muted); font-weight: 500; }
.counts { display: flex; gap: 16px; color: var(--muted); font-size: 13px; }
.counts b { color: var(--ink); font-variant-numeric: tabular-nums; }
.live { margin-left: auto; font-size: 12px; color: var(--muted); }
.live::before { content: ""; display: inline-block; width: 7px; height: 7px; border-radius: 50%;
  background: var(--ok); margin-right: 6px; vertical-align: 1px; }
.live.down::before { background: var(--bad); }
main { max-width: 980px; margin: 0 auto; padding: 20px 16px 48px; }
.auth { display: none; gap: 8px; align-items: center; margin-bottom: 16px; padding: 12px 14px;
  background: var(--warn-bg); color: var(--warn); border-radius: 8px; }
.auth.show { display: flex; flex-wrap: wrap; }
.empty { color: var(--muted); padding: 48px 0; text-align: center; }
.card { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 16px 18px;
  margin-bottom: 12px; }
.card.awaiting { border-color: var(--warn); box-shadow: 0 0 0 1px var(--warn) inset; }
.top { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; }
.id { font-family: var(--mono); font-size: 13px; color: var(--muted); }
.svc { font-weight: 600; }
.when { margin-left: auto; color: var(--muted); font-size: 12px; }
.badge { font-size: 12px; font-weight: 600; padding: 2px 8px; border-radius: 999px; white-space: nowrap; }
.s-awaiting_approval { background: var(--warn-bg); color: var(--warn); }
.s-done { background: var(--ok-bg); color: var(--ok); }
.s-failed { background: var(--bad-bg); color: var(--bad); }
.s-queued, .s-investigating, .s-remediating, .s-skipped { background: var(--info-bg); color: var(--accent); }
.diag { margin: 10px 0 0; display: grid; grid-template-columns: max-content 1fr; gap: 4px 14px; font-size: 14px; }
.diag dt { color: var(--muted); }
.diag dd { margin: 0; }
code, .cmd { font-family: var(--mono); font-size: 13px; }
.cmd { display: block; background: var(--code-bg); border: 1px solid var(--line); border-radius: 6px;
  padding: 8px 10px; margin-top: 10px; overflow-x: auto; white-space: pre; }
.alerts { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 6px; }
.chip { font-size: 12px; border: 1px solid var(--line); border-radius: 6px; padding: 1px 6px; color: var(--muted); }
.chip.firing { color: var(--bad); border-color: var(--bad); }
.decide { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; align-items: center; }
input { font: inherit; padding: 7px 10px; border-radius: 6px; border: 1px solid var(--line);
  background: var(--panel); color: var(--ink); min-width: 0; }
input.comment { flex: 1 1 260px; }
button { font: inherit; font-weight: 600; padding: 7px 14px; border-radius: 6px; border: 1px solid transparent;
  cursor: pointer; }
button:disabled { opacity: .5; cursor: default; }
.approve { background: var(--ok); color: var(--on-ok); }
.reject { background: transparent; color: var(--bad); border-color: var(--bad); }
.link { background: none; border: none; color: var(--accent); padding: 0; font-weight: 500; }
.outcome { margin-top: 10px; font-size: 14px; }
.outcome li { margin: 2px 0; }
.bad { color: var(--bad); }
pre.report { white-space: pre-wrap; word-break: break-word; background: var(--code-bg); border-radius: 6px;
  padding: 12px; font-size: 12.5px; max-height: 420px; overflow: auto; margin: 10px 0 0; }
.note { color: var(--muted); font-size: 12px; margin-top: 24px; }
@media (max-width: 560px) { .diag { grid-template-columns: 1fr; } .diag dt { margin-top: 6px; } }
</style>
</head>
<body>
<header>
  <h1>Incident Agent <span>· approvals</span></h1>
  <div class="counts" id="counts"></div>
  <div class="live" id="live">live</div>
</header>
<main>
  <div class="auth" id="auth">This agent needs the webhook token (WEBHOOK_TOKEN).
    <input id="token" type="password" placeholder="token" autocomplete="off">
    <button class="approve" id="saveToken">Save</button></div>
  <div id="list"><div class="empty">Loading…</div></div>
  <p class="note">The agent never changes anything on its own: a fix runs only after Approve, through
    an allow-listed executor (flag → off, rollout undo), and is then verified.</p>
</main>
<script>
const $ = (sel, el = document) => el.querySelector(sel);
const store = {
  get(k) { try { return localStorage.getItem(k) || ""; } catch { return ""; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch {} },
};
const open = new Set();        // incidents whose report is expanded
const drafts = {};             // unsent comments, survive re-renders
let busy = false;

function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v);
  }
  for (const kid of kids.flat()) {
    if (kid == null || kid === false) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

function headers(json) {
  const hd = json ? { "Content-Type": "application/json" } : {};
  const t = store.get("ia-token");
  if (t) hd["Authorization"] = "Bearer " + t;
  return hd;
}

function ago(iso) {
  if (!iso) return "";
  const s = Math.max(0, (Date.now() - Date.parse(iso)) / 1000);
  if (s < 60) return Math.round(s) + " s ago";
  if (s < 3600) return Math.round(s / 60) + " min ago";
  return Math.round(s / 3600) + " h ago";
}

async function load() {
  try {
    const r = await fetch("/incidents", { headers: headers(false) });
    $("#auth").classList.toggle("show", r.status === 401);
    if (!r.ok) throw new Error(r.status);
    $("#live").classList.remove("down"); $("#live").textContent = "live";
    render(await r.json());
  } catch (e) {
    $("#live").classList.add("down"); $("#live").textContent = "agent unreachable";
  }
}

function render(items) {
  if (busy || document.activeElement?.classList.contains("comment")) return;  // don't steal focus mid-typing
  const by = {};
  for (const i of items) by[i.status] = (by[i.status] || 0) + 1;
  $("#counts").replaceChildren(
    h("span", {}, h("b", {}, by.awaiting_approval || 0), " awaiting approval"),
    h("span", {}, h("b", {}, (by.investigating || 0) + (by.remediating || 0) + (by.queued || 0)), " in progress"),
    h("span", {}, h("b", {}, items.length), " total"));
  const order = { awaiting_approval: 0, remediating: 1, investigating: 2, queued: 3 };
  items.sort((a, b) => (order[a.status] ?? 9) - (order[b.status] ?? 9) || (b.opened_at > a.opened_at ? 1 : -1));
  $("#list").replaceChildren(...(items.length ? items.map(card)
    : [h("div", { class: "empty" }, "No incidents yet. Inject a fault: incident-agent chaos inject payment-failure")]));
  for (const id of open) fetchReport(id);
}

function card(i) {
  const waiting = i.status === "awaiting_approval";
  const p = i.proposal;
  const el = h("article", { class: "card" + (waiting ? " awaiting" : ""), id: "inc-" + i.id },
    h("div", { class: "top" },
      h("span", { class: "svc" }, i.service),
      h("span", { class: "id" }, i.id),
      h("span", { class: "badge s-" + i.status }, i.status.replace("_", " ")),
      i.follows ? h("span", { class: "id", title: "fired again after this finished incident" }, "follows " + i.follows) : null,
      h("span", { class: "when" }, ago(i.opened_at))),
    h("div", { class: "alerts" }, (i.alerts || []).map(a =>
      h("span", { class: "chip" + (a.firing ? " firing" : ""), title: a.role }, a.name + " · " + a.service))));
  if (i.culprit_service) {
    el.append(h("dl", { class: "diag" },
      h("dt", {}, "Culprit"), h("dd", {}, h("code", {}, i.culprit_service), "  ·  ", i.category,
        i.confidence != null ? "  ·  confidence " + Math.round(i.confidence * 100) + "%" : ""),
      i.root_cause ? [h("dt", {}, "Root cause"), h("dd", {}, i.root_cause)] : null,
      h("dt", {}, "Action"), h("dd", {}, h("code", {}, i.recommended_action || "–"),
        p && !p.executable ? "  — not automated: " + p.reason : "")));
  }
  if (p && p.executable) el.append(h("code", { class: "cmd" }, p.command));
  if (waiting) el.append(decide(i));
  const out = outcome(i);
  if (out) el.append(out);
  if (i.error) el.append(h("p", { class: "outcome bad" }, i.error));
  el.append(h("div", { class: "decide" }, h("button", { class: "link", onclick: () => toggle(i.id) },
    open.has(i.id) ? "Hide report" : "Show report")));
  if (open.has(i.id)) el.append(h("pre", { class: "report", id: "rep-" + i.id }, "Loading…"));
  return el;
}

function decide(i) {
  const who = h("input", { placeholder: "your name", value: store.get("ia-who"), size: "12", "aria-label": "Your name" });
  const note = h("input", { class: "comment", placeholder: "comment for the report (optional)", "aria-label": "Comment" });
  note.value = drafts[i.id] || "";
  note.addEventListener("input", () => { drafts[i.id] = note.value; });
  const send = async (approved, btn) => {
    if (approved && !confirm("Run this fix on the cluster?\n\n" + i.proposal.command)) return;
    busy = true; btn.disabled = true;
    store.set("ia-who", who.value.trim());
    try {
      const r = await fetch(`/incidents/${encodeURIComponent(i.id)}/${approved ? "approve" : "reject"}`, {
        method: "POST", headers: headers(true),
        body: JSON.stringify({ by: who.value.trim() || "web", comment: note.value.trim() }) });
      if (!r.ok) alert((await r.json().catch(() => ({}))).detail || ("HTTP " + r.status));
      delete drafts[i.id];
    } finally { busy = false; load(); }
  };
  return h("div", { class: "decide" }, who, note,
    h("button", { class: "approve", onclick: e => send(true, e.target) }, "Approve fix"),
    h("button", { class: "reject", onclick: e => send(false, e.target) }, "Reject"));
}

function outcome(i) {
  const d = i.decision, x = i.execution, v = i.verification;
  if (!d && !x && !v) return null;
  const li = [];
  if (d) li.push(h("li", {}, (d.approved ? "Approved" : "Rejected") + " by " + d.by + (d.comment ? " — " + d.comment : "")));
  if (x) li.push(h("li", { class: x.ok ? "" : "bad" }, x.ok ? "Executed: " + x.output : "Execution failed: " + x.error));
  if (v) li.push(h("li", { class: v.recovered === false ? "bad" : "" },
    v.recovered === true ? `Verified after ${Math.round(v.after_s)} s · ${v.method || "alert cleared"}`
      : v.recovered === false ? "NOT recovered: " + (v.detail || "") : (v.detail || "Not verified")));
  if (i.status === "remediating") li.push(h("li", {}, "Fix running / verifying…"));
  return h("ul", { class: "outcome" }, li);
}

async function fetchReport(id) {
  const el = document.getElementById("rep-" + id);
  if (!el) return;
  try {
    const r = await fetch("/incidents/" + encodeURIComponent(id), { headers: headers(false) });
    el.textContent = r.ok ? ((await r.json()).report || "(no report yet)") : "HTTP " + r.status;
  } catch { el.textContent = "agent unreachable"; }
}

function toggle(id) { open.has(id) ? open.delete(id) : open.add(id); load(); }

$("#saveToken").addEventListener("click", () => { store.set("ia-token", $("#token").value.trim()); load(); });
load();
setInterval(load, 3000);
</script>
</body>
</html>
"""
