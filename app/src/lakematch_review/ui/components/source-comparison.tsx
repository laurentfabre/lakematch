import { ArrowLeftRight, Info } from "lucide-react";
import type { DemoComparisonOut, DemoComparisonValueOut } from "@/lib/api";

const labels: Record<string, string> = {
  record_kind: "Record type", legal_name: "Legal name", country: "Country",
  registration_id: "Registration number", address_line1: "Street address",
  city: "City", postal_code: "Postal code",
};
const sources: Record<string, string> = { erp_vendor: "ERP vendors", crm_account: "CRM accounts" };
const states: Record<string, string> = {
  missing: "Not supplied", null: "No value", blank: "Blank value", invalid_type: "Invalid value type",
  invalid_format: "Invalid format", deleted: "Source deleted",
};

function ComparisonValue({ value }: { value: DemoComparisonValueOut }) {
  return <div className="match-value">
    <span>{value.value === null ? <em>{states[value.state] ?? "No value"}</em> : value.value === "" ? <em>Blank value</em> : value.value}</span>
    {value.state === "present" && value.normalized !== value.value && <small>Compared as: {value.normalized}</small>}
    {value.state !== "present" && value.value !== null && <small>{states[value.state]}</small>}
  </div>;
}

export function SourceComparison({ comparison }: { comparison: DemoComparisonOut }) {
  const excluded = comparison.decision.route === "exclude";
  const counts = comparison.fields.reduce((acc, field) => ({ ...acc, [field.comparison]: acc[field.comparison] + 1 }), { agree: 0, differ: 0, unavailable: 0 });
  return <section className="source-comparison" aria-labelledby="comparison-title">
    <div className="golden-section-heading"><h3 id="comparison-title"><ArrowLeftRight size={18} />Do the source records agree?</h3><p>Compare the original values and the text used by the comparison rules. Normalized agreement alone does not prove these are the same company.</p></div>
    <div className="comparison-outcome" data-route={comparison.decision.route}>
      <strong>{excluded ? "Excluded from new matching" : "Human review required"}</strong>
      <p>{comparison.decision.reason}</p>
      <span><Info size={14} />No model score · no automatic merge</span>
    </div>
    <p className="comparison-counts" aria-label="Comparison field counts"><span>{counts.agree} agree after normalization</span><span>{counts.differ} differ</span><span>{counts.unavailable} unavailable</span></p>
    <div className="match-fields">
      {comparison.fields.map(field => <details className="match-field" key={field.name} open={field.name === "registration_id" ? true : undefined}>
        <summary><span>{labels[field.name]}</span><span className="match-status" data-result={field.comparison}>{field.comparison === "agree" ? field.raw_equal ? "Same value" : "Agree after normalization" : field.comparison === "differ" ? "Different values" : "Not comparable"}</span></summary>
        <div className="match-values">{(["left", "right"] as const).map((side, index) => {
          const record = comparison.records[index];
          return <div key={side}><p className="match-source"><strong>{sources[record.source_id] ?? record.source_id}</strong><span>{record.source_key} · v{record.version}{record.deleted ? " · Deleted" : ""}</span></p><ComparisonValue value={field[side]} /></div>;
        })}</div>
      </details>)}
    </div>
    <details className="comparison-rules"><summary>Why this result?</summary><ol>{comparison.rules.map(rule => <li key={rule.rule_id}><strong>{rule.selected ? "Deciding rule" : "Also observed"}</strong><p>{rule.reason}</p></li>)}</ol><p>These records were selected from the synthetic company's predefined memberships. This comparison does not discover candidates or change the published master.</p></details>
    <details className="comparison-references"><summary>Comparison references</summary><dl>
      <div><dt>Ruleset</dt><dd>{comparison.ruleset_id} · version {comparison.ruleset_version}</dd></div>
      <div><dt>Ruleset checksum</dt><dd><code>{comparison.ruleset_sha256}</code></dd></div>
      <div><dt>Evidence checksum</dt><dd><code>{comparison.evidence_sha256}</code></dd></div>
    </dl></details>
  </section>;
}
