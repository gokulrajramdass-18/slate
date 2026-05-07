"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Database, GitBranch, Trash2, Eye, Calendar, HardDrive, Search, FileText, BarChart3 } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useAuthStore } from "@/lib/stores/auth-store";
import { apiClient } from "@/lib/api/client";

interface Snapshot {
  id: string;
  workflow_id: string;
  node_id: string;
  snapshot_date: string;
  snapshot_label: string | null;
  storage_type: string;
  row_count: number;
  total_size_bytes: number;
  context_hash: string;
  created_at: string;
}

interface SnapshotDetail {
  id: string;
  workflow_id: string;
  node_id: string;
  user_id: string;
  snapshot_date: string;
  snapshot_label: string | null;
  storage_type: string;
  row_count: number;
  total_size_bytes: number;
  column_count: number;
  context_hash: string;
  stats_summary: string | null;
  sample_data: string | null;
  created_at: string;
  expires_at: string | null;
}

interface CompareResult {
  status: string;
  strategy: string;
  has_changes: boolean;
  change_percentage: number;
  comparison_time_ms: number;
  snapshot1_date: string;
  snapshot2_date: string;
  delta?: any;
  stats_changes?: any;
}

export default function SnapshotsPage() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const user = useAuthStore((state) => state.user);
  const [selectedSnapshot, setSelectedSnapshot] = useState<Snapshot | null>(null);
  const [snapshotDetails, setSnapshotDetails] = useState<SnapshotDetail | null>(null);
  const [compareDialogOpen, setCompareDialogOpen] = useState(false);
  const [compareSnapshot1, setCompareSnapshot1] = useState("");
  const [compareSnapshot2, setCompareSnapshot2] = useState("");
  const [compareStrategy, setCompareStrategy] = useState("fast");
  const [compareResult, setCompareResult] = useState<CompareResult | null>(null);
  const [workflowFilter, setWorkflowFilter] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState("");

  // Fetch snapshots
  const { data: snapshots = [], isLoading } = useQuery<Snapshot[]>({
    queryKey: ["snapshots", workflowFilter],
    queryFn: async () => {
      const params: any = { limit: 100 };
      if (workflowFilter) params.workflow_id = workflowFilter;

      const response = await apiClient.get('/snapshots', { params });
      return response.data;
    },
    refetchInterval: 10000, // Refresh every 10 seconds
  });

  // Fetch storage statistics
  const { data: storageStats } = useQuery({
    queryKey: ["snapshots-storage-stats"],
    queryFn: async () => {
      const response = await apiClient.get('/snapshots/stats/storage');
      return response.data;
    },
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  // View snapshot details
  const viewDetails = async (snapshot: Snapshot) => {
    try {
      const response = await apiClient.get(`/snapshots/${snapshot.id}`);
      setSnapshotDetails(response.data);
      setSelectedSnapshot(snapshot);
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message || "Failed to fetch snapshot details",
        variant: "destructive",
      });
    }
  };

  // Delete snapshot mutation
  const deleteMutation = useMutation({
    mutationFn: async (snapshotId: string) => {
      await apiClient.delete(`/snapshots/${snapshotId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["snapshots"] });
      queryClient.invalidateQueries({ queryKey: ["snapshots-storage-stats"] });
      toast({
        title: "Success",
        description: "Snapshot deleted successfully",
      });
    },
    onError: (error: any) => {
      toast({
        title: "Error",
        description: error.message || "Failed to delete snapshot",
        variant: "destructive",
      });
    },
  });

  // Compare snapshots mutation
  const compareMutation = useMutation({
    mutationFn: async () => {
      const response = await apiClient.post('/snapshots/compare', {
        snapshot1_id: compareSnapshot1,
        snapshot2_id: compareSnapshot2,
        strategy: compareStrategy,
      });
      return response.data;
    },
    onSuccess: (data) => {
      setCompareResult(data);
      toast({
        title: "Comparison Complete",
        description: `Comparison took ${data.comparison_time_ms.toFixed(2)}ms`,
      });
    },
    onError: (error: any) => {
      toast({
        title: "Comparison Error",
        description: error.message || "Failed to compare snapshots",
        variant: "destructive",
      });
    },
  });

  const handleDelete = (snapshotId: string) => {
    if (confirm("Are you sure you want to delete this snapshot? This action cannot be undone.")) {
      deleteMutation.mutate(snapshotId);
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
  };

  const getStorageTypeColor = (type: string) => {
    switch (type) {
      case "inline": return "bg-green-100 text-green-800";
      case "file": return "bg-blue-100 text-blue-800";
      case "chunked": return "bg-purple-100 text-purple-800";
      default: return "bg-gray-100 text-gray-800";
    }
  };

  // Filter snapshots by search query
  const filteredSnapshots = snapshots.filter(s =>
    s.snapshot_label?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    s.workflow_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
    s.node_id.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <Database className="h-8 w-8" />
            Workflow Snapshots
          </h1>
          <p className="text-muted-foreground mt-1">
            Manage data snapshots from your workflow executions
          </p>
        </div>
        <Button onClick={() => setCompareDialogOpen(true)} disabled={snapshots.length < 2}>
          <GitBranch className="h-4 w-4 mr-2" />
          Compare Snapshots
        </Button>
      </div>

      {/* Storage Statistics */}
      {storageStats && storageStats.by_storage_type && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {storageStats.by_storage_type.map((stat: any) => (
            <Card key={stat.storage_type}>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <HardDrive className="h-4 w-4" />
                  {stat.storage_type.charAt(0).toUpperCase() + stat.storage_type.slice(1)} Storage
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stat.count}</div>
                <p className="text-xs text-muted-foreground">
                  {stat.total_mb.toFixed(2)} MB total ({stat.avg_mb.toFixed(2)} MB avg)
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle>Filter Snapshots</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-4">
            <div className="flex-1">
              <Input
                placeholder="Search by label, workflow ID, or node ID..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full"
              />
            </div>
            <div className="w-64">
              <Input
                placeholder="Filter by workflow ID"
                value={workflowFilter}
                onChange={(e) => setWorkflowFilter(e.target.value)}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Snapshots Table */}
      <Card>
        <CardHeader>
          <CardTitle>Snapshots ({filteredSnapshots.length})</CardTitle>
          <CardDescription>
            Your workflow data snapshots stored with multi-tenant isolation
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto" />
              <p className="mt-4 text-muted-foreground">Loading snapshots...</p>
            </div>
          ) : filteredSnapshots.length === 0 ? (
            <div className="text-center py-8">
              <Database className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-muted-foreground">No snapshots found</p>
              <p className="text-xs text-muted-foreground mt-2">
                Create snapshots by adding SNAPSHOT nodes to your workflows
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Label</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Workflow</TableHead>
                  <TableHead>Node</TableHead>
                  <TableHead>Storage</TableHead>
                  <TableHead>Rows</TableHead>
                  <TableHead>Size</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredSnapshots.map((snapshot) => (
                  <TableRow key={snapshot.id}>
                    <TableCell className="font-medium">
                      {snapshot.snapshot_label || <span className="text-muted-foreground italic">No label</span>}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1 text-sm">
                        <Calendar className="h-3 w-3" />
                        {new Date(snapshot.snapshot_date).toLocaleDateString()}
                      </div>
                    </TableCell>
                    <TableCell className="text-xs font-mono">{snapshot.workflow_id.slice(0, 8)}...</TableCell>
                    <TableCell className="text-xs font-mono">{snapshot.node_id.slice(0, 8)}...</TableCell>
                    <TableCell>
                      <Badge className={getStorageTypeColor(snapshot.storage_type)}>
                        {snapshot.storage_type}
                      </Badge>
                    </TableCell>
                    <TableCell>{snapshot.row_count.toLocaleString()}</TableCell>
                    <TableCell>{formatBytes(snapshot.total_size_bytes)}</TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => viewDetails(snapshot)}
                          title="View Details"
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => handleDelete(snapshot.id)}
                          className="text-destructive hover:text-destructive"
                          title="Delete"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Snapshot Details Dialog */}
      {snapshotDetails && (
        <Dialog open={!!snapshotDetails} onOpenChange={() => setSnapshotDetails(null)}>
          <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Snapshot Details</DialogTitle>
              <DialogDescription>
                {snapshotDetails.snapshot_label || "Unlabeled snapshot"} - {new Date(snapshotDetails.snapshot_date).toLocaleString()}
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm font-medium">Storage Type</p>
                  <Badge className={getStorageTypeColor(snapshotDetails.storage_type)}>
                    {snapshotDetails.storage_type}
                  </Badge>
                </div>
                <div>
                  <p className="text-sm font-medium">Row Count</p>
                  <p className="text-sm text-muted-foreground">{snapshotDetails.row_count.toLocaleString()}</p>
                </div>
                <div>
                  <p className="text-sm font-medium">Column Count</p>
                  <p className="text-sm text-muted-foreground">{snapshotDetails.column_count}</p>
                </div>
                <div>
                  <p className="text-sm font-medium">Size</p>
                  <p className="text-sm text-muted-foreground">{formatBytes(snapshotDetails.total_size_bytes)}</p>
                </div>
                <div>
                  <p className="text-sm font-medium">Created</p>
                  <p className="text-sm text-muted-foreground">{new Date(snapshotDetails.created_at).toLocaleString()}</p>
                </div>
                <div>
                  <p className="text-sm font-medium">Expires</p>
                  <p className="text-sm text-muted-foreground">
                    {snapshotDetails.expires_at ? new Date(snapshotDetails.expires_at).toLocaleString() : "Never"}
                  </p>
                </div>
              </div>

              {snapshotDetails.stats_summary && (
                <div>
                  <p className="text-sm font-medium mb-2 flex items-center gap-2">
                    <BarChart3 className="h-4 w-4" />
                    Statistics Summary
                  </p>
                  <pre className="bg-muted p-3 rounded text-xs overflow-x-auto">
                    {JSON.stringify(JSON.parse(snapshotDetails.stats_summary), null, 2)}
                  </pre>
                </div>
              )}

              {snapshotDetails.sample_data && (
                <div>
                  <p className="text-sm font-medium mb-2 flex items-center gap-2">
                    <FileText className="h-4 w-4" />
                    Sample Data (First 10 rows)
                  </p>
                  <pre className="bg-muted p-3 rounded text-xs overflow-x-auto max-h-64">
                    {JSON.stringify(JSON.parse(snapshotDetails.sample_data), null, 2)}
                  </pre>
                </div>
              )}

              <div>
                <p className="text-sm font-medium">Context Hash</p>
                <p className="text-xs text-muted-foreground font-mono break-all">{snapshotDetails.context_hash}</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Snapshots with the same context hash can be compared
                </p>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      )}

      {/* Compare Dialog */}
      <Dialog open={compareDialogOpen} onOpenChange={setCompareDialogOpen}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>Compare Snapshots</DialogTitle>
            <DialogDescription>
              Select two snapshots with matching context to compare
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">First Snapshot</label>
              <Select value={compareSnapshot1} onValueChange={setCompareSnapshot1}>
                <SelectTrigger>
                  <SelectValue placeholder="Select snapshot..." />
                </SelectTrigger>
                <SelectContent>
                  {snapshots.map(s => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.snapshot_label || "Unlabeled"} - {new Date(s.snapshot_date).toLocaleDateString()} ({s.row_count} rows)
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <label className="text-sm font-medium">Second Snapshot</label>
              <Select value={compareSnapshot2} onValueChange={setCompareSnapshot2}>
                <SelectTrigger>
                  <SelectValue placeholder="Select snapshot..." />
                </SelectTrigger>
                <SelectContent>
                  {snapshots.map(s => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.snapshot_label || "Unlabeled"} - {new Date(s.snapshot_date).toLocaleDateString()} ({s.row_count} rows)
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <label className="text-sm font-medium">Comparison Strategy</label>
              <Select value={compareStrategy} onValueChange={setCompareStrategy}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="fast">Fast (Hash + Stats) - Milliseconds</SelectItem>
                  <SelectItem value="medium">Medium (Sample-based) - Seconds</SelectItem>
                  <SelectItem value="full">Full (Row-by-row) - Minutes</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {compareResult && (
              <Card className={compareResult.has_changes ? "bg-yellow-50" : "bg-green-50"}>
                <CardHeader>
                  <CardTitle className="text-sm">Comparison Result</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  <div className="flex items-center gap-2">
                    <Badge variant={compareResult.has_changes ? "destructive" : "default"}>
                      {compareResult.has_changes ? "Changes Detected" : "No Changes"}
                    </Badge>
                    <span className="text-sm text-muted-foreground">
                      {compareResult.change_percentage.toFixed(2)}% change
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Strategy: {compareResult.strategy} | Time: {compareResult.comparison_time_ms.toFixed(2)}ms
                  </p>
                  {compareResult.stats_changes && (
                    <pre className="bg-white p-2 rounded text-xs overflow-x-auto">
                      {JSON.stringify(compareResult.stats_changes, null, 2)}
                    </pre>
                  )}
                </CardContent>
              </Card>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCompareDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => compareMutation.mutate()}
              disabled={!compareSnapshot1 || !compareSnapshot2 || compareMutation.isPending}
            >
              {compareMutation.isPending ? "Comparing..." : "Compare"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
