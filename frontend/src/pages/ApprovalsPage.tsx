import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Clock, CheckCircle, XCircle, AlertCircle, User, Calendar, Play, Eye, Workflow as WorkflowIcon, ChevronDown, ChevronUp, Search, Sparkles, Inbox } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useAuthStore } from "@/lib/stores/auth-store";
import { workflowApprovalsApi } from "@/lib/api/workflow-approvals";
import { apiClient } from "@/lib/api/client";

interface Approval {
  id: string;
  workflow_id: string | null;
  execution_id: string | null;
  node_id: string;
  approval_prompt: string;
  approval_options: string[];
  required_approvers: string[];
  input_data: Record<string, any>;
  status: "pending" | "approved" | "rejected" | "timed_out";
  response?: string;
  comment?: string;
  approved_by?: string;
  timeout_seconds?: number;
  timeout_action?: string;
  timeout_at?: string;
  created_at: string;
  responded_at?: string;
}

interface WorkflowExecution {
  id: string;
  workflow_id: string;
  template_id?: string;
  template_name?: string;
  status: "pending" | "running" | "completed" | "failed" | "paused";
  trigger_type: "immediate" | "scheduled";
  started_at?: string;
  completed_at?: string;
  duration_ms?: number;
  created_at: string;
}

export default function ApprovalsPage() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const user = useAuthStore((state) => state.user);
  const userId = user?.id || user?.username || "test-user";
  const [selectedApproval, setSelectedApproval] = useState<Approval | null>(null);
  const [selectedExecution, setSelectedExecution] = useState<WorkflowExecution | null>(null);
  const [comment, setComment] = useState("");
  const [activeTab, setActiveTab] = useState("pending");
  const [workflowsTab, setWorkflowsTab] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [expandedCards, setExpandedCards] = useState<Set<string>>(new Set());
  const itemsPerPage = 5;

  const { data: approvals = [], isLoading } = useQuery<Approval[]>({
    queryKey: ["approvals", activeTab, userId],
    queryFn: () => workflowApprovalsApi.getInbox(activeTab !== "all" && activeTab !== "workflows" ? activeTab : undefined) as unknown as Promise<Approval[]>,
    refetchInterval: 5000,
    enabled: activeTab !== "workflows",
  });

  const { data: allApprovals = [] } = useQuery<Approval[]>({
    queryKey: ["approvals-all", userId],
    queryFn: () => workflowApprovalsApi.getInbox() as unknown as Promise<Approval[]>,
    refetchInterval: 5000,
  });

  const { data: workflowExecutions = [], isLoading: workflowsLoading } = useQuery<WorkflowExecution[]>({
    queryKey: ["workflow-executions", workflowsTab, userId],
    queryFn: async () => {
      const response = await apiClient.get('/template-executions', {
        params: { user_id: userId }
      });
      return response.data;
    },
    refetchInterval: 10000,
    enabled: activeTab === "workflows",
  });

  const { data: executionDetails, isLoading: executionDetailsLoading } = useQuery({
    queryKey: ["execution-details", selectedExecution?.workflow_id, selectedExecution?.id],
    queryFn: async () => {
      if (!selectedExecution?.workflow_id || !selectedExecution?.id) return null;

      const response = await apiClient.get(
        `/workflows/${selectedExecution.workflow_id}/executions/${selectedExecution.id}`
      );
      return response.data;
    },
    enabled: !!selectedExecution?.id,
  });

  const respondMutation = useMutation({
    mutationFn: async ({ approvalId, response, comment }: { approvalId: string; response: string; comment?: string }) => {
      return workflowApprovalsApi.respond(approvalId, { response, comment });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["approvals"] });
      setSelectedApproval(null);
      setComment("");
      toast({
        title: "Success",
        description: "Your response has been submitted",
      });
    },
    onError: (error: Error) => {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const handleRespond = (response: string) => {
    if (!selectedApproval) return;
    respondMutation.mutate({
      approvalId: selectedApproval.id,
      response,
      comment: comment || undefined
    });
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "pending":
        return <Clock className="h-4 w-4 text-yellow-500" />;
      case "approved":
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case "rejected":
        return <XCircle className="h-4 w-4 text-red-500" />;
      case "timed_out":
        return <AlertCircle className="h-4 w-4 text-orange-500" />;
      default:
        return null;
    }
  };

  const getStatusBadge = (status: string) => {
    const variants: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
      pending: "default",
      approved: "secondary",
      rejected: "destructive",
      timed_out: "outline",
    };

    return (
      <Badge variant={variants[status] || "outline"} className="flex items-center gap-1">
        {getStatusIcon(status)}
        {status}
      </Badge>
    );
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const getTimeRemaining = (timeoutAt?: string) => {
    if (!timeoutAt) return null;

    const now = new Date();
    const timeout = new Date(timeoutAt);
    const diff = timeout.getTime() - now.getTime();

    if (diff <= 0) return "Timed out";

    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

    return `${hours}h ${minutes}m remaining`;
  };

  const getWorkflowStatusBadge = (status: string) => {
    const variants: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
      pending: "outline",
      running: "default",
      completed: "secondary",
      failed: "destructive",
      paused: "outline",
    };

    return (
      <Badge variant={variants[status] || "outline"}>
        {status}
      </Badge>
    );
  };

  const formatDuration = (ms?: number) => {
    if (!ms) return "N/A";
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);

    if (hours > 0) return `${hours}h ${minutes % 60}m`;
    if (minutes > 0) return `${minutes}m ${seconds % 60}s`;
    return `${seconds}s`;
  };

  const toggleCardExpansion = (id: string) => {
    setExpandedCards(prev => {
      const newSet = new Set(prev);
      if (newSet.has(id)) {
        newSet.delete(id);
      } else {
        newSet.add(id);
      }
      return newSet;
    });
  };

  const parseChangeDetails = (prompt: string) => {
    try {
      const match = prompt.match(/CHANGE_DETAILS_START\s*([\s\S]*?)\s*CHANGE_DETAILS_END/);
      if (!match) return null;

      const detailsText = match[1].trim();

      const jsonArrays: any[] = [];
      let currentJson = '';
      let bracketCount = 0;

      for (let i = 0; i < detailsText.length; i++) {
        const char = detailsText[i];

        if (char === '[') {
          if (bracketCount === 0) {
            currentJson = '';
          }
          bracketCount++;
          currentJson += char;
        } else if (char === ']') {
          currentJson += char;
          bracketCount--;

          if (bracketCount === 0 && currentJson) {
            try {
              const parsed = JSON.parse(currentJson);
              jsonArrays.push(parsed);
            } catch (e) {
              console.error('Failed to parse JSON array:', currentJson, e);
            }
            currentJson = '';
          }
        } else if (bracketCount > 0) {
          currentJson += char;
        }
      }

      const modified = jsonArrays[0] || [];
      const added = jsonArrays[1] || [];
      const removed = jsonArrays[2] || [];

      return { modified, added, removed };
    } catch (e) {
      console.error('Failed to parse change details:', e);
      return null;
    }
  };

  const formatPromptForDisplay = (prompt: string) => {
    return prompt.replace(/CHANGE_DETAILS_START[\s\S]*?CHANGE_DETAILS_END/, '').trim();
  };

  type BeautifiedSection = {
    heading: string;
    fields: { key: string; value: string }[];
    bullets: string[];
    paragraph?: string;
  };

  type BeautifiedPrompt = {
    subject: string;
    summary: string;
    sections: BeautifiedSection[];
    bullets: string[];
    signoff?: string;
    raw: string;
  };

  const beautifyPrompt = (prompt: string): BeautifiedPrompt => {
    const cleaned = formatPromptForDisplay(prompt);

    let subject = "";
    let body = cleaned;
    const subjectMatch = cleaned.match(/^\s*Subject:\s*([^\n\-]+?)(?=\s+(?:Dear|Hello|Hi|This is|---|Campaign\s+\d|[A-Z][a-z]+,))/);
    if (subjectMatch) {
      subject = subjectMatch[1].trim().replace(/\s+/g, " ");
      body = cleaned.slice(subjectMatch[0].length).trim();
    } else {
      const lineMatch = cleaned.match(/^\s*Subject:\s*(.+?)(?:\n|$)/);
      if (lineMatch) {
        subject = lineMatch[1].trim();
        body = cleaned.slice(lineMatch[0].length).trim();
      }
    }

    body = body.replace(/\s+---\s+/g, "\n\n---\n\n");

    const blocks = body
      .split(/\n\n+|(?:\s*---\s*)/)
      .map((b) => b.trim())
      .filter(Boolean);

    let summary = "";
    const sections: BeautifiedSection[] = [];
    const looseBullets: string[] = [];
    let signoff: string | undefined;

    const headingRegex = /^(Campaign\s+\d+|Record\s+\d+|Item\s+\d+|Additional\s+Context|Context|Notes?|Summary|Details?)\s*[:\-]?\s*/i;

    const splitInlineSections = (text: string): string[] => {
      const parts: string[] = [];
      const re = /(Campaign\s+\d+:|Record\s+\d+:|Item\s+\d+:|Additional\s+Context:|Context:|Summary:|Notes?:|Details?:)/gi;
      let lastIdx = 0;
      let match: RegExpExecArray | null;
      const matches: { idx: number }[] = [];
      while ((match = re.exec(text)) !== null) {
        matches.push({ idx: match.index });
      }
      if (matches.length === 0) return [text];
      if (matches[0].idx > 0) parts.push(text.slice(0, matches[0].idx).trim());
      for (let i = 0; i < matches.length; i++) {
        const start = matches[i].idx;
        const end = i + 1 < matches.length ? matches[i + 1].idx : text.length;
        parts.push(text.slice(start, end).trim());
        lastIdx = end;
      }
      if (lastIdx < text.length) {
        const tail = text.slice(lastIdx).trim();
        if (tail) parts.push(tail);
      }
      return parts.filter(Boolean);
    };

    const expandedBlocks: string[] = [];
    for (const block of blocks) {
      const pieces = splitInlineSections(block);
      expandedBlocks.push(...pieces);
    }

    const parseFieldsAndBullets = (text: string): { fields: { key: string; value: string }[]; bullets: string[]; paragraph: string } => {
      const fields: { key: string; value: string }[] = [];
      const bullets: string[] = [];
      let paragraphParts: string[] = [];

      const segments = text
        .split(/\s+-\s+(?=[A-Z])/g)
        .map((s) => s.trim())
        .filter(Boolean);

      for (const seg of segments) {
        const kv = seg.match(/^([A-Z][A-Za-z0-9 _\/\-\.]{1,40}?):\s*(.+)$/s);
        if (kv) {
          fields.push({ key: kv[1].trim(), value: kv[2].trim().replace(/\s+/g, " ") });
        } else if (/^[A-Z]/.test(seg) && seg.length < 240) {
          bullets.push(seg.replace(/\s+/g, " "));
        } else {
          paragraphParts.push(seg);
        }
      }

      return { fields, bullets, paragraph: paragraphParts.join(" ").trim() };
    };

    for (const block of expandedBlocks) {
      const headMatch = block.match(headingRegex);

      if (/^(Best regards|Regards|Sincerely|Thanks|Thank you)/i.test(block)) {
        signoff = block;
        continue;
      }

      if (headMatch) {
        const heading = headMatch[1].replace(/\s+/g, " ").trim();
        const rest = block.slice(headMatch[0].length).trim();
        const { fields, bullets, paragraph } = parseFieldsAndBullets(rest);
        sections.push({
          heading,
          fields,
          bullets,
          paragraph: paragraph || undefined,
        });
      } else if (/^\s*-\s+/.test(block) || / - [A-Z]/.test(block)) {
        const { fields, bullets, paragraph } = parseFieldsAndBullets(block);
        if (fields.length > 0 || bullets.length > 0) {
          if (!summary && paragraph) summary = paragraph;
          looseBullets.push(...bullets);
          if (fields.length > 0) {
            sections.push({ heading: "Details", fields, bullets: [], paragraph: undefined });
          }
        } else {
          if (!summary) summary = block;
          else looseBullets.push(block);
        }
      } else {
        if (!summary) summary = block;
        else looseBullets.push(block);
      }
    }

    if (summary) summary = summary.replace(/\s+/g, " ").trim();

    return {
      subject,
      summary,
      sections,
      bullets: looseBullets,
      signoff,
      raw: cleaned,
    };
  };

  const truncate = (text: string, max: number) =>
    text.length > max ? text.slice(0, max).trimEnd() + "…" : text;

  const filteredApprovals = approvals.filter(approval => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      approval.approval_prompt.toLowerCase().includes(query) ||
      approval.workflow_id?.toLowerCase().includes(query) ||
      approval.execution_id?.toLowerCase().includes(query) ||
      approval.comment?.toLowerCase().includes(query) ||
      approval.approved_by?.toLowerCase().includes(query)
    );
  });

  const totalPages = Math.ceil(filteredApprovals.length / itemsPerPage);
  const paginatedApprovals = filteredApprovals.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  React.useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, activeTab]);

  return (
    <div className="p-6 h-full overflow-auto">
      <div className="space-y-6 max-w-7xl mx-auto">
        <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-teal-100 via-cyan-100 to-sky-100 dark:from-teal-900/30 dark:via-cyan-900/30 dark:to-sky-900/30 p-8 shadow-lg border border-teal-200 dark:border-teal-800 animate-fade-in-up">
          <div className="absolute inset-0 bg-[url('/grid.svg')] opacity-10"></div>
          <div className="relative z-10">
            <div className="flex items-center gap-3 mb-2">
              <Inbox className="w-10 h-10 text-teal-600 dark:text-teal-400" />
              <h1 className="text-4xl font-bold text-gray-800 dark:text-gray-100 flex items-center gap-2">
                Inbox
                <Sparkles className="w-8 h-8 text-teal-600 dark:text-teal-400 animate-pulse" />
              </h1>
            </div>
            <p className="text-gray-700 dark:text-gray-300 text-lg">Review and respond to workflow approvals</p>
          </div>
          <div className="absolute top-0 right-0 w-64 h-64 bg-teal-200 dark:bg-teal-700 opacity-20 rounded-full -mr-32 -mt-32"></div>
          <div className="absolute bottom-0 left-0 w-48 h-48 bg-cyan-200 dark:bg-cyan-700 opacity-20 rounded-full -ml-24 -mb-24"></div>
        </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="w-full justify-start overflow-x-auto bg-gray-100 dark:bg-gray-900 p-1 rounded-lg h-12">
          <TabsTrigger value="pending" className="relative flex items-center gap-2 text-sm font-semibold">
            Pending
            {allApprovals.filter(a => a.status === "pending").length > 0 && (
              <span className="ml-1 inline-flex items-center justify-center rounded-full bg-gray-500 px-2 py-0.5 text-xs font-semibold text-white">
                {allApprovals.filter(a => a.status === "pending").length}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="approved" className="relative flex items-center gap-2 text-sm font-semibold">
            Approved
            {allApprovals.filter(a => a.status === "approved").length > 0 && (
              <span className="ml-1 inline-flex items-center justify-center rounded-full bg-gray-500 px-2 py-0.5 text-xs font-semibold text-white">
                {allApprovals.filter(a => a.status === "approved").length}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="rejected" className="relative flex items-center gap-2 text-sm font-semibold">
            Rejected
            {allApprovals.filter(a => a.status === "rejected").length > 0 && (
              <span className="ml-1 inline-flex items-center justify-center rounded-full bg-gray-500 px-2 py-0.5 text-xs font-semibold text-white">
                {allApprovals.filter(a => a.status === "rejected").length}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="all" className="relative flex items-center gap-2 text-sm font-semibold">
            All Approvals
            {allApprovals.length > 0 && (
              <span className="ml-1 inline-flex items-center justify-center rounded-full bg-gray-500 px-2 py-0.5 text-xs font-semibold text-white">
                {allApprovals.length}
              </span>
            )}
          </TabsTrigger>
        </TabsList>

        <TabsContent value={activeTab} className="space-y-4 mt-6 animate-fade-in-up animation-delay-200">
          <div className="flex items-center gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search by prompt, workflow, execution, comment..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10 border-gray-300 dark:border-gray-700 focus:ring-2 focus:ring-blue-500"
              />
            </div>
            {searchQuery && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSearchQuery("")}
                className="hover:bg-gray-100 dark:hover:bg-gray-800"
              >
                Clear
              </Button>
            )}
          </div>

          {isLoading ? (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <Card key={i} className="animate-pulse">
                  <CardContent className="p-6 space-y-3">
                    <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-3/4"></div>
                    <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-full"></div>
                    <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/2"></div>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : filteredApprovals.length === 0 ? (
            <Card className="border-dashed border-2 border-gray-300 dark:border-gray-700">
              <CardContent className="flex flex-col items-center justify-center py-16">
                <Inbox className="w-16 h-16 text-gray-400 mb-4" />
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  {searchQuery ? "No approvals match your search" : "No approvals found"}
                </h3>
                <p className="text-gray-500 dark:text-gray-400 text-center max-w-md">
                  {searchQuery ? "Try adjusting your search query" : "You're all caught up! No pending approvals at the moment."}
                </p>
              </CardContent>
            </Card>
          ) : (
            <>
              {paginatedApprovals.map((approval) => {
                const isExpanded = expandedCards.has(approval.id);
                const changeDetails = parseChangeDetails(approval.approval_prompt);
                const beautified = beautifyPrompt(approval.approval_prompt);
                const headerTitle =
                  beautified.subject ||
                  truncate(beautified.summary || beautified.raw, 120) ||
                  "Approval requested";
                const headerPreview = beautified.subject
                  ? truncate(beautified.summary || "", 160)
                  : "";

                return (
                  <Card key={approval.id} className="hover:shadow-lg transition-all duration-300 hover:scale-[1.01] border-gray-200 dark:border-gray-800">
                    <CardHeader className="pb-3 bg-gradient-to-r from-gray-50 via-slate-50 to-gray-50 dark:from-gray-900 dark:via-slate-900 dark:to-gray-900">
                      <div className="flex justify-between items-start gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start gap-2">
                            <div className="flex-1 min-w-0">
                              <CardTitle className="text-base mb-1 font-semibold leading-snug">
                                {headerTitle}
                              </CardTitle>
                              {headerPreview && (
                                <p className="text-sm text-muted-foreground mb-2 line-clamp-2">
                                  {headerPreview}
                                </p>
                              )}
                              <CardDescription className="flex items-center gap-2 text-xs">
                                <Calendar className="h-3 w-3 flex-shrink-0" />
                                {formatDate(approval.created_at)}
                                {approval.timeout_at && approval.status === "pending" && (
                                  <>
                                    <span className="mx-1">•</span>
                                    <Clock className="h-3 w-3 flex-shrink-0" />
                                    {getTimeRemaining(approval.timeout_at)}
                                  </>
                                )}
                                {beautified.sections.length > 0 && (
                                  <>
                                    <span className="mx-1">•</span>
                                    <span>{beautified.sections.length} {beautified.sections.length === 1 ? "section" : "sections"}</span>
                                  </>
                                )}
                              </CardDescription>
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center gap-2 flex-shrink-0">
                          {getStatusBadge(approval.status)}
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => toggleCardExpansion(approval.id)}
                            className="h-8 w-8 p-0 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                          >
                            {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                          </Button>
                        </div>
                      </div>
                    </CardHeader>

                    {isExpanded && (
                      <CardContent className="space-y-4 pt-4">
                        {beautified.summary && (
                          <p className="text-sm text-foreground leading-relaxed">
                            {beautified.summary}
                          </p>
                        )}

                        {beautified.sections.length > 0 && (
                          <div className="grid gap-3 sm:grid-cols-2">
                            {beautified.sections.map((section, sIdx) => (
                              <div
                                key={`${section.heading}-${sIdx}`}
                                className="rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 overflow-hidden"
                              >
                                <div className="px-3 py-2 bg-gradient-to-r from-teal-50 to-cyan-50 dark:from-teal-950/40 dark:to-cyan-950/40 border-b border-gray-200 dark:border-gray-800">
                                  <h4 className="text-sm font-semibold text-teal-800 dark:text-teal-200">
                                    {section.heading}
                                  </h4>
                                </div>
                                <div className="p-3 space-y-2">
                                  {section.paragraph && (
                                    <p className="text-xs text-muted-foreground leading-relaxed">
                                      {section.paragraph}
                                    </p>
                                  )}
                                  {section.fields.length > 0 && (
                                    <dl className="grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1.5 text-xs">
                                      {section.fields.map((f, fIdx) => (
                                        <React.Fragment key={`${f.key}-${fIdx}`}>
                                          <dt className="font-medium text-muted-foreground whitespace-nowrap">
                                            {f.key}
                                          </dt>
                                          <dd className="font-mono text-foreground break-words">
                                            {f.value}
                                          </dd>
                                        </React.Fragment>
                                      ))}
                                    </dl>
                                  )}
                                  {section.bullets.length > 0 && (
                                    <ul className="list-disc list-inside text-xs space-y-1 text-foreground">
                                      {section.bullets.map((b, bIdx) => (
                                        <li key={bIdx}>{b}</li>
                                      ))}
                                    </ul>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}

                        {beautified.bullets.length > 0 && (
                          <div className="rounded-lg border border-gray-200 dark:border-gray-800 bg-muted/30 p-3">
                            <ul className="list-disc list-inside text-sm space-y-1 text-foreground">
                              {beautified.bullets.map((b, bIdx) => (
                                <li key={bIdx}>{b}</li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {beautified.signoff && (
                          <p className="text-xs italic text-muted-foreground border-t border-gray-200 dark:border-gray-800 pt-3">
                            {beautified.signoff}
                          </p>
                        )}

                        {!beautified.subject &&
                          beautified.sections.length === 0 &&
                          beautified.bullets.length === 0 &&
                          !beautified.summary && (
                            <p className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">
                              {beautified.raw}
                            </p>
                          )}

                        {changeDetails && (changeDetails.modified.length > 0 || changeDetails.added.length > 0 || changeDetails.removed.length > 0) && (
                          <div className="border rounded-lg overflow-hidden">
                            {changeDetails.modified.length > 0 && (
                              <div className="mb-4">
                                <div className="bg-yellow-50 dark:bg-yellow-900/20 px-3 py-2 border-b">
                                  <h4 className="text-sm font-semibold text-yellow-800 dark:text-yellow-300">Modified Rows ({changeDetails.modified.length})</h4>
                                </div>
                                <div className="overflow-x-auto">
                                  {changeDetails.modified.map((change: any, idx: number) => {
                                    const allKeys = new Set([...Object.keys(change.before || {}), ...Object.keys(change.after || {})]);
                                    const changedKeys = Array.from(allKeys).filter(key =>
                                      JSON.stringify(change.before?.[key]) !== JSON.stringify(change.after?.[key])
                                    );

                                    return (
                                      <div key={idx} className="border-b last:border-b-0">
                                        <Table>
                                          <TableHeader>
                                            <TableRow className="bg-muted/50">
                                              <TableHead className="w-32 font-semibold">Field</TableHead>
                                              <TableHead className="font-semibold">Before</TableHead>
                                              <TableHead className="font-semibold">After</TableHead>
                                            </TableRow>
                                          </TableHeader>
                                          <TableBody>
                                            {changedKeys.map((key) => (
                                              <TableRow key={key} className="bg-yellow-50/50 dark:bg-yellow-900/10">
                                                <TableCell className="font-medium">{key}</TableCell>
                                                <TableCell className="font-mono text-sm text-red-600 dark:text-red-400">
                                                  {JSON.stringify(change.before?.[key])}
                                                </TableCell>
                                                <TableCell className="font-mono text-sm text-green-600 dark:text-green-400">
                                                  {JSON.stringify(change.after?.[key])}
                                                </TableCell>
                                              </TableRow>
                                            ))}
                                          </TableBody>
                                        </Table>
                                      </div>
                                    );
                                  })}
                                </div>
                              </div>
                            )}

                            {changeDetails.added.length > 0 && (
                              <div className="mb-4">
                                <div className="bg-green-50 dark:bg-green-900/20 px-3 py-2 border-b">
                                  <h4 className="text-sm font-semibold text-green-800 dark:text-green-300">Added Rows ({changeDetails.added.length})</h4>
                                </div>
                                <div className="overflow-x-auto">
                                  <Table>
                                    <TableHeader>
                                      <TableRow className="bg-muted/50">
                                        {Object.keys(changeDetails.added[0] || {}).map((key) => (
                                          <TableHead key={key} className="font-semibold">{key}</TableHead>
                                        ))}
                                      </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                      {changeDetails.added.map((row: any, idx: number) => (
                                        <TableRow key={idx} className="bg-green-50/50 dark:bg-green-900/10">
                                          {Object.keys(changeDetails.added[0]).map((key) => (
                                            <TableCell key={key} className="font-mono text-sm">
                                              {JSON.stringify(row[key])}
                                            </TableCell>
                                          ))}
                                        </TableRow>
                                      ))}
                                    </TableBody>
                                  </Table>
                                </div>
                              </div>
                            )}

                            {changeDetails.removed.length > 0 && (
                              <div className="mb-4">
                                <div className="bg-red-50 dark:bg-red-900/20 px-3 py-2 border-b">
                                  <h4 className="text-sm font-semibold text-red-800 dark:text-red-300">Removed Rows ({changeDetails.removed.length})</h4>
                                </div>
                                <div className="overflow-x-auto">
                                  <Table>
                                    <TableHeader>
                                      <TableRow className="bg-muted/50">
                                        {Object.keys(changeDetails.removed[0] || {}).map((key) => (
                                          <TableHead key={key} className="font-semibold">{key}</TableHead>
                                        ))}
                                      </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                      {changeDetails.removed.map((row: any, idx: number) => (
                                        <TableRow key={idx} className="bg-red-50/50 dark:bg-red-900/10">
                                          {Object.keys(changeDetails.removed[0]).map((key) => (
                                            <TableCell key={key} className="font-mono text-sm">
                                              {JSON.stringify(row[key])}
                                            </TableCell>
                                          ))}
                                        </TableRow>
                                      ))}
                                    </TableBody>
                                  </Table>
                                </div>
                              </div>
                            )}
                          </div>
                        )}

                        <div className="flex gap-4 text-xs bg-muted/50 p-2 rounded">
                          {approval.workflow_id && (
                            <Link
                              to={`/workflows/${approval.workflow_id}`}
                              className="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 hover:underline"
                            >
                              Workflow: {approval.workflow_id.substring(0, 12)}...
                            </Link>
                          )}
                          {!approval.workflow_id && (
                            <span className="text-muted-foreground">Workflow: N/A</span>
                          )}

                          {approval.workflow_id && approval.execution_id && (
                            <Link
                              to={`/workflows/${approval.workflow_id}/executions/${approval.execution_id}`}
                              className="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 hover:underline"
                            >
                              Execution: {approval.execution_id.substring(0, 12)}...
                            </Link>
                          )}
                          {(!approval.workflow_id || !approval.execution_id) && approval.execution_id && (
                            <span className="text-muted-foreground">Execution: {approval.execution_id.substring(0, 12)}...</span>
                          )}
                          {!approval.execution_id && (
                            <span className="text-muted-foreground">Execution: N/A</span>
                          )}
                        </div>

                        {approval.status !== "pending" && (
                          <div className="bg-muted p-3 rounded-md space-y-2 text-sm">
                            {approval.approved_by && (
                              <div className="flex items-center gap-2">
                                <User className="h-3 w-3 flex-shrink-0" />
                                <span>Responded by: {approval.approved_by}</span>
                              </div>
                            )}
                            {approval.comment && (
                              <div>
                                <strong>Comment:</strong> {approval.comment}
                              </div>
                            )}
                            {approval.responded_at && (
                              <div className="text-xs text-muted-foreground">
                                {formatDate(approval.responded_at)}
                              </div>
                            )}
                          </div>
                        )}

                        {approval.status === "pending" && (
                          <div className="flex gap-2">
                            <Dialog>
                              <DialogTrigger asChild>
                                <Button
                                  variant="default"
                                  size="sm"
                                  onClick={() => setSelectedApproval(approval)}
                                >
                                  Respond
                                </Button>
                              </DialogTrigger>
                              <DialogContent className="max-w-2xl">
                                <DialogHeader>
                                  <DialogTitle>Respond to Approval</DialogTitle>
                                  <DialogDescription>
                                    {approval.approval_prompt}
                                </DialogDescription>
                              </DialogHeader>

                              <div className="space-y-4">
                                {Object.keys(approval.input_data).length > 0 && (
                                  <div className="bg-muted p-4 rounded-md">
                                    <Label className="text-sm font-medium">Context Data:</Label>
                                    <pre className="text-xs mt-2 overflow-auto max-h-40">
                                      {JSON.stringify(approval.input_data, null, 2)}
                                    </pre>
                                  </div>
                                )}

                                <div className="space-y-2">
                                  <Label htmlFor="comment">Comment (optional)</Label>
                                  <Textarea
                                    id="comment"
                                    placeholder="Add a comment about your decision..."
                                    value={comment}
                                    onChange={(e) => setComment(e.target.value)}
                                    rows={3}
                                  />
                                </div>
                              </div>

                              <DialogFooter className="gap-2">
                                {approval.approval_options.map((option) => (
                                  <Button
                                    key={option}
                                    variant={option === "approve" ? "default" : "destructive"}
                                    onClick={() => handleRespond(option)}
                                    disabled={respondMutation.isPending}
                                  >
                                    {option === "approve" ? <CheckCircle className="h-4 w-4 mr-2" /> : <XCircle className="h-4 w-4 mr-2" />}
                                    {option.charAt(0).toUpperCase() + option.slice(1)}
                                  </Button>
                                ))}
                              </DialogFooter>
                            </DialogContent>
                          </Dialog>
                        </div>
                      )}
                    </CardContent>
                    )}
                  </Card>
                );
              })}

              {totalPages > 1 && (
                <Card className="mt-4 border-gray-200 dark:border-gray-800 bg-gradient-to-r from-gray-50 via-slate-50 to-gray-50 dark:from-gray-900 dark:via-slate-900 dark:to-gray-900">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="text-sm text-muted-foreground">
                        Showing <span className="font-medium text-foreground">{((currentPage - 1) * itemsPerPage) + 1}</span> to <span className="font-medium text-foreground">{Math.min(currentPage * itemsPerPage, filteredApprovals.length)}</span> of <span className="font-medium text-foreground">{filteredApprovals.length}</span> approvals
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                          disabled={currentPage === 1}
                        >
                          Previous
                        </Button>
                        <div className="flex items-center gap-1">
                          {(() => {
                            const maxVisible = 5;
                            const pages = [];

                            if (totalPages <= maxVisible) {
                              for (let i = 1; i <= totalPages; i++) {
                                pages.push(i);
                              }
                            } else {
                              if (currentPage <= 3) {
                                for (let i = 1; i <= 4; i++) pages.push(i);
                                pages.push(-1);
                                pages.push(totalPages);
                              } else if (currentPage >= totalPages - 2) {
                                pages.push(1);
                                pages.push(-1);
                                for (let i = totalPages - 3; i <= totalPages; i++) pages.push(i);
                              } else {
                                pages.push(1);
                                pages.push(-1);
                                pages.push(currentPage - 1);
                                pages.push(currentPage);
                                pages.push(currentPage + 1);
                                pages.push(-2);
                                pages.push(totalPages);
                              }
                            }

                            return pages.map((page, idx) => {
                              if (page === -1 || page === -2) {
                                return (
                                  <span key={`ellipsis-${idx}`} className="px-2 text-muted-foreground">
                                    ...
                                  </span>
                                );
                              }
                              return (
                                <Button
                                  key={page}
                                  variant={currentPage === page ? "default" : "outline"}
                                  size="sm"
                                  onClick={() => setCurrentPage(page)}
                                  className="w-9 h-9 p-0"
                                >
                                  {page}
                                </Button>
                              );
                            });
                          })()}
                        </div>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                          disabled={currentPage === totalPages}
                        >
                          Next
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </TabsContent>
      </Tabs>
      </div>
    </div>
  );
}
