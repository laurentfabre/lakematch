import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { genieAsk, useGenieConfig, type GenieAnswerOut } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";

export const Route = createFileRoute("/_sidebar/genie")({
  component: () => <GeniePanel />,
});

const SUGGESTED = [
  "Which states have the most linked pairs whose two sources disagree on surname?",
  "How many merges in the last run produced entities of more than 5 records?",
  "What is the precision of the links by the number of empty fields in the left record?",
];

// Questions to the lakematch Genie agent, asked as the signed-in user (paid_features.genie, genie_auth_mode: user).
function GeniePanel() {
  const cfg = useGenieConfig({ query: { select: (d) => d.data } });
  const [question, setQuestion] = useState("");
  const [conversation, setConversation] = useState<string | null>(null);
  const [answers, setAnswers] = useState<{ q: string; a: GenieAnswerOut }[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (cfg.isLoading) return <Skeleton className="h-64 w-full" />;
  if (!cfg.data?.enabled)
    return <p className="text-muted-foreground">Genie is off for this deployment (paid_features.genie).</p>;

  const ask = async (q: string) => {
    if (!q.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const r = await genieAsk({ question: q.trim(), conversation_id: conversation });
      setConversation(r.data.conversation_id ?? null);
      setAnswers((a) => [{ q: q.trim(), a: r.data }, ...a]);
      setQuestion("");
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between gap-4">
        <h1 className="text-2xl font-semibold">Ask Genie</h1>
        <p className="text-muted-foreground text-xs">
          asked as you ({cfg.data.auth.replaceAll("_", " ")}) · space {cfg.data.space_id}
          {conversation && (
            <>
              {" · "}
              <button className="underline" onClick={() => setConversation(null)}>new conversation</button>
            </>
          )}
        </p>
      </div>
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          void ask(question);
        }}
      >
        <Input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Ask about links, entities, the queue, labels…" />
        <Button type="submit" disabled={busy || !question.trim()}>{busy ? "Asking…" : "Ask"}</Button>
      </form>
      {answers.length === 0 && (
        <div className="flex flex-wrap gap-2">
          {SUGGESTED.map((s) => (
            <button key={s} className="rounded-md border px-2 py-1 text-xs hover:bg-accent" onClick={() => void ask(s)}>
              {s}
            </button>
          ))}
        </div>
      )}
      {error && <p className="text-destructive text-sm">{error}</p>}
      {answers.map(({ q, a }, i) => (
        <Card key={i}>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">{q}</CardTitle>
            <p className="text-muted-foreground text-xs">{a.status} · asked as {a.asked_as}</p>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {a.text && <p>{a.text}</p>}
            {a.error && <p className="text-destructive">{a.error}</p>}
            {a.columns.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-xs tabular-nums">
                  <thead className="text-muted-foreground text-left">
                    <tr>{a.columns.map((c) => <th key={c} className="py-1 pr-3 font-normal">{c}</th>)}</tr>
                  </thead>
                  <tbody>
                    {a.rows.map((r, j) => (
                      <tr key={j} className="border-t">{r.map((v, k) => <td key={k} className="py-1 pr-3">{v ?? "—"}</td>)}</tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {a.sql && (
              <details>
                <summary className="text-muted-foreground cursor-pointer text-xs">SQL</summary>
                <pre className="bg-muted mt-1 overflow-x-auto rounded p-2 text-xs">{a.sql}</pre>
              </details>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
