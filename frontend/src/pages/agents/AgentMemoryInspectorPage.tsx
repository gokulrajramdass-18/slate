/**
 * AgentMemoryInspector Page
 *
 * Per-agent browser for the 4 memory layers (Episodic, Semantic, Procedural).
 * Short-term has no UI surface — it's transient LangGraph state.
 *
 * The page also exposes a "Recall" probe at the top: type a query, hit recall,
 * and you see exactly what the agent would see prepended to its system prompt.
 *
 * Route: /agents/standalone/:id/memory  (registered in App.tsx)
 */

import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as memoryApi from "@/lib/api/agent-memory";
import * as standaloneAgentsApi from "@/lib/api/standalone-agents";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { ArrowLeft, Brain, Clock, Database, Trash2, Search, RefreshCw, Zap, Sparkles } from "lucide-react";
import { toast } from "sonner";

export default function AgentMemoryInspectorPage() {
  const { id: agentId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: agent } = useQuery({
    queryKey: ["standalone-agent", agentId],
    queryFn: () => standaloneAgentsApi.getStandaloneAgent(agentId!),
    enabled: !!agentId,
  });

  const { data: stats, refetch: refetchStats } = useQuery({
    queryKey: ["agent-memory-stats", agentId],
    queryFn: () => memoryApi.getMemoryStats(agentId!),
    enabled: !!agentId,
  });

  const { data: episodicData, isLoading: episodicLoading } = useQuery({
    queryKey: ["agent-memory-episodic", agentId],
    queryFn: () => memoryApi.listEpisodic(agentId!, { limit: 100 }),
    enabled: !!agentId,
  });

  const { data: semanticData, isLoading: semanticLoading } = useQuery({
    queryKey: ["agent-memory-semantic", agentId],
    queryFn: () => memoryApi.listSemantic(agentId!, { limit: 100 }),
    enabled: !!agentId,
  });

  const { data: proceduralData, isLoading: proceduralLoading } = useQuery({
    queryKey: ["agent-memory-procedural", agentId],
    queryFn: () => memoryApi.listProcedural(agentId!, { limit: 100 }),
    enabled: !!agentId,
  });

  const invalidateAll = () => {
    qc.invalidateQueries({ queryKey: ["agent-memory-stats", agentId] });
    qc.invalidateQueries({ queryKey: ["agent-memory-episodic", agentId] });
    qc.invalidateQueries({ queryKey: ["agent-memory-semantic", agentId] });
    qc.invalidateQueries({ queryKey: ["agent-memory-procedural", agentId] });
  };

  const deleteEpisodic = useMutation({
    mutationFn: (entryId: string) => memoryApi.deleteEpisodic(agentId!, entryId),
    onSuccess: () => {
      toast.success("Episodic memory deleted");
      invalidateAll();
    },
  });

  const deleteSemantic = useMutation({
    mutationFn: (entryId: string) => memoryApi.deleteSemantic(agentId!, entryId),
    onSuccess: () => {
      toast.success("Semantic memory deleted");
      invalidateAll();
    },
  });

  const deleteProcedural = useMutation({
    mutationFn: (entryId: string) => memoryApi.deleteProcedural(agentId!, entryId),
    onSuccess: () => {
      toast.success("Procedural memory deleted");
      invalidateAll();
    },
  });

  const pruneExpired = useMutation({
    mutationFn: () => memoryApi.pruneExpired(agentId!),
    onSuccess: (data) => {
      toast.success(data.message);
      invalidateAll();
    },
  });

  // Recall probe -------------------------------------------------------------

  const [recallQuery, setRecallQuery] = useState("");
  const [recallBundle, setRecallBundle] = useState<memoryApi.RecallBundle | null>(null);
  const recall = useMutation({
    mutationFn: (q: string) => memoryApi.recallForAgent(agentId!, q),
    onSuccess: (bundle) => setRecallBundle(bundle),
    onError: (err: any) => toast.error(err?.message || "Recall failed"),
  });

  if (!agentId) {
    return <div className="p-6">Missing agent id.</div>;
  }

  return (
    <div className="container mx-auto py-6 max-w-6xl space-y-4">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
          <ArrowLeft className="w-4 h-4 mr-1.5" />
          Back
        </Button>
        <div className="flex items-center gap-2">
          <Brain className="w-5 h-5 text-emerald-500" />
          <h1 className="text-xl font-semibold">Memory Inspector</h1>
          {agent?.name && (
            <Badge variant="outline" className="font-normal">
              {agent.name}
            </Badge>
          )}
        </div>
        <div className="flex-1" />
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            refetchStats();
            invalidateAll();
          }}
        >
          <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
          Refresh
        </Button>
      </div>

      {/* Stats overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <StatCard icon={<Zap className="w-4 h-4 text-amber-500" />} label="Short-Term" value="live" hint="LangGraph state" />
        <StatCard icon={<Clock className="w-4 h-4 text-blue-500" />} label="Episodic" value={stats?.episodic ?? "—"} />
        <StatCard icon={<Database className="w-4 h-4 text-purple-500" />} label="Semantic" value={stats?.semantic ?? "—"} />
        <StatCard icon={<Brain className="w-4 h-4 text-emerald-500" />} label="Procedural" value={stats?.procedural ?? "—"} />
      </div>

      {/* Recall probe */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-blue-500" />
            Recall preview
          </CardTitle>
          <CardDescription className="text-xs">
            See exactly what would be prepended to the agent&apos;s system prompt for a given query.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2">
            <Input
              value={recallQuery}
              onChange={(e) => setRecallQuery(e.target.value)}
              placeholder="e.g. quarterly revenue calculation"
              className="h-9 text-sm"
              onKeyDown={(e) => {
                if (e.key === "Enter" && recallQuery.trim()) recall.mutate(recallQuery);
              }}
            />
            <Button
              size="sm"
              onClick={() => recallQuery.trim() && recall.mutate(recallQuery)}
              disabled={recall.isPending || !recallQuery.trim()}
            >
              <Search className="w-3.5 h-3.5 mr-1.5" />
              Recall
            </Button>
          </div>
          {recallBundle && (
            <pre className="text-xs bg-muted/50 rounded-md p-3 overflow-x-auto whitespace-pre-wrap max-h-64 overflow-y-auto">
              {recallBundle.formatted_prompt || "(nothing recalled)"}
            </pre>
          )}
        </CardContent>
      </Card>

      {/* Layer tabs */}
      <Tabs defaultValue="episodic">
        <TabsList>
          <TabsTrigger value="episodic">
            <Clock className="w-3.5 h-3.5 mr-1.5" />
            Episodic
            {stats?.episodic ? (
              <Badge variant="secondary" className="ml-1.5 h-4 px-1.5 text-[10px]">
                {stats.episodic}
              </Badge>
            ) : null}
          </TabsTrigger>
          <TabsTrigger value="semantic">
            <Database className="w-3.5 h-3.5 mr-1.5" />
            Semantic
            {stats?.semantic ? (
              <Badge variant="secondary" className="ml-1.5 h-4 px-1.5 text-[10px]">
                {stats.semantic}
              </Badge>
            ) : null}
          </TabsTrigger>
          <TabsTrigger value="procedural">
            <Brain className="w-3.5 h-3.5 mr-1.5" />
            Procedural
            {stats?.procedural ? (
              <Badge variant="secondary" className="ml-1.5 h-4 px-1.5 text-[10px]">
                {stats.procedural}
              </Badge>
            ) : null}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="episodic" className="mt-3 space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground">
              Captured automatically from chat turns. Expired entries auto-prune on recall.
            </p>
            <Button variant="outline" size="sm" onClick={() => pruneExpired.mutate()} disabled={pruneExpired.isPending}>
              Prune expired
            </Button>
          </div>
          <EntryList
            loading={episodicLoading}
            empty="No episodic memories yet — run a chat with this agent."
            rows={(episodicData?.entries ?? []).map((e) => ({
              id: e.id,
              primary: e.content,
              secondary: [
                e.expires_at ? `Expires ${formatDate(e.expires_at)}` : "No expiry",
                `Importance ${e.importance.toFixed(2)}`,
                e.created ? formatDate(e.created) : "",
              ].filter(Boolean).join(" · "),
              tags: e.tags ?? [],
              onDelete: () => deleteEpisodic.mutate(e.id),
            }))}
          />
        </TabsContent>

        <TabsContent value="semantic" className="mt-3 space-y-2">
          <p className="text-xs text-muted-foreground">
            Durable facts. Embeddings are generated when an embedding model is configured in Settings → Models.
          </p>
          <EntryList
            loading={semanticLoading}
            empty="No semantic facts stored yet."
            rows={(semanticData?.entries ?? []).map((e) => ({
              id: e.id,
              primary: e.content,
              secondary: [
                e.has_embedding ? "Embedded" : "No embedding",
                `Used ${e.access_count}×`,
                e.last_accessed ? `last ${formatDate(e.last_accessed)}` : "",
              ].filter(Boolean).join(" · "),
              tags: e.tags ?? [],
              onDelete: () => deleteSemantic.mutate(e.id),
            }))}
          />
        </TabsContent>

        <TabsContent value="procedural" className="mt-3 space-y-2">
          <p className="text-xs text-muted-foreground">
            Tool sequences the agent has tried, sorted by success rate. Captured automatically from executions.
          </p>
          <ProceduralList
            loading={proceduralLoading}
            entries={proceduralData?.entries ?? []}
            onDelete={(id) => deleteProcedural.mutate(id)}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}

// ----------------------------------------------------------------------------
// Sub-components
// ----------------------------------------------------------------------------

function StatCard({
  icon,
  label,
  value,
  hint,
}: {
  icon: React.ReactNode;
  label: string;
  value: number | string;
  hint?: string;
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {icon}
          <span>{label}</span>
        </div>
        <div className="mt-1 text-2xl font-semibold">{value}</div>
        {hint && <div className="text-[11px] text-muted-foreground mt-0.5">{hint}</div>}
      </CardContent>
    </Card>
  );
}

interface Row {
  id: string;
  primary: string;
  secondary?: string;
  tags?: string[];
  onDelete?: () => void;
}

function EntryList({ loading, rows, empty }: { loading: boolean; rows: Row[]; empty: string }) {
  if (loading) {
    return <div className="text-xs text-muted-foreground py-6 text-center">Loading…</div>;
  }
  if (!rows.length) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-sm text-muted-foreground">{empty}</CardContent>
      </Card>
    );
  }
  return (
    <div className="space-y-2">
      {rows.map((r) => (
        <Card key={r.id}>
          <CardContent className="p-3 flex items-start gap-3">
            <div className="flex-1 min-w-0">
              <div className="text-sm whitespace-pre-wrap break-words">{r.primary}</div>
              {(r.secondary || (r.tags && r.tags.length > 0)) && (
                <div className="mt-1 flex flex-wrap gap-1.5 items-center">
                  {r.secondary && <span className="text-[11px] text-muted-foreground">{r.secondary}</span>}
                  {r.tags?.map((t) => (
                    <Badge key={t} variant="outline" className="text-[10px] h-4 px-1.5 font-normal">
                      {t}
                    </Badge>
                  ))}
                </div>
              )}
            </div>
            {r.onDelete && (
              <Button variant="ghost" size="sm" onClick={r.onDelete} className="h-7 w-7 p-0">
                <Trash2 className="w-3.5 h-3.5 text-muted-foreground hover:text-destructive" />
              </Button>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function ProceduralList({
  loading,
  entries,
  onDelete,
}: {
  loading: boolean;
  entries: memoryApi.ProceduralEntry[];
  onDelete: (id: string) => void;
}) {
  if (loading) {
    return <div className="text-xs text-muted-foreground py-6 text-center">Loading…</div>;
  }
  if (!entries.length) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-sm text-muted-foreground">
          No procedural memory yet — run a few chats with this agent and successful tool sequences will appear here.
        </CardContent>
      </Card>
    );
  }
  return (
    <div className="space-y-2">
      {entries.map((e) => {
        const ratePct = Math.round(e.success_rate * 100);
        return (
          <Card key={e.id}>
            <CardContent className="p-3">
              <div className="flex items-start gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium">{e.task_pattern}</span>
                    <Badge
                      variant={ratePct >= 80 ? "default" : ratePct >= 50 ? "secondary" : "outline"}
                      className="text-[10px] h-4 px-1.5"
                    >
                      {ratePct}% · {e.success_count}/{e.total_attempts}
                    </Badge>
                  </div>
                  <div className="mt-1 text-xs font-mono text-muted-foreground break-all">
                    {e.tool_sequence.length ? e.tool_sequence.join(" → ") : "(no tools)"}
                  </div>
                  {e.example_inputs && e.example_inputs.length > 0 && (
                    <div className="mt-1.5 text-[11px] text-muted-foreground italic line-clamp-1">
                      e.g. {String(e.example_inputs[0]).slice(0, 140)}
                    </div>
                  )}
                  <div className="mt-1 text-[11px] text-muted-foreground">
                    {e.avg_duration_ms ? `${Math.round(e.avg_duration_ms)}ms avg · ` : ""}
                    {e.last_used ? `last ${formatDate(e.last_used)}` : ""}
                  </div>
                </div>
                <Button variant="ghost" size="sm" onClick={() => onDelete(e.id)} className="h-7 w-7 p-0">
                  <Trash2 className="w-3.5 h-3.5 text-muted-foreground hover:text-destructive" />
                </Button>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString();
  } catch {
    return iso;
  }
}
