import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  addLabel,
  retractLabel,
  useNextPairs,
  type LabelOut,
  type QueueItemOut,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/_sidebar/review")({
  component: () => <Review />,
});

type Decision = "match" | "no_match" | "unsure";

// Reason codes, picked with 1-4; a decision taken without one records its default.
const REASONS = [
  "Same identity: the differences are typos or formatting",
  "A key identifier disagrees (date of birth, ID number)",
  "Different people sharing an address or a name (household, namesake)",
  "Not enough information to decide",
];
const DEFAULT_REASON: Record<Decision, number> = { match: 0, no_match: 1, unsure: 3 };
const LABEL: Record<Decision, string> = { match: "Match", no_match: "No match", unsure: "Unsure" };

const pairKey = (i: { l_id: string; r_id: string }) => `${i.l_id}|${i.r_id}`;

function why(i: QueueItemOut): string {
  const p = i.p.toFixed(3);
  switch (i.queue_reason) {
    case "llm_unsure":
      return `the LLM could not tell (P(same) ${i.llm_p_same?.toFixed(2) ?? "?"}); p ${p}`;
    case "near_threshold":
      return `p ${p} is ${i.distance.toFixed(3)} from the threshold ${i.threshold}`;
    case "high_impact":
      return `linked: the merge makes an entity of ${i.impact} records`;
    default:
      return `p ${p} (threshold ${i.threshold}); candidate rank ${i.cand_rank ?? "?"}, score ${
        i.cand_score?.toFixed(3) ?? "?"
      } — the model ${i.linked ? "links" : "rejects"} it`;
  }
}

function Review() {
  const qc = useQueryClient();
  const [skip, setSkip] = useState<string[]>([]);
  const [reason, setReason] = useState<number | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [last, setLast] = useState<LabelOut | null>(null);
  const [help, setHelp] = useState(false);
  const noteRef = useRef<HTMLInputElement>(null);

  const next = useNextPairs({ params: { skip, n: 3 }, query: { select: (d) => d.data } });
  const item = next.data?.items[0];

  const refresh = useCallback(async () => {
    await qc.invalidateQueries({ queryKey: ["/api/queue/next"] });
    void qc.invalidateQueries({ queryKey: ["/api/stats"] });
    void qc.invalidateQueries({ queryKey: ["/api/labels"] });
  }, [qc]);

  const decide = useCallback(
    async (decision: Decision) => {
      if (!item || busy) return;
      const code = REASONS[reason ?? DEFAULT_REASON[decision]];
      const text = note.trim() ? (reason !== null ? `${code} — ${note.trim()}` : note.trim()) : code;
      setBusy(true);
      try {
        const r = await addLabel({ l_id: item.l_id, r_id: item.r_id, decision, reason: text });
        setLast(r.data);
        setReason(null);
        setNote("");
        toast.success(`${LABEL[decision]} · #${item.rank} · ${text}`, { duration: 1500 });
        await refresh();
      } catch (e) {
        toast.error(`Not recorded: ${String(e)}`);
      } finally {
        setBusy(false);
      }
    },
    [item, busy, reason, note, refresh],
  );

  const undo = useCallback(async () => {
    if (!last || busy) return;
    setBusy(true);
    try {
      await retractLabel({ l_id: last.l_id, r_id: last.r_id, reason: "" });
      toast.info(`Undone: ${LABEL[last.decision as Decision] ?? last.decision} on ${last.l_id} / ${last.r_id}`);
      setSkip((s) => s.filter((k) => k !== pairKey(last)));
      setLast(null);
      await refresh();
    } catch (e) {
      toast.error(`Undo failed: ${String(e)}`);
    } finally {
      setBusy(false);
    }
  }, [last, busy, refresh]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const typing = document.activeElement === noteRef.current;
      if (typing) {
        if (e.key === "Escape" || e.key === "Enter") noteRef.current?.blur();
        return;
      }
      const k = e.key.toLowerCase();
      if (k === "m") void decide("match");
      else if (k === "n") void decide("no_match");
      else if (k === "u") void decide("unsure");
      else if (k === "s" && item) setSkip((s) => [...s, pairKey(item)]);
      else if (k === "z") void undo();
      else if (["1", "2", "3", "4"].includes(k)) setReason((r) => (r === Number(k) - 1 ? null : Number(k) - 1));
      else if (k === "/") noteRef.current?.focus();
      else if (k === "?") setHelp((h) => !h);
      else if (k === "escape") {
        setReason(null);
        setHelp(false);
      } else return;
      e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [decide, undo, item]);

  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between gap-4">
        <h1 className="text-2xl font-semibold">Review queue</h1>
        <p className="text-muted-foreground text-sm">
          <Kbd>M</Kbd> match · <Kbd>N</Kbd> no match · <Kbd>U</Kbd> unsure · <Kbd>1</Kbd>–<Kbd>4</Kbd> reason ·{" "}
          <Kbd>/</Kbd> note · <Kbd>S</Kbd> skip · <Kbd>Z</Kbd> undo · <Kbd>?</Kbd> help
        </p>
      </div>

      {help && <Help />}

      {next.isLoading && <Skeleton className="h-96 w-full" />}
      {next.isError && <p className="text-destructive">Queue unavailable: {String(next.error)}</p>}
      {next.isSuccess && !item && (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            The queue is empty{skip.length ? ` (${skip.length} skipped in this tab)` : ""}. The next run writes a new
            one.
          </CardContent>
        </Card>
      )}

      {item && (
        <Card className={cn(busy && "opacity-60")}>
          <CardHeader className="pb-2">
            <CardTitle className="flex flex-wrap items-center gap-2 text-base">
              <span className="font-mono">#{item.rank}</span>
              <Badge variant="secondary">{item.queue_reason.replace("_", " ")}</Badge>
              {item.llm_label && <Badge variant="outline">LLM: {item.llm_label}</Badge>}
              <Badge variant={item.linked ? "default" : "outline"}>{item.linked ? "linked" : "not linked"}</Badge>
              <span className="text-muted-foreground text-sm font-normal">{why(item)}</span>
            </CardTitle>
            <p className="text-muted-foreground text-xs">
              model {item.model_version} · run {item.run_id} · {item.l_id} ↔ {item.r_id}
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-muted-foreground text-left">
                  <th className="w-40 py-1 font-normal">field</th>
                  <th className="py-1 font-normal">left · {item.l_id}</th>
                  <th className="py-1 font-normal">right · {item.r_id}</th>
                </tr>
              </thead>
              <tbody className="font-mono">
                {item.fields.map((f) => (
                  <tr key={f.name} className={cn("border-t", !f.same && "bg-amber-500/10")}>
                    <td className="text-muted-foreground py-1 font-sans">{f.name}</td>
                    <td className="py-1">{f.left ?? <span className="text-muted-foreground">—</span>}</td>
                    <td className="py-1">{f.right ?? <span className="text-muted-foreground">—</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div className="flex flex-wrap gap-2">
              {REASONS.map((r, i) => (
                <button
                  key={r}
                  onClick={() => setReason(reason === i ? null : i)}
                  className={cn(
                    "rounded-md border px-2 py-1 text-xs",
                    reason === i ? "bg-primary text-primary-foreground" : "hover:bg-accent",
                  )}
                >
                  <Kbd>{i + 1}</Kbd> {r}
                </button>
              ))}
            </div>
            <Input
              ref={noteRef}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="/ to add your own words to the reason (Enter or Esc to return to the keys)"
              maxLength={400}
            />
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => void decide("match")} disabled={busy}>
                <Kbd>M</Kbd> Match
              </Button>
              <Button variant="destructive" onClick={() => void decide("no_match")} disabled={busy}>
                <Kbd>N</Kbd> No match
              </Button>
              <Button variant="secondary" onClick={() => void decide("unsure")} disabled={busy}>
                <Kbd>U</Kbd> Unsure
              </Button>
              <Button variant="outline" onClick={() => setSkip((s) => [...s, pairKey(item)])} disabled={busy}>
                <Kbd>S</Kbd> Skip
              </Button>
              <Button variant="ghost" onClick={() => void undo()} disabled={busy || !last}>
                <Kbd>Z</Kbd> Undo{last ? ` (${LABEL[last.decision as Decision] ?? last.decision})` : ""}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {next.data && next.data.items.length > 1 && (
        <p className="text-muted-foreground text-xs">
          Next: {next.data.items.slice(1).map((i) => `#${i.rank} ${i.queue_reason.replace("_", " ")}`).join(" · ")}
        </p>
      )}
    </div>
  );
}

function Kbd({ children }: { children: React.ReactNode }) {
  return <kbd className="rounded border bg-muted px-1 font-mono text-[0.7rem]">{children}</kbd>;
}

function Help() {
  return (
    <Card>
      <CardContent className="grid gap-1 py-4 text-sm md:grid-cols-2">
        <p>
          <Kbd>M</Kbd> / <Kbd>N</Kbd> / <Kbd>U</Kbd> record match, no match or unsure for the pair on screen, with
          the reason picked (or the decision's default) and your note.
        </p>
        <p>
          <Kbd>1</Kbd>–<Kbd>4</Kbd> pick a reason code; <Kbd>/</Kbd> types a note; <Kbd>Esc</Kbd> clears the pick.
        </p>
        <p>
          <Kbd>S</Kbd> skips the pair in this tab only (nothing is recorded); <Kbd>Z</Kbd> withdraws your last label
          and puts the pair back in the queue.
        </p>
        <p>
          Every label records you, the time, the model version that scored the pair, its probability and the
          reason. Unsure is recorded but never trains the model.
        </p>
      </CardContent>
    </Card>
  );
}
