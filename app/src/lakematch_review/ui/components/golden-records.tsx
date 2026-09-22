// Lakematch APX synthetic golden-record explorer, 2026-09-22.
import { Suspense, useState } from "react";
import { QueryErrorResetBoundary } from "@tanstack/react-query";
import { ErrorBoundary } from "react-error-boundary";
import { Building2, GitBranch, History, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SourceComparison } from "@/components/source-comparison";
import { useGoldenDemoCatalogSuspense, useGoldenDemoDetailSuspense } from "@/lib/api";
import type { DemoFieldOut } from "@/lib/api";

const label = (name: string) => name.replaceAll("_", " ");
const source = (name: string) => ({ erp_vendor: "ERP vendors", crm_account: "CRM accounts" })[name] ?? label(name);
const reasons: Record<string, string> = {
  approved_override: "An approved steward edit sets this value.",
  source_priority: "The policy prefers this source when verification is equal.",
  verified: "The verified source takes precedence.",
  quality: "The higher quality assessment takes precedence.",
  freshness: "The more recent source value takes precedence.",
  source_id: "A stable source order resolves the tie.",
  source_key: "A stable source-key order resolves the tie.",
  only_eligible_value: "This is the only eligible value.",
  no_eligible_value: "No eligible source value is available.",
};

function Loading() {
  return <div className="golden-loading" role="status" aria-live="polite"><div className="golden-skeleton" /><span>Loading the company record…</span></div>;
}

function DataBoundary({ children }: { children: React.ReactNode }) {
  return <QueryErrorResetBoundary>{({ reset }) => <ErrorBoundary onReset={reset} fallbackRender={({ resetErrorBoundary }) =>
    <section className="error-banner" role="alert"><p>The company demo could not load. Try again to read the packaged records.</p><Button variant="outline" onClick={resetErrorBoundary}>Try again</Button></section>
  }><Suspense fallback={<Loading />}>{children}</Suspense></ErrorBoundary>}</QueryErrorResetBoundary>;
}

export function GoldenRecords() {
  return <section aria-label="Golden records demo">
    <div className="golden-demo-note"><ShieldCheck size={19} /><p><strong>Synthetic company demo</strong> Explore six legal companies from ERP and CRM. Memberships are predefined for this example; these records are separate from your review queue.</p></div>
    <DataBoundary><CompanyPicker /></DataBoundary>
  </section>;
}

function CompanyPicker() {
  const { data: { data: catalog } } = useGoldenDemoCatalogSuspense({ query: { retry: false } });
  const [selected, setSelected] = useState(catalog.default_master_id);
  const [publication, setPublication] = useState<"first" | "second">("second");
  if (!catalog.companies.length) return <section className="empty-state"><h2>No demo companies available</h2><p>Rebuild the packaged demo to restore the synthetic records.</p></section>;
  return <>
    <div className="golden-controls">
      <label>Company<select aria-label="Company" value={selected} onChange={e => setSelected(e.target.value)}>{catalog.companies.map(c => <option key={c.master_id} value={c.master_id}>{c.legal_name} · {c.country}</option>)}</select></label>
      <label>Publication<select aria-label="Publication" value={publication} onChange={e => setPublication(e.target.value as "first" | "second")}>
        {catalog.publications.map(p => <option value={p} key={p}>{p === "first" ? "1 · Original values" : "2 · Updates and approved edit"}</option>)}
      </select></label>
    </div>
    <DataBoundary key={`${selected}-${publication}`}><CompanyDetail masterId={selected} publication={publication} /></DataBoundary>
  </>;
}

function FieldEvidence({ field }: { field: DemoFieldOut }) {
  const winner = field.decision_id ? "Approved edit" : field.winner_source_id ? source(field.winner_source_id) : "No selected source";
  return <details className="golden-field" open={field.name === "legal_name" ? true : undefined}>
    <summary><span className="golden-field-label">{label(field.name)}</span><span className="golden-field-value">{field.value ?? <em>No value</em>}</span><span className="golden-winner">{winner}</span></summary>
    <div className="golden-field-evidence">
      <p>{reasons[field.reason] ?? `Selection rule: ${label(field.reason)}.`}</p>
      {field.conflicting_values && <p className="golden-conflict">The source values differ. The selected value follows the policy shown here.</p>}
      {field.decision_id ? <p>Decision <code>{field.decision_id}</code> · approved by <strong>{field.approved_by}</strong><br />{field.decision_reason}</p> : field.winner_source_id && <p>Selected from {source(field.winner_source_id)} · {field.winner_source_key} · source version {field.winner_version}</p>}
      <div className="comparison-scroll"><table className="simple-table"><caption className="sr-only">Source values for {label(field.name)}</caption><thead><tr><th scope="col">Source</th><th scope="col">Recorded value</th><th scope="col">Eligibility</th></tr></thead>
        <tbody>{field.alternatives.map(a => <tr key={`${a.source_id}-${a.source_key}`}><th scope="row">{source(a.source_id)}<small>{a.source_key} · v{a.version}</small></th><td>{a.value ?? <em>No value</em>}</td><td>{a.excluded ? `Excluded: ${label(a.excluded)}` : a.verified ? "Verified source value" : "Eligible source value"}</td></tr>)}</tbody>
      </table></div>
    </div>
  </details>;
}

function CompanyDetail({ masterId, publication }: { masterId: string; publication: "first" | "second" }) {
  const { data: { data: detail } } = useGoldenDemoDetailSuspense({ params: { master_id: masterId, publication }, query: { retry: false } });
  const entity = detail.entity;
  return <article className="golden-record" aria-labelledby="golden-title">
    <header className="golden-header"><div className="golden-company-icon"><Building2 size={28} /></div><div><p className="eyebrow">LEGAL COMPANY</p><h2 id="golden-title">{entity.values.legal_name}</h2><p>{entity.values.country} · {entity.values.registration_id ?? "Registration identifier unavailable"}</p></div></header>
    <div className="golden-revisions"><span><History size={15} />Data revision <strong>{entity.revision}</strong></span><span><GitBranch size={15} />Identity revision <strong>{entity.identity_revision}</strong></span><span>{entity.sources.filter(s => !s.deleted).length} active sources · {entity.sources.filter(s => s.deleted).length} deleted</span></div>
    <p className="golden-freshness">{publication === "first" ? "Earlier publication. Later changes are hidden." : "Second publication, including source updates and the approved name edit."} Frozen synthetic data as of {new Date(detail.as_of).toLocaleDateString("en-GB", { timeZone: "UTC", day: "numeric", month: "long", year: "numeric" })}.</p>
    <SourceComparison comparison={entity.comparison} />
    <section className="golden-values" aria-label="Published values and provenance"><div className="golden-section-heading"><h3>Every value has a story.</h3><p>Open a field to compare the source values and see why one was selected.</p></div>
      {entity.fields.map(f => <FieldEvidence key={`${detail.publication_id}-${f.name}`} field={f} />)}
    </section>
    <section className="golden-sources" aria-label="Source crosswalk"><div className="golden-section-heading"><h3>Connected source records</h3><p>These source keys refer to the same company in this synthetic fixture.</p></div>
      <div className="golden-source-grid">{entity.sources.map(s => <details key={`${s.source_id}-${s.source_key}`}><summary><strong>{source(s.source_id)}</strong><span>{s.source_key} · v{s.version} · {s.deleted ? "Deleted" : "Active"}</span></summary>
        {s.deleted ? <p>This source was deleted in this publication. Its older values remain visible in the first publication.</p> : <dl>{Object.entries(s.values).map(([key, value]) => <div key={key}><dt>{label(key)}</dt><dd>{value ?? "No value"}</dd></div>)}</dl>}
      </details>)}</div>
    </section>
    <details className="golden-receipt"><summary>Publication and policy references</summary><dl><div><dt>Persistent master ID</dt><dd><code>{entity.master_id}</code></dd></div><div><dt>Policy</dt><dd>{entity.policy_id} · version {entity.policy_version}</dd></div><div><dt>Policy checksum</dt><dd><code>{entity.policy_sha256}</code></dd></div><div><dt>Publication checksum</dt><dd><code>{detail.snapshot_sha256}</code></dd></div></dl><p>Memberships come from the declared synthetic fixture. No matching model or probability is used here.</p></details>
  </article>;
}
