/**
 * useGraphExport Hook
 *
 * Provides PNG, SVG, and JSON export functionality for the graph canvas.
 * Uses getNodesBounds + getViewportForBounds from React Flow and native
 * browser APIs (Canvas for PNG, DOM serialization for SVG).
 */

'use client';

import { useCallback } from 'react';
import {
  useReactFlow,
  getNodesBounds,
  getViewportForBounds,
} from '@xyflow/react';
import { useSourceGraphStore } from '@/lib/stores/source-graph-store';

// ============================================================================
// Helpers
// ============================================================================

/** Generate a datestamp string for filenames: YYYY-MM-DD */
function datestamp(): string {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

/** Build a filename with the project naming pattern */
function filename(ext: string): string {
  return `open-notebook-graph-${datestamp()}.${ext}`;
}

/** Trigger a browser download for the given blob */
function downloadBlob(blob: Blob, name: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/** Trigger a browser download for a data URL string */
function downloadDataUrl(dataUrl: string, name: string): void {
  const a = document.createElement('a');
  a.href = dataUrl;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

// Image export settings
const IMAGE_WIDTH = 2048;
const IMAGE_HEIGHT = 1536;
const PADDING = 0.2;

// ============================================================================
// Hook
// ============================================================================

export function useGraphExport() {
  const { getNodes } = useReactFlow();

  // --------------------------------------------------------------------------
  // PNG export: renders the .react-flow__viewport element to a canvas
  // --------------------------------------------------------------------------
  const exportPNG = useCallback(async () => {
    const nodes = getNodes();
    if (nodes.length === 0) return;

    const viewportEl = document.querySelector<HTMLElement>(
      '.react-flow__viewport'
    );
    if (!viewportEl) return;

    // Compute bounds and the viewport transform to fit all nodes
    const bounds = getNodesBounds(nodes);
    const viewport = getViewportForBounds(
      bounds,
      IMAGE_WIDTH,
      IMAGE_HEIGHT,
      0.5,
      2,
      PADDING
    );

    // Use the browser's native serialization to create an SVG image source
    const svgEl = viewportEl.closest('.react-flow')?.querySelector('svg.react-flow__edges');
    const nodesContainer = viewportEl;

    // Serialize the entire viewport to an SVG foreignObject
    const serializer = new XMLSerializer();
    const clonedViewport = nodesContainer.cloneNode(true) as HTMLElement;

    // Copy computed styles inline so the clone renders properly
    const stylesheets = Array.from(document.styleSheets);
    let cssText = '';
    for (const sheet of stylesheets) {
      try {
        const rules = sheet.cssRules;
        for (let i = 0; i < rules.length; i++) {
          cssText += rules[i].cssText + '\n';
        }
      } catch {
        // Cross-origin stylesheet, skip
      }
    }

    const svgData = `
      <svg xmlns="http://www.w3.org/2000/svg"
           width="${IMAGE_WIDTH}"
           height="${IMAGE_HEIGHT}">
        <defs>
          <style type="text/css"><![CDATA[${cssText}]]></style>
        </defs>
        <foreignObject
          width="${IMAGE_WIDTH}"
          height="${IMAGE_HEIGHT}">
          <div xmlns="http://www.w3.org/1999/xhtml"
               style="width:${IMAGE_WIDTH}px;height:${IMAGE_HEIGHT}px;overflow:hidden;background:white;">
            <div style="transform: translate(${viewport.x}px, ${viewport.y}px) scale(${viewport.zoom});">
              ${serializer.serializeToString(clonedViewport)}
            </div>
          </div>
        </foreignObject>
      </svg>
    `;

    const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
    const svgUrl = URL.createObjectURL(svgBlob);

    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width = IMAGE_WIDTH;
      canvas.height = IMAGE_HEIGHT;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, IMAGE_WIDTH, IMAGE_HEIGHT);
      ctx.drawImage(img, 0, 0);

      canvas.toBlob(
        (blob) => {
          if (blob) {
            downloadBlob(blob, filename('png'));
          }
          URL.revokeObjectURL(svgUrl);
        },
        'image/png',
        1.0
      );
    };
    img.onerror = () => {
      URL.revokeObjectURL(svgUrl);
    };
    img.src = svgUrl;
  }, [getNodes]);

  // --------------------------------------------------------------------------
  // SVG export: serializes the React Flow SVG edges + nodes as foreignObject
  // --------------------------------------------------------------------------
  const exportSVG = useCallback(() => {
    const nodes = getNodes();
    if (nodes.length === 0) return;

    const viewportEl = document.querySelector<HTMLElement>(
      '.react-flow__viewport'
    );
    if (!viewportEl) return;

    const bounds = getNodesBounds(nodes);
    const viewport = getViewportForBounds(
      bounds,
      IMAGE_WIDTH,
      IMAGE_HEIGHT,
      0.5,
      2,
      PADDING
    );

    // Get the edges SVG layer
    const edgesSvg = document.querySelector<SVGSVGElement>(
      '.react-flow__edges'
    );

    const serializer = new XMLSerializer();
    const clonedViewport = viewportEl.cloneNode(true) as HTMLElement;

    // Inline the styles
    const stylesheets = Array.from(document.styleSheets);
    let cssText = '';
    for (const sheet of stylesheets) {
      try {
        const rules = sheet.cssRules;
        for (let i = 0; i < rules.length; i++) {
          cssText += rules[i].cssText + '\n';
        }
      } catch {
        // Cross-origin stylesheet, skip
      }
    }

    // Build a standalone SVG
    let edgesMarkup = '';
    if (edgesSvg) {
      // Extract the inner contents of the edges SVG (defs + groups)
      edgesMarkup = serializer.serializeToString(edgesSvg);
    }

    const svgData = `<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:xlink="http://www.w3.org/1999/xlink"
     width="${IMAGE_WIDTH}"
     height="${IMAGE_HEIGHT}"
     viewBox="0 0 ${IMAGE_WIDTH} ${IMAGE_HEIGHT}">
  <defs>
    <style type="text/css"><![CDATA[${cssText}]]></style>
  </defs>
  <rect width="100%" height="100%" fill="white" />
  <g transform="translate(${viewport.x}, ${viewport.y}) scale(${viewport.zoom})">
    ${edgesMarkup}
  </g>
  <foreignObject width="${IMAGE_WIDTH}" height="${IMAGE_HEIGHT}">
    <div xmlns="http://www.w3.org/1999/xhtml"
         style="width:${IMAGE_WIDTH}px;height:${IMAGE_HEIGHT}px;overflow:hidden;">
      <div style="transform:translate(${viewport.x}px,${viewport.y}px) scale(${viewport.zoom});">
        ${serializer.serializeToString(clonedViewport)}
      </div>
    </div>
  </foreignObject>
</svg>`;

    const blob = new Blob([svgData], {
      type: 'image/svg+xml;charset=utf-8',
    });
    downloadBlob(blob, filename('svg'));
  }, [getNodes]);

  // --------------------------------------------------------------------------
  // JSON export: dumps nodes, edges, and metadata from the store
  // --------------------------------------------------------------------------
  const exportJSON = useCallback(() => {
    const state = useSourceGraphStore.getState();

    const exportData = {
      exportedAt: new Date().toISOString(),
      metadata: state.metadata,
      layout: state.currentLayout,
      filters: {
        sourceTypes: state.filters.sourceTypes,
        edgeTypes: state.filters.edgeTypes,
        semanticThreshold: state.filters.semanticThreshold,
        showIsolated: state.filters.showIsolated,
      },
      nodes: state.nodes.map((n) => ({
        id: n.id,
        type: n.type,
        position: n.position,
        data: n.data,
      })),
      edges: state.edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        type: e.type,
        data: e.data,
        label: e.label,
      })),
    };

    const json = JSON.stringify(exportData, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    downloadBlob(blob, filename('json'));
  }, []);

  return {
    exportPNG,
    exportSVG,
    exportJSON,
  };
}
