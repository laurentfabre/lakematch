import { createFileRoute } from "@tanstack/react-router";
import { useStats, type StatsOut } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export const Route = createFileRoute("/_sidebar/stats")({
  component: () => <Stats />,
});

const pct = (v?: number | null) => (v == null ? "—" : `${(v * 100).toFixed(1)} %`);

function Stats() {
  const q = useStats({ query: { select: (d) => d.data, refetchInterval: 30_000 } });
  if (q.isLoading) return <Skeleton className="h-96 w-full" />;
  if (q.isError || !q.data) return <p className="text-destructive">Statistics unavailable: {String(q.error)}</p>;
  return <StatsView s={q.data} />;
}

function Tile({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-lg border p-3">
      <div className="text-muted-foreground text-xs">{label}</div>
      <div className="text-2xl font-semibold tabular-nums">{value}</div>
      {sub && <div className="text-muted-foreground text-xs">{sub}</div>}
    </div>
  );
}

function Counts({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data);
  if (!entries.length) return <span className="text-muted-foreground">none</span>;
  return (
    <span className="tabular-nums">
      {entries.map(([k, v]) => `${k.replace("_", " ")} ${v}`).join(" · ")}
    </span>
  );
}

function StatsView({ s }: { s: StatsOut }) {
  const cur = s.labels.current;
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Statistics</h1>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Tile label="labels (current)" value={(cur.match ?? 0) + (cur.no_match ?? 0) + (cur.unsure ?? 0)}
              sub={`match ${cur.match ?? 0} · no match ${cur.no_match ?? 0} · unsure ${cur.unsure ?? 0}`} />
        <Tile label="human ↔ LLM agreement" value={pct(s.agreement.rate)}
              sub={`${s.agreement.agree} of ${s.agreement.pairs} pairs both labelled`} />
        <Tile label="queue depth" value={s.queue.pending} sub={`of ${s.queue.total} queued · ${s.queue.labelled} labelled`} />
        <Tile label="quarantined (latest run)"
              value={s.quarantine.latest ? s.quarantine.latest.left + s.quarantine.latest.right : "—"}
              sub={s.quarantine.latest ? `left ${s.quarantine.latest.left} · right ${s.quarantine.latest.right}` : "no run yet"} />
      </div>

      <Card>
        <CardHeader><CardTitle className="text-base">Precision and recall by model version</CardTitle></CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-sm tabular-nums">
            <thead className="text-muted-foreground text-left">
              <tr>
                <th className="py-1 pr-3 font-normal">model version</th>
                <th className="py-1 pr-3 font-normal">run</th>
                <th className="py-1 pr-3 font-normal">labels</th>
                <th className="py-1 pr-3 font-normal">app labels used</th>
                <th className="py-1 pr-3 font-normal">threshold</th>
                <th className="py-1 pr-3 font-normal">precision</th>
                <th className="py-1 pr-3 font-normal">recall</th>
                <th className="py-1 pr-3 font-normal">F1</th>
                <th className="py-1 pr-3 font-normal">reviewed pairs</th>
                <th className="py-1 pr-3 font-normal">precision (reviewed)</th>
                <th className="py-1 font-normal">recall (reviewed)</th>
              </tr>
            </thead>
            <tbody>
              {s.model_versions.map((v) => (
                <tr key={v.model_version} className="border-t">
                  <td className="py-1 pr-3 font-mono text-xs">{v.model_version}</td>
                  <td className="py-1 pr-3 text-xs">{v.created_at?.replace("T", " ").slice(0, 16) ?? "—"}</td>
                  <td className="py-1 pr-3">{v.label_source ?? "—"}{v.labels_train != null ? ` (${v.labels_train} train)` : ""}</td>
                  <td className="py-1 pr-3">{v.app_labels_used ?? "—"}</td>
                  <td className="py-1 pr-3">{v.threshold ?? "—"}</td>
                  <td className="py-1 pr-3">{pct(v.precision)}</td>
                  <td className="py-1 pr-3">{pct(v.recall)}</td>
                  <td className="py-1 pr-3">{pct(v.f1)}</td>
                  <td className="py-1 pr-3">{v.human_labelled}</td>
                  <td className="py-1 pr-3">{pct(v.human_precision)}</td>
                  <td className="py-1">{pct(v.human_recall)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-muted-foreground mt-2 text-xs">
            Precision / recall / F1: each run's links against its evaluation sample (the truth set when the config
            names one). Reviewed: the model's decision at its threshold against the reviewers' match / no-match labels
            on the pairs that version scored — a sample biased towards the hard pairs by construction.
          </p>
        </CardContent>
      </Card>

      <div className="grid gap-3 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle className="text-base">Labels</CardTitle></CardHeader>
          <CardContent className="space-y-1 text-sm">
            <p>Rows in the store: {s.labels.events} ({s.labels.retracted} retractions)</p>
            <p>Provenance complete (reviewer, time, model version, reason): {s.labels.complete_provenance} of {s.labels.events}</p>
            <p>By reviewer: <Counts data={s.labels.by_reviewer} /></p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-base">Human and LLM labeller</CardTitle></CardHeader>
          <CardContent className="space-y-1 text-sm">
            <p>Both labelled: {s.agreement.pairs} · agree {s.agreement.agree} ({pct(s.agreement.rate)})</p>
            <p>Human / LLM: <Counts data={s.agreement.confusion} /></p>
            <p>LLM unsure on labelled pairs: {s.agreement.llm_unsure_on_labelled} · LLM opinions in the queue: {s.agreement.llm_opinions_in_queue}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-base">Queue</CardTitle></CardHeader>
          <CardContent className="space-y-1 text-sm">
            <p>Pending by reason: <Counts data={s.queue.pending_by_reason} /></p>
            <p>Queued by reason: <Counts data={s.queue.total_by_reason} /></p>
            <p className="text-muted-foreground text-xs">Scored by {s.queue.model_version ?? "—"}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-base">Quarantine by run</CardTitle></CardHeader>
          <CardContent>
            <table className="w-full text-sm tabular-nums">
              <thead className="text-muted-foreground text-left">
                <tr><th className="font-normal">run</th><th className="font-normal">left</th><th className="font-normal">right</th></tr>
              </thead>
              <tbody>
                {s.quarantine.history.map((r) => (
                  <tr key={r.run_id} className="border-t">
                    <td className="py-1 text-xs">{r.created_at?.replace("T", " ").slice(0, 16) ?? r.run_id}</td>
                    <td>{r.left}</td>
                    <td>{r.right}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
