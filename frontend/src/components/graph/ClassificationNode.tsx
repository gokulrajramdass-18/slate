/**
 * Classification Node Component for React Flow
 *
 * Renders classification nodes in the knowledge graph with hierarchical levels.
 * Level 0 (Categories): Rounded squares, green gradient, 48px
 * Level 1 (Topics/Projects): Hexagons, purple gradient, 40px
 * Level 2 (Subtopics): Circles, orange gradient, 32px
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
import { Folder, Lightbulb, Tag, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

// ============================================================================
// Types
// ============================================================================

export type ClassificationType = 'category' | 'topic' | 'project' | 'subtopic';

export interface ClassificationNodeData {
  id: string;
  name: string;
  classification_type: ClassificationType;
  level: 0 | 1 | 2;
  sourceCount: number;
  childCount?: number;
  pendingCount?: number;
  color?: string;
  icon?: string;
  description?: string;
}

// ============================================================================
// Configuration
// ============================================================================

const LEVEL_CONFIG: Record<0 | 1 | 2, {
  size: number;
  bgGradient: string;
  darkBgGradient: string;
  borderColor: string;
  darkBorderColor: string;
  selectedRing: string;
  selectedBorder: string;
  hoverBorder: string;
  handleClass: string;
  shape: 'rounded-square' | 'hexagon' | 'circle';
  defaultIcon: React.ElementType;
}> = {
  0: {
    size: 56,
    bgGradient: 'from-emerald-100/80 to-green-100/80',
    darkBgGradient: 'dark:from-emerald-900/60 dark:to-green-900/60',
    borderColor: 'border-emerald-300/50',
    darkBorderColor: 'dark:border-emerald-700/50',
    selectedRing: 'ring-emerald-400/30',
    selectedBorder: 'border-emerald-400',
    hoverBorder: 'hover:border-emerald-300',
    handleClass: '!bg-emerald-500',
    shape: 'rounded-square',
    defaultIcon: Folder,
  },
  1: {
    size: 48,
    bgGradient: 'from-purple-100/80 to-violet-100/80',
    darkBgGradient: 'dark:from-purple-900/60 dark:to-violet-900/60',
    borderColor: 'border-purple-300/50',
    darkBorderColor: 'dark:border-purple-700/50',
    selectedRing: 'ring-purple-400/30',
    selectedBorder: 'border-purple-400',
    hoverBorder: 'hover:border-purple-300',
    handleClass: '!bg-purple-500',
    shape: 'hexagon',
    defaultIcon: Lightbulb,
  },
  2: {
    size: 40,
    bgGradient: 'from-blue-100/80 to-sky-100/80',
    darkBgGradient: 'dark:from-blue-900/60 dark:to-sky-900/60',
    borderColor: 'border-blue-300/50',
    darkBorderColor: 'dark:border-blue-700/50',
    selectedRing: 'ring-blue-400/30',
    selectedBorder: 'border-blue-400',
    hoverBorder: 'hover:border-blue-300',
    handleClass: '!bg-blue-500',
    shape: 'circle',
    defaultIcon: Tag,
  },
};

// Handle style consistent with SourceNode
const handleStyle = {
  width: '10px',
  height: '10px',
  border: '2px solid white',
  boxShadow: '0 1px 4px rgba(0,0,0,0.15)',
};

// ============================================================================
// Component
// ============================================================================

export const ClassificationNode = memo<NodeProps<any>>(({ data, selected }) => {
  // Ensure level is valid (0, 1, or 2), default to 0 if invalid
  const level: 0 | 1 | 2 = (data.level === 0 || data.level === 1 || data.level === 2) ? data.level : 0;
  const config = LEVEL_CONFIG[level];
  const Icon = config.defaultIcon;

  // Shape classes based on level
  const shapeClasses = {
    'rounded-square': 'rounded-xl',
    'hexagon': 'rounded-lg', // Approximation - true hexagon would need clip-path
    'circle': 'rounded-full',
  };

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            className={cn(
              'relative flex flex-col items-center justify-center transition-all duration-300',
              'bg-gradient-to-br border backdrop-blur-sm',
              config.bgGradient,
              config.darkBgGradient,
              config.borderColor,
              config.darkBorderColor,
              config.hoverBorder,
              shapeClasses[config.shape],
              selected && [config.selectedRing, config.selectedBorder, 'ring-4'],
              'shadow-lg hover:shadow-xl hover:scale-105',
              'cursor-pointer group'
            )}
            style={{
              width: `${config.size}px`,
              height: `${config.size}px`,
            }}
          >
            {/* Handles for connections */}
            <Handle
              type="target"
              position={Position.Top}
              style={handleStyle}
              className={cn('!top-0', config.handleClass)}
            />
            <Handle
              type="source"
              position={Position.Bottom}
              style={handleStyle}
              className={cn('!bottom-0', config.handleClass)}
            />
            <Handle
              type="target"
              position={Position.Left}
              style={handleStyle}
              className={cn('!left-0', config.handleClass)}
            />
            <Handle
              type="source"
              position={Position.Right}
              style={handleStyle}
              className={cn('!right-0', config.handleClass)}
            />

            {/* Icon and label */}
            <div className="flex flex-col items-center justify-center gap-1">
              <Icon className="w-5 h-5 text-gray-700 dark:text-gray-300 group-hover:scale-110 transition-transform" />
              {config.size >= 48 && (
                <span className="text-[10px] font-medium text-gray-700 dark:text-gray-300 max-w-full truncate px-1">
                  {data.name}
                </span>
              )}
            </div>

            {/* Source count badge (bottom-right) */}
            {data.sourceCount > 0 && (
              <Badge
                variant="secondary"
                className="absolute -bottom-1 -right-1 px-1.5 py-0 text-[9px] h-4 font-medium bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 shadow-sm"
              >
                {data.sourceCount}
              </Badge>
            )}

            {/* Child count badge (top-right) */}
            {data.childCount && data.childCount > 0 && (
              <Badge
                variant="outline"
                className="absolute -top-1 -right-1 px-1.5 py-0 text-xs font-medium bg-blue-50 dark:bg-blue-950 border-blue-200 dark:border-blue-800"
              >
                {data.childCount}
              </Badge>
            )}

            {/* Pending approval badge (top-left) */}
            {data.pendingCount && data.pendingCount > 0 && (
              <Badge
                variant="outline"
                className="absolute -top-1 -left-1 px-1.5 py-0 text-xs font-medium bg-yellow-50 dark:bg-yellow-950 border-yellow-400 dark:border-yellow-600 flex items-center gap-0.5"
              >
                <AlertCircle className="w-2.5 h-2.5" />
                {data.pendingCount}
              </Badge>
            )}
          </div>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-xs">
          <div className="space-y-1">
            <p className="font-semibold">{data.name}</p>
            {data.description && (
              <p className="text-xs text-gray-500 dark:text-gray-400">{data.description}</p>
            )}
            <div className="flex items-center gap-2 text-xs">
              <span className="text-gray-500 dark:text-gray-400">
                Level {data.level} • {data.classification_type}
              </span>
            </div>
            <div className="flex items-center gap-3 text-xs pt-1 border-t">
              {data.sourceCount > 0 && (
                <span className="text-gray-600 dark:text-gray-400">
                  {data.sourceCount} source{data.sourceCount !== 1 ? 's' : ''}
                </span>
              )}
              {data.childCount && data.childCount > 0 && (
                <span className="text-gray-600 dark:text-gray-400">
                  {data.childCount} child{data.childCount !== 1 ? 'ren' : ''}
                </span>
              )}
              {data.pendingCount && data.pendingCount > 0 && (
                <span className="text-yellow-600 dark:text-yellow-400 font-medium">
                  {data.pendingCount} pending
                </span>
              )}
            </div>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
});

ClassificationNode.displayName = 'ClassificationNode';

export default ClassificationNode;
