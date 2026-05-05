/**
 * Relationship Edge Component for React Flow
 *
 * Custom edge rendering for 6 relationship types in the knowledge graph:
 * semantic, notebook, topic, note_link, hana_schema, api_relation.
 */

'use client';

import React, { memo } from 'react';
import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  type EdgeProps,
} from '@xyflow/react';

// ============================================================================
// Types
// ============================================================================

export type RelationshipType =
  | 'semantic'
  | 'notebook'
  | 'topic'
  | 'note_link'
  | 'hana_schema'
  | 'api_relation'
  | 'classified_as'
  | 'parent_child'
  | 'related';

export type ApiRelationVariant = 'solid' | 'dashed' | 'dotted';

export interface RelationshipEdgeData {
  relationship_type: RelationshipType;
  label?: string;
  strength?: number; // 0-1, used for semantic edges
  // api_relation specific
  api_variant?: ApiRelationVariant;
  // classified_as specific
  status?: 'pending' | 'approved' | 'rejected';
}

// ============================================================================
// Configuration
// ============================================================================

interface EdgeConfig {
  color: string;
  dashArray: string; // SVG stroke-dasharray
  baseWidth: number;
  animated: boolean;
  labelBg: string;
  labelText: string;
}

const EDGE_CONFIG: Record<RelationshipType, EdgeConfig> = {
  semantic: {
    color: '#9333EA',
    dashArray: '', // solid
    baseWidth: 2,
    animated: false,
    labelBg: 'bg-purple-100 dark:bg-purple-900/40',
    labelText: 'text-purple-700 dark:text-purple-300',
  },
  notebook: {
    color: '#3B82F6',
    dashArray: '', // solid
    baseWidth: 2,
    animated: false,
    labelBg: 'bg-blue-100 dark:bg-blue-900/40',
    labelText: 'text-blue-700 dark:text-blue-300',
  },
  topic: {
    color: '#10B981',
    dashArray: '6 4', // dashed
    baseWidth: 1.5,
    animated: false,
    labelBg: 'bg-emerald-100 dark:bg-emerald-900/40',
    labelText: 'text-emerald-700 dark:text-emerald-300',
  },
  note_link: {
    color: '#F59E0B',
    dashArray: '', // solid (animated)
    baseWidth: 2,
    animated: true,
    labelBg: 'bg-amber-100 dark:bg-amber-900/40',
    labelText: 'text-amber-700 dark:text-amber-300',
  },
  hana_schema: {
    color: '#EC4899',
    dashArray: '10 4', // long dash
    baseWidth: 1.5,
    animated: false,
    labelBg: 'bg-pink-100 dark:bg-pink-900/40',
    labelText: 'text-pink-700 dark:text-pink-300',
  },
  api_relation: {
    color: '#14B8A6',
    dashArray: '4 3', // short dash (default)
    baseWidth: 1.5,
    animated: false,
    labelBg: 'bg-teal-100 dark:bg-teal-900/40',
    labelText: 'text-teal-700 dark:text-teal-300',
  },
  classified_as: {
    color: '#10B981', // Green for approved, yellow for pending
    dashArray: '', // solid for approved, dashed for pending
    baseWidth: 1.5,
    animated: false,
    labelBg: 'bg-green-100 dark:bg-green-900/40',
    labelText: 'text-green-700 dark:text-green-300',
  },
  parent_child: {
    color: '#6366F1', // Indigo
    dashArray: '', // solid
    baseWidth: 2.5,
    animated: false,
    labelBg: 'bg-indigo-100 dark:bg-indigo-900/40',
    labelText: 'text-indigo-700 dark:text-indigo-300',
  },
  related: {
    color: '#8B5CF6', // Purple
    dashArray: '5 5', // dashed
    baseWidth: 1,
    animated: false,
    labelBg: 'bg-purple-100 dark:bg-purple-900/40',
    labelText: 'text-purple-700 dark:text-purple-300',
  },
};

// api_relation dash variants
const API_DASH_VARIANTS: Record<ApiRelationVariant, string> = {
  solid: '',
  dashed: '6 4',
  dotted: '2 3',
};

// ============================================================================
// Helpers
// ============================================================================

function getSemanticWidth(strength?: number): number {
  // Map strength (0-1) to width (1-4px)
  if (strength === undefined || strength === null) return 2;
  const clamped = Math.max(0, Math.min(1, strength));
  return 1 + clamped * 3; // 1px at 0, 4px at 1
}

function getSemanticOpacity(strength?: number): number {
  if (strength === undefined || strength === null) return 0.8;
  const clamped = Math.max(0, Math.min(1, strength));
  return 0.4 + clamped * 0.6; // 0.4 at 0, 1.0 at 1
}

// ============================================================================
// RelationshipEdge Component
// ============================================================================

export const RelationshipEdge = memo(function RelationshipEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  markerEnd,
  selected,
}: EdgeProps) {
  const edgeData = (data ?? {}) as unknown as RelationshipEdgeData;
  const relType = edgeData.relationship_type || 'semantic';
  const config = EDGE_CONFIG[relType] || EDGE_CONFIG.semantic;

  // Calculate path
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
  });

  // Determine stroke width
  let strokeWidth = config.baseWidth;
  if (relType === 'semantic') {
    strokeWidth = getSemanticWidth(edgeData.strength);
  }

  // Determine dash array
  let dashArray = config.dashArray;
  if (relType === 'api_relation' && edgeData.api_variant) {
    dashArray = API_DASH_VARIANTS[edgeData.api_variant] ?? config.dashArray;
  }
  // Handle classified_as status-based styling
  if (relType === 'classified_as' && edgeData.status) {
    if (edgeData.status === 'pending') {
      dashArray = '5 5'; // Dashed for pending
    } else if (edgeData.status === 'approved') {
      dashArray = ''; // Solid for approved
    }
    // rejected edges should be filtered out by backend, but just in case:
    if (edgeData.status === 'rejected') {
      return null; // Don't render rejected edges
    }
  }

  // Determine opacity (semantic varies by strength)
  let opacity = 0.6; // Default lower opacity for cleaner look
  if (relType === 'semantic') {
    opacity = getSemanticOpacity(edgeData.strength);
  } else if (relType === 'parent_child') {
    opacity = 0.8; // Hierarchy edges more prominent
  }

  // Selected styling
  const finalWidth = selected ? strokeWidth + 1 : strokeWidth;
  // Handle classified_as color based on status
  let finalColor = config.color;
  if (relType === 'classified_as' && edgeData.status) {
    if (edgeData.status === 'pending') {
      finalColor = '#F59E0B'; // Yellow for pending
    } else if (edgeData.status === 'approved') {
      finalColor = '#10B981'; // Green for approved
    }
  }

  return (
    <>
      {/* Animated glow for note_link */}
      {config.animated && (
        <BaseEdge
          id={`${id}-glow`}
          path={edgePath}
          style={{
            stroke: finalColor,
            strokeWidth: finalWidth + 4,
            opacity: 0.15,
            strokeLinecap: 'round',
          }}
        />
      )}

      {/* Main edge */}
      <BaseEdge
        id={id}
        path={edgePath}
        markerEnd={markerEnd}
        className="animate-edge-draw"
        style={{
          stroke: finalColor,
          strokeWidth: finalWidth,
          strokeDasharray: dashArray || undefined,
          strokeLinecap: 'round',
          opacity,
          transition: 'all 0.3s ease',
          ...(selected ? { filter: `drop-shadow(0 0 6px ${finalColor}80)`, strokeWidth: finalWidth + 1 } : {}),
        }}
      />

      {/* Animated dot for note_link edges */}
      {config.animated && (
        <circle r={3} fill={finalColor}>
          <animateMotion dur="2s" repeatCount="indefinite" path={edgePath} />
        </circle>
      )}

      {/* Edge label - always show for semantic edges with strength */}
      {(edgeData.label || (relType === 'semantic' && edgeData.strength !== undefined)) && (
        <EdgeLabelRenderer>
          <div
            className="nodrag nopan pointer-events-auto"
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            }}
          >
            <div
              className={`
                px-2 py-0.5 rounded-full text-[10px] font-medium
                border border-white/20 shadow-sm
                ${config.labelBg} ${config.labelText}
                ${selected ? 'ring-1 ring-offset-1' : ''}
              `}
              style={selected ? { outlineColor: finalColor } : undefined}
            >
              {relType === 'semantic' && edgeData.strength !== undefined ? (
                <span className="font-semibold">
                  {Math.round(edgeData.strength * 100)}%
                </span>
              ) : (
                edgeData.label
              )}
            </div>
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
});

// ============================================================================
// Edge Type Registration
// ============================================================================

export const relationshipEdgeTypes = {
  relationship: RelationshipEdge,
};
