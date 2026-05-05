/**
 * Source Node Component for React Flow
 *
 * Renders source nodes in the knowledge graph with 6 visual variants
 * based on source_type: file, url, text, youtube, hana_table, api.
 */

'use client';

import React, { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Badge } from '@/components/ui/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { FileText, Globe, Video, Database, Plug } from 'lucide-react';
import { cn } from '@/lib/utils';

// ============================================================================
// Types
// ============================================================================

export type SourceType = 'file' | 'url' | 'text' | 'youtube' | 'hana_table' | 'api';

export interface SourceNodeData {
  label: string;
  source_type: SourceType;
  title: string;
  connection_count: number;
  topics?: string[];
  status?: 'active' | 'syncing' | 'error' | 'stale';
  // API-specific
  http_method?: string;
  endpoint?: string;
  // HANA-specific
  table_name?: string;
  schema_name?: string;
}

// ============================================================================
// Configuration
// ============================================================================

const SOURCE_CONFIG: Record<SourceType, {
  color: string;
  bgGradient: string;
  darkBgGradient: string;
  borderColor: string;
  darkBorderColor: string;
  selectedRing: string;
  selectedBorder: string;
  hoverBorder: string;
  handleClass: string;
  icon: React.ElementType;
  typeLabel: string;
}> = {
  file: {
    color: '#3B82F6',
    bgGradient: 'from-blue-50 to-sky-50',
    darkBgGradient: 'dark:from-blue-950 dark:to-sky-950',
    borderColor: 'border-blue-200',
    darkBorderColor: 'dark:border-blue-800',
    selectedRing: 'ring-blue-500/50',
    selectedBorder: 'border-blue-500',
    hoverBorder: 'hover:border-blue-400',
    handleClass: '!bg-blue-500',
    icon: FileText,
    typeLabel: 'File',
  },
  url: {
    color: '#10B981',
    bgGradient: 'from-emerald-50 to-green-50',
    darkBgGradient: 'dark:from-emerald-950 dark:to-green-950',
    borderColor: 'border-emerald-200',
    darkBorderColor: 'dark:border-emerald-800',
    selectedRing: 'ring-emerald-500/50',
    selectedBorder: 'border-emerald-500',
    hoverBorder: 'hover:border-emerald-400',
    handleClass: '!bg-emerald-500',
    icon: Globe,
    typeLabel: 'URL',
  },
  text: {
    color: '#6B7280',
    bgGradient: 'from-gray-50 to-slate-50',
    darkBgGradient: 'dark:from-gray-950 dark:to-slate-950',
    borderColor: 'border-gray-200',
    darkBorderColor: 'dark:border-gray-800',
    selectedRing: 'ring-gray-500/50',
    selectedBorder: 'border-gray-500',
    hoverBorder: 'hover:border-gray-400',
    handleClass: '!bg-gray-500',
    icon: FileText,
    typeLabel: 'Text',
  },
  youtube: {
    color: '#EF4444',
    bgGradient: 'from-red-50 to-rose-50',
    darkBgGradient: 'dark:from-red-950 dark:to-rose-950',
    borderColor: 'border-red-200',
    darkBorderColor: 'dark:border-red-800',
    selectedRing: 'ring-red-500/50',
    selectedBorder: 'border-red-500',
    hoverBorder: 'hover:border-red-400',
    handleClass: '!bg-red-500',
    icon: Video,
    typeLabel: 'YouTube',
  },
  hana_table: {
    color: '#8B5CF6',
    bgGradient: 'from-violet-50 to-purple-50',
    darkBgGradient: 'dark:from-violet-950 dark:to-purple-950',
    borderColor: 'border-violet-200',
    darkBorderColor: 'dark:border-violet-800',
    selectedRing: 'ring-violet-500/50',
    selectedBorder: 'border-violet-500',
    hoverBorder: 'hover:border-violet-400',
    handleClass: '!bg-violet-500',
    icon: Database,
    typeLabel: 'HANA Table',
  },
  api: {
    color: '#F59E0B',
    bgGradient: 'from-amber-50 to-yellow-50',
    darkBgGradient: 'dark:from-amber-950 dark:to-yellow-950',
    borderColor: 'border-amber-200',
    darkBorderColor: 'dark:border-amber-800',
    selectedRing: 'ring-amber-500/50',
    selectedBorder: 'border-amber-500',
    hoverBorder: 'hover:border-amber-400',
    handleClass: '!bg-amber-500',
    icon: Plug,
    typeLabel: 'API',
  },
};

// Handle style consistent with workflow NodeComponents
const handleStyle = {
  width: '10px',
  height: '10px',
  border: '2px solid white',
  boxShadow: '0 1px 4px rgba(0,0,0,0.15)',
};

// ============================================================================
// Helpers
// ============================================================================

function getNodeWidth(connectionCount: number): number {
  if (connectionCount <= 5) return 120;
  if (connectionCount <= 15) return 150;
  if (connectionCount <= 30) return 180;
  return 220;
}

function getStatusColor(status?: SourceNodeData['status']): { dot: string; label: string } | null {
  if (!status) return null;
  switch (status) {
    case 'active':
      return { dot: 'bg-green-500', label: 'Active' };
    case 'syncing':
      return { dot: 'bg-blue-500 animate-pulse', label: 'Syncing' };
    case 'error':
      return { dot: 'bg-red-500', label: 'Error' };
    case 'stale':
      return { dot: 'bg-yellow-500', label: 'Stale' };
    default:
      return null;
  }
}

// ============================================================================
// Standard Node (file, url, text, youtube) - Rounded Rectangle
// ============================================================================

function StandardSourceContent({
  data,
  selected,
  config,
  width,
}: {
  data: SourceNodeData;
  selected: boolean;
  config: typeof SOURCE_CONFIG['file'];
  width: number;
}) {
  const Icon = config.icon;
  const statusInfo = getStatusColor(data.status);
  const displayTopics = data.topics?.slice(0, 3) ?? [];

  return (
    <div
      className={cn(
        'rounded-xl border-2 shadow-lg transition-all duration-300 overflow-hidden animate-in fade-in zoom-in-95',
        `bg-gradient-to-br ${config.bgGradient} ${config.darkBgGradient}`,
        selected
          ? `ring-4 ${config.selectedRing} ${config.selectedBorder} shadow-xl scale-105`
          : `${config.borderColor} ${config.darkBorderColor} ${config.hoverBorder} hover:scale-105 hover:shadow-xl`
      )}
      style={{
        width: `${width}px`,
        animationDelay: `${Math.random() * 0.3}s`,
        animationDuration: '0.5s'
      }}
    >
      {/* Header */}
      <div className="px-3 pt-2.5 pb-1.5">
        <div className="flex items-center gap-2">
          <div
            className="p-1.5 rounded-md text-white shadow-sm shrink-0"
            style={{ backgroundColor: config.color }}
          >
            <Icon className="h-3.5 w-3.5" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-xs font-semibold truncate leading-tight">
              {data.title || data.label}
            </div>
          </div>
        </div>
      </div>

      {/* Info row */}
      <div className="px-3 pb-1.5 flex items-center gap-1.5 flex-wrap">
        <Badge
          variant="outline"
          className="text-[9px] px-1.5 py-0 h-4 leading-none"
          style={{ borderColor: config.color, color: config.color }}
        >
          {config.typeLabel}
        </Badge>
        {data.connection_count > 0 && (
          <span className="text-[9px] text-muted-foreground">
            {data.connection_count} conn.
          </span>
        )}
        {statusInfo && (
          <span className="flex items-center gap-1 text-[9px] text-muted-foreground">
            <span className={cn('w-1.5 h-1.5 rounded-full', statusInfo.dot)} />
            {statusInfo.label}
          </span>
        )}
      </div>

      {/* Topics */}
      {displayTopics.length > 0 && (
        <div className="px-3 pb-2 flex flex-wrap gap-1">
          {displayTopics.map((topic) => (
            <span
              key={topic}
              className="text-[8px] bg-white/60 dark:bg-black/20 px-1.5 py-0.5 rounded-full text-muted-foreground truncate max-w-[80px]"
            >
              {topic}
            </span>
          ))}
          {(data.topics?.length ?? 0) > 3 && (
            <span className="text-[8px] text-muted-foreground">
              +{(data.topics?.length ?? 0) - 3}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Hexagon Node (hana_table) - Hexagonal Shape via clip-path
// ============================================================================

function HexagonSourceContent({
  data,
  selected,
  config,
  width,
}: {
  data: SourceNodeData;
  selected: boolean;
  config: typeof SOURCE_CONFIG['hana_table'];
  width: number;
}) {
  const Icon = config.icon;
  const statusInfo = getStatusColor(data.status);
  const height = width * 0.85;

  return (
    <div className="relative animate-in fade-in zoom-in-95" style={{ width: `${width}px`, height: `${height}px`, animationDelay: `${Math.random() * 0.3}s`, animationDuration: '0.5s' }}>
      {/* Hexagon background */}
      <div
        className={cn(
          'absolute inset-0 transition-all duration-300 hover:scale-110',
          selected ? 'shadow-xl scale-105' : 'shadow-lg'
        )}
        style={{
          clipPath: 'polygon(25% 0%, 75% 0%, 100% 50%, 75% 100%, 25% 100%, 0% 50%)',
          background: selected
            ? `linear-gradient(135deg, rgba(139,92,246,0.2), rgba(167,139,250,0.2))`
            : `linear-gradient(135deg, rgba(139,92,246,0.1), rgba(167,139,250,0.1))`,
          border: 'none',
        }}
      />
      {/* Hexagon border overlay */}
      <svg
        className="absolute inset-0"
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
      >
        <polygon
          points={`${width * 0.25},0 ${width * 0.75},0 ${width},${height * 0.5} ${width * 0.75},${height} ${width * 0.25},${height} 0,${height * 0.5}`}
          fill="none"
          stroke={selected ? config.color : 'rgba(139,92,246,0.3)'}
          strokeWidth={selected ? 3 : 2}
        />
      </svg>
      {selected && (
        <div
          className="absolute -inset-2 rounded-2xl opacity-30"
          style={{
            boxShadow: `0 0 0 4px ${config.color}40`,
          }}
        />
      )}

      {/* Content centered */}
      <div className="absolute inset-0 flex flex-col items-center justify-center px-6 text-center">
        <div
          className="p-1.5 rounded-md text-white shadow-sm mb-1"
          style={{ backgroundColor: config.color }}
        >
          <Icon className="h-3.5 w-3.5" />
        </div>
        <div className="text-[10px] font-semibold truncate w-full leading-tight">
          {data.title || data.label}
        </div>
        {data.table_name && (
          <div className="text-[8px] text-muted-foreground truncate w-full mt-0.5">
            {data.schema_name ? `${data.schema_name}.` : ''}
            {data.table_name}
          </div>
        )}
        <div className="flex items-center gap-1 mt-1">
          <Badge
            variant="outline"
            className="text-[8px] px-1 py-0 h-3.5 leading-none"
            style={{ borderColor: config.color, color: config.color }}
          >
            HANA
          </Badge>
          {statusInfo && (
            <span className={cn('w-1.5 h-1.5 rounded-full', statusInfo.dot)} />
          )}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Diamond Node (api) - Diamond Shape via transform
// ============================================================================

function DiamondSourceContent({
  data,
  selected,
  config,
  width,
}: {
  data: SourceNodeData;
  selected: boolean;
  config: typeof SOURCE_CONFIG['api'];
  width: number;
}) {
  const Icon = config.icon;
  const statusInfo = getStatusColor(data.status);
  // Diamond is a square rotated 45deg; the inscribed content area is smaller
  const diamondSize = width * 0.85;

  return (
    <div className="relative animate-in fade-in zoom-in-95" style={{ width: `${diamondSize}px`, height: `${diamondSize}px`, animationDelay: `${Math.random() * 0.3}s`, animationDuration: '0.5s' }}>
      {/* Diamond shape */}
      <div
        className={cn(
          'absolute inset-0 transform rotate-45 rounded-xl border-2 transition-all duration-300 hover:scale-110',
          `bg-gradient-to-br ${config.bgGradient} ${config.darkBgGradient}`,
          selected
            ? `ring-4 ${config.selectedRing} ${config.selectedBorder} shadow-xl scale-105`
            : `${config.borderColor} ${config.darkBorderColor} ${config.hoverBorder} shadow-lg`
        )}
      />

      {/* Content (counter-rotated) */}
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center px-4">
        <div
          className="p-1.5 rounded-md text-white shadow-sm mb-1"
          style={{ backgroundColor: config.color }}
        >
          <Icon className="h-3.5 w-3.5" />
        </div>
        <div className="text-[10px] font-semibold truncate w-full leading-tight">
          {data.title || data.label}
        </div>
        {data.http_method && data.endpoint && (
          <div className="text-[8px] text-muted-foreground truncate w-full mt-0.5">
            <span className="font-mono font-bold">{data.http_method}</span>{' '}
            {data.endpoint}
          </div>
        )}
        <div className="flex items-center gap-1 mt-1">
          <Badge
            variant="outline"
            className="text-[8px] px-1 py-0 h-3.5 leading-none"
            style={{ borderColor: config.color, color: config.color }}
          >
            API
          </Badge>
          {statusInfo && (
            <span className={cn('w-1.5 h-1.5 rounded-full', statusInfo.dot)} />
          )}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Main SourceNode Component
// ============================================================================

export const SourceNode = memo(function SourceNode({ data, selected }: NodeProps) {
  const nodeData = data as unknown as SourceNodeData;
  const sourceType = nodeData.source_type || 'file';
  const config = SOURCE_CONFIG[sourceType] || SOURCE_CONFIG.file;
  const width = getNodeWidth(nodeData.connection_count || 0);

  const renderContent = () => {
    switch (sourceType) {
      case 'hana_table':
        return (
          <HexagonSourceContent
            data={nodeData}
            selected={!!selected}
            config={config}
            width={width}
          />
        );
      case 'api':
        return (
          <DiamondSourceContent
            data={nodeData}
            selected={!!selected}
            config={config}
            width={width}
          />
        );
      default:
        return (
          <StandardSourceContent
            data={nodeData}
            selected={!!selected}
            config={config}
            width={width}
          />
        );
    }
  };

  // Build tooltip content
  const title = nodeData.title || nodeData.label || 'Untitled';
  const connectionCount = nodeData.connection_count || 0;
  const topicCount = nodeData.topics?.length || 0;

  return (
    <TooltipProvider delayDuration={400}>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className="relative">
            <Handle
              type="target"
              position={Position.Top}
              className={config.handleClass}
              style={handleStyle}
            />

            {renderContent()}

            <Handle
              type="source"
              position={Position.Bottom}
              className={config.handleClass}
              style={handleStyle}
            />
          </div>
        </TooltipTrigger>
        <TooltipContent
          side="bottom"
          className="max-w-[220px] p-2"
          sideOffset={8}
        >
          <div className="space-y-1">
            <p className="text-xs font-semibold leading-tight">{title}</p>
            <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
              <span style={{ color: config.color }}>{config.typeLabel}</span>
              {connectionCount > 0 && (
                <span>{connectionCount} connection{connectionCount !== 1 ? 's' : ''}</span>
              )}
              {topicCount > 0 && (
                <span>{topicCount} topic{topicCount !== 1 ? 's' : ''}</span>
              )}
            </div>
            {nodeData.table_name && (
              <p className="text-[10px] text-muted-foreground font-mono truncate">
                {nodeData.schema_name ? `${nodeData.schema_name}.` : ''}{nodeData.table_name}
              </p>
            )}
            {nodeData.endpoint && (
              <p className="text-[10px] text-muted-foreground font-mono truncate">
                {nodeData.http_method} {nodeData.endpoint}
              </p>
            )}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
});

// ============================================================================
// Node Type Registration
// ============================================================================

export const sourceNodeTypes = {
  source: SourceNode,
};

// Import and register classification node types
import ClassificationNode from './ClassificationNode';

export const allNodeTypes = {
  source: SourceNode,
  category: ClassificationNode,
  topic: ClassificationNode,
  project: ClassificationNode,
  subtopic: ClassificationNode,
};

