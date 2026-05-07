"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Clock, CheckCircle, XCircle, AlertCircle, User, Calendar, Play, Eye, Workflow as WorkflowIcon, ChevronDown, ChevronUp, Search } from "lucide-react";
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

  // Fetch approvals
  const { data: approvals = [], isLoading } = useQuery<Approval[]>({
    queryKey: ["approvals", activeTab, userId],
    queryFn: () => workflowApprovalsApi.getInbox(activeTab !== "all" && activeTab !== "workflows" ? activeTab : undefined) as unknown as Promise<Approval[]>,
    refetchInterval: 5000, // Refresh every 5 seconds
    enabled: activeTab !== "workflows",
  });

  // Fetch all approvals for tab counts
  const { data: allApprovals = [] } = useQuery<Approval[]>({
    queryKey: ["approvals-all", userId],
    queryFn: () => workflowApprovalsApi.getInbox() as unknown as Promise<Approval[]>,
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  // Fetch workflow executions
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

  // Fetch execution details
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

  // Respond to approval mutation
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

  // Parse change details from approval prompt
  const parseChangeDetails = (prompt: string) => {
    try {
      const match = prompt.match(/CHANGE_DETAILS_START\s*([\s\S]*?)\s*CHANGE_DETAILS_END/);
      if (!match) return null;

      const detailsText = match[1].trim();

      // Split by empty arrays or JSON arrays
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

      // First array is modified, second is added, third is removed
      const modified = jsonArrays[0] || [];
      const added = jsonArrays[1] || [];
      const removed = jsonArrays[2] || [];

      console.log('Parsed change details:', { modified, added, removed });

      return { modified, added, removed };
    } catch (e) {
      console.error('Failed to parse change details:', e);
      return null;
    }
  };

  // Format prompt for display (remove internal markers)
  const formatPromptForDisplay = (prompt: string) => {
    return prompt.replace(/CHANGE_DETAILS_START[\s\S]*?CHANGE_DETAILS_END/, '').trim();
  };

  // Filter approvals based on search query
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

  // Paginate filtered approvals
  const totalPages = Math.ceil(filteredApprovals.length / itemsPerPage);
  const paginatedApprovals = filteredApprovals.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  // Reset to page 1 when search query or tab changes
  React.useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, activeTab]);

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-4xl font-bold tracking-tight bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 bg-clip-text text-transparent">Inbox</h1>
          <p className="text-muted-foreground mt-2 text-base">Review and respond to workflow approvals</p>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="pending" className="relative">
            Pending
            {allApprovals.filter(a => a.status === "pending").length > 0 && (
              <span className="ml-2 inline-flex items-center justify-center rounded-full bg-red-500 px-2 py-0.5 text-xs font-semibold text-white">
                {allApprovals.filter(a => a.status === "pending").length}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="approved" className="relative">
            Approved
            {allApprovals.filter(a => a.status === "approved").length > 0 && (
              <span className="ml-2 inline-flex items-center justify-center rounded-full bg-green-500 px-2 py-0.5 text-xs font-semibold text-white">
                {allApprovals.filter(a => a.status === "approved").length}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="rejected" className="relative">
            Rejected
            {allApprovals.filter(a => a.status === "rejected").length > 0 && (
              <span className="ml-2 inline-flex items-center justify-center rounded-full bg-gray-500 px-2 py-0.5 text-xs font-semibold text-white">
                {allApprovals.filter(a => a.status === "rejected").length}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="all" className="relative">
            All Approvals
            {allApprovals.length > 0 && (
              <span className="ml-2 inline-flex items-center justify-center rounded-full bg-blue-500 px-2 py-0.5 text-xs font-semibold text-white">
                {allApprovals.length}
              </span>
            )}
          </TabsTrigger>
        </TabsList>

        <TabsContent value={activeTab} className="space-y-4 mt-6">
          {/* Search Bar */}
          <div className="flex items-center gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search by prompt, workflow, execution, comment..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>
            {searchQuery && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSearchQuery("")}
              >
                Clear
              </Button>
            )}
          </div>

          {isLoading ? (
            <Card>
              <CardContent className="p-6">
                <p className="text-center text-muted-foreground">Loading approvals...</p>
              </CardContent>
            </Card>
          ) : filteredApprovals.length === 0 ? (
            <Card>
              <CardContent className="p-6">
                <p className="text-center text-muted-foreground">
                  {searchQuery ? "No approvals match your search" : "No approvals found"}
                </p>
              </CardContent>
            </Card>
          ) : (
            <>
              {paginatedApprovals.map((approval) => {
                const isExpanded = expandedCards.has(approval.id);
                const changeDetails = parseChangeDetails(approval.approval_prompt);
                const displayPrompt = formatPromptForDisplay(approval.approval_prompt);

                return (
                  <Card key={approval.id} className="hover:shadow-md transition-shadow">
                    <CardHeader className="pb-3">
                      <div className="flex justify-between items-start gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start gap-2">
                            <div className="flex-1 min-w-0">
                              <CardTitle className="text-base mb-1">{displayPrompt}</CardTitle>
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
                            className="h-8 w-8 p-0"
                          >
                            {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                          </Button>
                        </div>
                      </div>
                    </CardHeader>

                    {isExpanded && (
                      <CardContent className="space-y-3 pt-0">
                        {/* Change Details Table */}
                        {changeDetails && (changeDetails.modified.length > 0 || changeDetails.added.length > 0 || changeDetails.removed.length > 0) && (
                          <div className="border rounded-lg overflow-hidden">
                            {/* Modified Rows */}
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

                            {/* Added Rows */}
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

                            {/* Removed Rows */}
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

                        {/* Workflow info */}
                        <div className="flex gap-4 text-xs bg-muted/50 p-2 rounded">
                          {approval.workflow_id && (
                            <Link
                              href={`/workflows/${approval.workflow_id}`}
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
                              href={`/workflows/${approval.workflow_id}/executions/${approval.execution_id}`}
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

                        {/* Response info (if already responded) */}
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

                        {/* Actions (for pending approvals) */}
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
                                {/* Input data preview */}
                                {Object.keys(approval.input_data).length > 0 && (
                                  <div className="bg-muted p-4 rounded-md">
                                    <Label className="text-sm font-medium">Context Data:</Label>
                                    <pre className="text-xs mt-2 overflow-auto max-h-40">
                                      {JSON.stringify(approval.input_data, null, 2)}
                                    </pre>
                                  </div>
                                )}

                                {/* Comment input */}
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

              {/* Pagination */}
              {totalPages > 1 && (
                <Card className="mt-4">
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
                              // Show all pages
                              for (let i = 1; i <= totalPages; i++) {
                                pages.push(i);
                              }
                            } else {
                              // Show first, last, and pages around current
                              if (currentPage <= 3) {
                                // Near start
                                for (let i = 1; i <= 4; i++) pages.push(i);
                                pages.push(-1); // ellipsis
                                pages.push(totalPages);
                              } else if (currentPage >= totalPages - 2) {
                                // Near end
                                pages.push(1);
                                pages.push(-1); // ellipsis
                                for (let i = totalPages - 3; i <= totalPages; i++) pages.push(i);
                              } else {
                                // Middle
                                pages.push(1);
                                pages.push(-1); // ellipsis
                                pages.push(currentPage - 1);
                                pages.push(currentPage);
                                pages.push(currentPage + 1);
                                pages.push(-2); // ellipsis
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
  );
}
