/**
 * Classification Approval Panel Component
 *
 * Displays pending classifications grouped by confidence for user review.
 * Supports individual and batch approve/reject actions.
 */

'use client';

import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  AlertCircle,
  Check,
  X,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Loader2,
} from 'lucide-react';
import { cn } from '@/lib/utils';

// ============================================================================
// Types
// ============================================================================

interface PendingClassification {
  id: string;
  classification_id: string;
  source_id: string;
  name: string;
  type: string;
  level: number;
  parent_name?: string;
  confidence: number;
  description?: string;
  reason?: string;
  status: 'pending' | 'approved' | 'rejected';
}

interface ClassificationApprovalPanelProps {
  sourceId?: string; // Optional: filter by source
  onApprovalComplete?: () => void;
  onClose?: () => void;
}

// ============================================================================
// API Functions
// ============================================================================

async function fetchPendingClassifications(sourceId?: string) {
  const params = new URLSearchParams();
  if (sourceId) params.append('source_id', sourceId);
  params.append('min_confidence', '0.0');

  const response = await fetch(`/api/graph/classifications/pending?${params}`);
  if (!response.ok) throw new Error('Failed to fetch pending classifications');
  return response.json();
}

async function approveClassification(linkId: string, action: 'approve' | 'reject') {
  const response = await fetch(
    `/api/graph/classifications/approve/${linkId}?action=${action}&user_id=default-user`,
    { method: 'PUT' }
  );
  if (!response.ok) throw new Error(`Failed to ${action} classification`);
  return response.json();
}

async function approveBatch(linkIds: string[], action: 'approve' | 'reject') {
  const response = await fetch(
    `/api/graph/classifications/approve-batch?action=${action}&user_id=default-user`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ classification_link_ids: linkIds }),
    }
  );
  if (!response.ok) throw new Error(`Failed to ${action} batch`);
  return response.json();
}

// ============================================================================
// Component
// ============================================================================

export function ClassificationApprovalPanel({
  sourceId,
  onApprovalComplete,
  onClose,
}: ClassificationApprovalPanelProps) {
  const queryClient = useQueryClient();
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Fetch pending classifications
  const { data, isLoading, error } = useQuery({
    queryKey: ['pending-classifications', sourceId],
    queryFn: () => fetchPendingClassifications(sourceId),
  });

  // Approve mutation
  const approveMutation = useMutation({
    mutationFn: ({ id, action }: { id: string; action: 'approve' | 'reject' }) =>
      approveClassification(id, action),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pending-classifications'] });
      queryClient.invalidateQueries({ queryKey: ['graph-data'] });
      onApprovalComplete?.();
    },
  });

  // Batch approve mutation
  const batchMutation = useMutation({
    mutationFn: ({ ids, action }: { ids: string[]; action: 'approve' | 'reject' }) =>
      approveBatch(ids, action),
    onSuccess: () => {
      setSelectedIds(new Set());
      queryClient.invalidateQueries({ queryKey: ['pending-classifications'] });
      queryClient.invalidateQueries({ queryKey: ['graph-data'] });
      onApprovalComplete?.();
    },
  });

  const handleToggleSelection = (id: string) => {
    const newSelected = new Set(selectedIds);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedIds(newSelected);
  };

  const handleSelectAll = (classifications: PendingClassification[]) => {
    const allIds = classifications.map((c) => c.id);
    setSelectedIds(new Set(allIds));
  };

  const handleApprove = (id: string) => {
    approveMutation.mutate({ id, action: 'approve' });
  };

  const handleReject = (id: string) => {
    approveMutation.mutate({ id, action: 'reject' });
  };

  const handleBatchAction = (action: 'approve' | 'reject') => {
    if (selectedIds.size === 0) return;
    batchMutation.mutate({ ids: Array.from(selectedIds), action });
  };

  if (isLoading) {
    return (
      <Card className="w-full">
        <CardContent className="flex items-center justify-center py-8">
          <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
          <span className="ml-2 text-sm text-gray-500">Loading classifications...</span>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="w-full border-red-200 dark:border-red-800">
        <CardContent className="flex items-center py-4">
          <XCircle className="w-5 h-5 text-red-500 mr-2" />
          <span className="text-sm text-red-600 dark:text-red-400">
            Failed to load classifications
          </span>
        </CardContent>
      </Card>
    );
  }

  const highConf = data?.high_confidence || [];
  const mediumConf = data?.medium_confidence || [];
  const lowConf = data?.low_confidence || [];
  const total = data?.total || 0;

  if (total === 0) {
    return (
      <Card className="w-full">
        <CardContent className="flex flex-col items-center justify-center py-8">
          <CheckCircle2 className="w-12 h-12 text-green-500 mb-2" />
          <p className="text-sm text-gray-600 dark:text-gray-400">
            No pending classifications
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Review Classifications</h3>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {total} pending classification{total !== 1 ? 's' : ''}
          </p>
        </div>
        {onClose && (
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="w-4 h-4" />
          </Button>
        )}
      </div>

      {/* Batch Actions */}
      {selectedIds.size > 0 && (
        <Card className="border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950">
          <CardContent className="flex items-center justify-between py-3">
            <span className="text-sm font-medium">
              {selectedIds.size} selected
            </span>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="default"
                onClick={() => handleBatchAction('approve')}
                disabled={batchMutation.isPending}
              >
                <Check className="w-4 h-4 mr-1" />
                Approve Selected
              </Button>
              <Button
                size="sm"
                variant="destructive"
                onClick={() => handleBatchAction('reject')}
                disabled={batchMutation.isPending}
              >
                <X className="w-4 h-4 mr-1" />
                Reject Selected
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <ScrollArea className="h-[600px]">
        <div className="space-y-4">
          {/* High Confidence */}
          {highConf.length > 0 && (
            <ClassificationSection
              title="High Confidence"
              subtitle="≥ 80% confidence - recommended for approval"
              icon={<CheckCircle2 className="w-5 h-5 text-green-500" />}
              classifications={highConf}
              selectedIds={selectedIds}
              onToggleSelection={handleToggleSelection}
              onSelectAll={handleSelectAll}
              onApprove={handleApprove}
              onReject={handleReject}
              isPending={approveMutation.isPending}
              accentColor="green"
            />
          )}

          {/* Medium Confidence */}
          {mediumConf.length > 0 && (
            <ClassificationSection
              title="Medium Confidence"
              subtitle="50-80% confidence - review recommended"
              icon={<AlertTriangle className="w-5 h-5 text-yellow-500" />}
              classifications={mediumConf}
              selectedIds={selectedIds}
              onToggleSelection={handleToggleSelection}
              onSelectAll={handleSelectAll}
              onApprove={handleApprove}
              onReject={handleReject}
              isPending={approveMutation.isPending}
              accentColor="yellow"
            />
          )}

          {/* Low Confidence */}
          {lowConf.length > 0 && (
            <ClassificationSection
              title="Low Confidence"
              subtitle="< 50% confidence - likely to reject"
              icon={<AlertCircle className="w-5 h-5 text-red-500" />}
              classifications={lowConf}
              selectedIds={selectedIds}
              onToggleSelection={handleToggleSelection}
              onSelectAll={handleSelectAll}
              onApprove={handleApprove}
              onReject={handleReject}
              isPending={approveMutation.isPending}
              accentColor="red"
            />
          )}
        </div>
      </ScrollArea>
    </div>
  );
}

// ============================================================================
// Section Component
// ============================================================================

interface ClassificationSectionProps {
  title: string;
  subtitle: string;
  icon: React.ReactNode;
  classifications: PendingClassification[];
  selectedIds: Set<string>;
  onToggleSelection: (id: string) => void;
  onSelectAll: (classifications: PendingClassification[]) => void;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  isPending: boolean;
  accentColor: 'green' | 'yellow' | 'red';
}

function ClassificationSection({
  title,
  subtitle,
  icon,
  classifications,
  selectedIds,
  onToggleSelection,
  onSelectAll,
  onApprove,
  onReject,
  isPending,
  accentColor,
}: ClassificationSectionProps) {
  const colorClasses = {
    green: {
      border: 'border-green-200 dark:border-green-800',
      bg: 'bg-green-50 dark:bg-green-950',
      badge: 'bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300',
    },
    yellow: {
      border: 'border-yellow-200 dark:border-yellow-800',
      bg: 'bg-yellow-50 dark:bg-yellow-950',
      badge: 'bg-yellow-100 dark:bg-yellow-900 text-yellow-700 dark:text-yellow-300',
    },
    red: {
      border: 'border-red-200 dark:border-red-800',
      bg: 'bg-red-50 dark:bg-red-950',
      badge: 'bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-300',
    },
  };

  const colors = colorClasses[accentColor];

  return (
    <Card className={cn('border-2', colors.border)}>
      <CardHeader className={cn('pb-3', colors.bg)}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {icon}
            <div>
              <CardTitle className="text-base">{title}</CardTitle>
              <CardDescription className="text-xs">{subtitle}</CardDescription>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className={colors.badge}>
              {classifications.length}
            </Badge>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => onSelectAll(classifications)}
            >
              Select All
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-2 pt-4">
        {classifications.map((classification) => (
          <ClassificationItem
            key={classification.id}
            classification={classification}
            isSelected={selectedIds.has(classification.id)}
            onToggleSelection={() => onToggleSelection(classification.id)}
            onApprove={() => onApprove(classification.id)}
            onReject={() => onReject(classification.id)}
            isPending={isPending}
          />
        ))}
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Item Component
// ============================================================================

interface ClassificationItemProps {
  classification: PendingClassification;
  isSelected: boolean;
  onToggleSelection: () => void;
  onApprove: () => void;
  onReject: () => void;
  isPending: boolean;
}

function ClassificationItem({
  classification,
  isSelected,
  onToggleSelection,
  onApprove,
  onReject,
  isPending,
}: ClassificationItemProps) {
  const levelLabels = ['Category', 'Topic/Project', 'Subtopic'];
  const breadcrumb = classification.parent_name
    ? `${classification.parent_name} → ${classification.name}`
    : classification.name;

  return (
    <div className="flex items-start gap-3 p-3 border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-900 transition-colors">
      <Checkbox
        checked={isSelected}
        onCheckedChange={onToggleSelection}
        className="mt-1"
      />
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1">
            <p className="font-medium text-sm">{breadcrumb}</p>
            <div className="flex items-center gap-2 mt-1">
              <Badge variant="outline" className="text-xs">
                Level {classification.level}: {levelLabels[classification.level]}
              </Badge>
              <Badge variant="secondary" className="text-xs">
                {(classification.confidence * 100).toFixed(0)}% confidence
              </Badge>
            </div>
          </div>
          <div className="flex gap-1">
            <Button
              size="sm"
              variant="ghost"
              onClick={onApprove}
              disabled={isPending}
              className="h-8 w-8 p-0 text-green-600 hover:text-green-700 hover:bg-green-50 dark:hover:bg-green-950"
            >
              <Check className="w-4 h-4" />
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={onReject}
              disabled={isPending}
              className="h-8 w-8 p-0 text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950"
            >
              <X className="w-4 h-4" />
            </Button>
          </div>
        </div>
        {classification.description && (
          <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
            {classification.description}
          </p>
        )}
        {classification.reason && (
          <p className="text-xs text-gray-500 dark:text-gray-500 mt-1 italic">
            Reason: {classification.reason}
          </p>
        )}
      </div>
    </div>
  );
}

export default ClassificationApprovalPanel;
