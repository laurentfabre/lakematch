// Modified for lakematch on 2026-09-20 from the APX 0.3.8 scaffold.
import { createFileRoute } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { ErrorBoundary } from "react-error-boundary";
import { Check, X, HelpCircle, ArrowRight, Layers, BarChart3, History, RefreshCw, Building2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiError, useReviewQueue, useReviewStats, useReviewHistory, useSession, saveReview } from "@/lib/api";
import { GoldenRecords } from "@/components/golden-records";
import type { ReviewIn } from "@/lib/api";

export const Route = createFileRoute("/")({ component: () => <ErrorBoundary fallback={<main className="review-shell"><h1>Review could not load</h1><p>Reload the page to try again. Saved reviews are preserved.</p></main>}><ReviewApp /></ErrorBoundary> });
const pct = (n: number) => `${(n * 100).toFixed(1)}%`;

function errorText(error: unknown) {
  if (error instanceof ApiError && typeof error.body === "object" && error.body && "detail" in error.body && typeof error.body.detail === "string") return error.body.detail;
  return "The request could not complete. Retry, or refresh to check what was saved.";
}

function ReviewApp() {
  const client = useQueryClient();
  const [tab, setTab] = useState<"review" | "statistics" | "history" | "golden">(window.location.hash === "#golden-records" ? "golden" : "review");
  const queue = useReviewQueue({ query: { enabled: tab !== "golden", retry: false } });
  const stats = useReviewStats({ query: { enabled: tab !== "golden", retry: false } });
  const session = useSession({ query: { retry: false } });
  const history = useReviewHistory({ query: { enabled: tab === "history", retry: false } });
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  const pending = useRef<ReviewIn | null>(null);
  const inFlight = useRef(false);
  const reasonInput = useRef<HTMLTextAreaElement>(null);
  const workspace = useRef<HTMLElement>(null);
  const pair = queue.data?.data[0];
  const counts = stats.data?.data;
  const refresh = useCallback(async () => { await client.invalidateQueries(); }, [client]);

  const submit = useCallback(async (decision: ReviewIn["decision"]) => {
    if (!pair || inFlight.current || queue.isFetching) return;
    if (!reason.trim()) { setError("Add a reason before saving your decision."); reasonInput.current?.focus(); return; }
    inFlight.current = true; setSaving(true); setError(""); setSaved("");
    const prior = pending.current;
    const body: ReviewIn = prior?.pair_id === pair.pair_id && prior.decision === decision && prior.reason === reason.trim() ? prior : {
      pair_id: pair.pair_id, model_version: pair.model_version, decision, reason: reason.trim(), request_id: crypto.randomUUID(),
    };
    pending.current = body;
    try {
      await saveReview(body);
      pending.current = null; setReason("");
      setSaved(`Saved ${decision.replace("_", " ")} with your reason.`);
      await refresh(); workspace.current?.focus();
    } catch (e) { setError(errorText(e)); }
    finally { inFlight.current = false; setSaving(false); }
  }, [pair, reason, refresh, queue.isFetching]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement;
      if (tab !== "review" || e.repeat || e.isComposing || e.ctrlKey || e.metaKey || e.altKey || target.closest("input, textarea, select, [contenteditable=true]")) return;
      const key = e.key.toLowerCase();
      if (key === "r") { e.preventDefault(); reasonInput.current?.focus(); }
      const decision = ({ m: "match", n: "no_match", u: "unsure" } as const)[key as "m" | "n" | "u"];
      if (decision) { e.preventDefault(); void submit(decision); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [submit, tab]);

  return <div className="review-app">
    <aside className="review-sidebar">
      <a className="brand" href="/" aria-label="Lakematch home"><span className="brand-mark"><Layers size={23} /></span>lakematch<span className="brand-dot">.</span></a>
      <p className="eyebrow sidebar-label">ENTITY RESOLUTION</p>
      <nav aria-label="Main navigation">
        {([{ id: "review", label: "Review queue", icon: Layers }, { id: "statistics", label: "Statistics", icon: BarChart3 }, { id: "history", label: "Review history", icon: History }, { id: "golden", label: "Golden records", icon: Building2 }] as const).map(item => <button key={item.id} aria-current={tab === item.id ? "page" : undefined} onClick={() => setTab(item.id)}><item.icon size={18} />{item.label}{item.id === "review" && counts && <span className="nav-count">{counts.queue_depth}</span>}</button>)}
      </nav>
      <div className="sidebar-footer"><span className="status-dot" />{session.data ? session.data.data.user : "Connecting…"}<p>Decisions with a traceable history.</p></div>
    </aside>
    <div className="review-content">
      <header className="topbar"><span>Workspace <span className="crumb">/</span> {tab === "review" ? "Review queue" : tab === "statistics" ? "Statistics" : tab === "golden" ? "Golden records" : "Review history"}</span><Button variant="ghost" onClick={() => void refresh()} disabled={saving}><RefreshCw size={15} /> Refresh</Button></header>
      <main className="review-shell" ref={workspace} tabIndex={-1}>
        <div className="page-heading"><div><p className="eyebrow">{tab === "golden" ? "COMPANY MASTER DATA" : "HUMAN REVIEW"}</p><h1>{tab === "review" ? "A closer look." : tab === "statistics" ? "Every decision counts." : tab === "golden" ? "One company. The full picture." : "The decision trail."}</h1><p>{tab === "review" ? "Compare the records. Leave a reason. Help the next model learn." : tab === "statistics" ? "Review progress and recorded model quality, in one place." : tab === "golden" ? "Trace a golden record back to the people, policies and sources behind it." : "Your saved decisions, with the context that led to them."}</p></div><span className="batch-badge">{tab === "golden" ? "Synthetic demo" : counts ? `${counts.reviewed} reviewed` : "Loading batch"}</span></div>
        {tab !== "golden" && (queue.error || stats.error || session.error || history.error) && <div role="alert" className="error-banner">{errorText(queue.error || stats.error || session.error || history.error)} <button onClick={() => void refresh()}>Retry</button></div>}
        {tab === "golden" && <GoldenRecords />}
        {tab === "review" && <>
          <div className="queue-summary"><span><strong>{counts?.queue_depth ?? "—"}</strong> pairs awaiting a decision</span><span>Uncertain pairs first <ArrowRight size={14} /></span></div>
          {queue.isPending ? <div className="empty-state" role="status">Loading the review queue…</div> : pair ? <>
            <section className="pair-panel" aria-labelledby="pair-title">
              <div className="pair-heading"><div><span className="eyebrow">NEXT IN QUEUE</span><h2 id="pair-title">Do these records describe the same entity?</h2></div><span className="confidence"><strong>{pct(pair.probability)}</strong> match probability</span></div>
              <div className="probability-track" role="meter" aria-label="Match probability" aria-valuenow={pair.probability * 100} aria-valuemin={0} aria-valuemax={100}><span style={{ width: pct(pair.probability) }} /><i style={{ left: pct(pair.threshold) }} /></div>
              <div className="pair-context"><span>Decision threshold {pct(pair.threshold)}</span><span>{pair.llm_decision ? `LLM: ${pair.llm_decision.replace("_", " ")}` : "No LLM label"} · {pair.impact ?? 2} records affected</span></div>
              <div className="comparison-scroll"><table className="comparison"><thead><tr><th scope="col">FIELD</th><th scope="col"><span className="record-tag">A</span> Source record <small>{pair.a_id}</small></th><th scope="col"><span className="record-tag right">B</span> Candidate record <small>{pair.b_id}</small></th></tr></thead><tbody>{Array.from(new Set([...Object.keys(pair.left), ...Object.keys(pair.right)])).map(field => { const differs = pair.left[field] !== pair.right[field]; return <tr key={field} className={differs ? "different" : ""}><th scope="row">{field.replaceAll("_", " ")}{differs && <span className="difference-label">DIFFERS</span>}</th><td>{pair.left[field] || <em>Missing</em>}</td><td>{pair.right[field] || <em>Missing</em>}</td></tr>; })}</tbody></table></div>
              <div className="model-note">Scored by <code>{pair.model_version}</code></div>
            </section>
            <section className="decision-panel" aria-label="Your decision"><label htmlFor="reason">What informed your decision? <kbd>R</kbd></label><textarea id="reason" ref={reasonInput} value={reason} maxLength={1000} disabled={saving} onChange={e => setReason(e.target.value)} onKeyDown={e => { if (e.key === "Escape") { workspace.current?.focus(); e.preventDefault(); } }} placeholder="For example: same name and postcode, but a different birth date." /><div className="decision-footer"><span>Reason required · Esc returns to shortcuts</span><div className="decision-buttons"><Button variant="outline" disabled={saving || queue.isFetching} onClick={() => void submit("unsure")}><HelpCircle /> Unsure <kbd>U</kbd></Button><Button className="no-match-button" variant="outline" disabled={saving || queue.isFetching} onClick={() => void submit("no_match")}><X /> No match <kbd>N</kbd></Button><Button className="match-button" disabled={saving || queue.isFetching} onClick={() => void submit("match")}><Check /> Match <kbd>M</kbd></Button></div></div></section>
          </> : !queue.error && <section className="empty-state"><Check size={32} /><h2>You're up to date.</h2><p>All pairs in this batch have a saved decision.</p></section>}
          {error && <p role="alert" className="error-banner">{error}</p>}<p className="save-status" role="status" aria-live="polite">{saving ? "Saving your decision…" : saved}</p>
        </>}
        {tab === "statistics" && counts && <>
          <div className="stat-grid">{[["Reviewed", counts.reviewed], ["In queue", counts.queue_depth], ["Quarantined", counts.quarantine ?? "Unavailable"], ["LLM agreement", counts.llm_agreement === null ? "Unavailable" : pct(counts.llm_agreement)]].map(([label, value]) => <section className="stat-card" key={label}><p>{label}</p><strong>{value}</strong></section>)}</div>
          <section className="data-panel"><h2>Review decisions</h2>{[["Match", counts.match], ["No match", counts.no_match], ["Unsure", counts.unsure]].map(([label, value]) => <div className="decision-stat" key={label}><span>{label}</span><meter min={0} max={Math.max(1, counts.reviewed)} value={Number(value)} aria-label={String(label)} /><strong>{value}</strong></div>)}<p className="muted">Agreement uses {counts.llm_compared} resolved human/LLM pairs. Unsure reviews stay out of training.</p></section>
          <section className="data-panel"><h2>Model quality over time</h2>{counts.evaluations.length ? <div className="comparison-scroll"><table className="simple-table"><thead><tr><th>Model</th><th>Precision</th><th>Recall</th><th>Sample</th><th>Context</th></tr></thead><tbody>{counts.evaluations.map(e => <tr key={e.model_version}><td><code>{e.model_version}</code></td><td>{pct(e.precision)}</td><td>{pct(e.recall)}</td><td>{e.sample_size}</td><td>{e.context}</td></tr>)}</tbody></table></div> : <p>No recorded evaluation is available for this batch.</p>}</section>
        </>}
        {tab === "history" && <section className="data-panel"><h2>Saved reviews</h2>{history.isPending ? <p>Loading history…</p> : !history.data?.data.length ? <p>No reviews saved yet.</p> : <ol className="history-list">{[...history.data.data].sort((a,b) => b.reviewed_at.localeCompare(a.reviewed_at)).map(r => <li key={r.request_id}><div><strong>{r.decision.replace("_", " ")}</strong><time dateTime={r.reviewed_at}>{new Date(r.reviewed_at).toLocaleString()}</time></div><p>{r.reason}</p><small>{r.a_id} ↔ {r.b_id} · {r.user}</small><code>{r.model_version}</code></li>)}</ol>}</section>}
      </main>
    </div>
  </div>;
}
