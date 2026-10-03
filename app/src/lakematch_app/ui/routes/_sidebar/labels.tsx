import { createFileRoute } from "@tanstack/react-router";
import { useListLabels } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export const Route = createFileRoute("/_sidebar/labels")({
  component: () => <Labels />,
});

// Every row of the label store, newest first, with its provenance.
function Labels() {
  const q = useListLabels({ params: { limit: 500 }, query: { select: (d) => d.data.labels } });
  if (q.isLoading) return <Skeleton className="h-96 w-full" />;
  if (q.isError) return <p className="text-destructive">Labels unavailable: {String(q.error)}</p>;
  const rows = q.data ?? [];
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Labels</h1>
      <Card>
        <CardContent className="overflow-x-auto pt-4">
          {rows.length === 0 && <p className="text-muted-foreground">No label yet.</p>}
          {rows.length > 0 && (
            <table className="w-full text-xs">
              <thead className="text-muted-foreground text-left">
                <tr>
                  {["when (UTC)", "reviewer", "pair", "decision", "reason", "model version", "p", "queued as", "LLM"].map((h) => (
                    <th key={h} className="py-1 pr-3 font-normal">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.label_id} className="border-t align-top">
                    <td className="py-1 pr-3 whitespace-nowrap">{r.labelled_at.replace("T", " ").slice(0, 19)}</td>
                    <td className="py-1 pr-3">{r.reviewer}</td>
                    <td className="py-1 pr-3 font-mono">{r.l_id} ↔ {r.r_id}</td>
                    <td className="py-1 pr-3">{r.decision.replace("_", " ")}</td>
                    <td className="py-1 pr-3">{r.reason}</td>
                    <td className="py-1 pr-3 font-mono">{r.model_version}</td>
                    <td className="py-1 pr-3 tabular-nums">{r.p?.toFixed(3) ?? "—"}</td>
                    <td className="py-1 pr-3">{r.queue_reason?.replace("_", " ")}</td>
                    <td className="py-1">{r.llm_label ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
