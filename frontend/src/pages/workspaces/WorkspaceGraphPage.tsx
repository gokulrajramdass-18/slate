import { useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import { useNotebook } from '@/lib/hooks/use-api';
import { GraphCanvas } from '@/components/graph/GraphCanvas';
import { GraphSidebar } from '@/components/graph/GraphSidebar';
import { NodeDetailsPanel } from '@/components/graph/NodeDetailsPanel';
import { useSourceGraphStore } from '@/lib/stores/source-graph-store';

export default function WorkspaceGraphPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const notebookId = id as string;

  const { data: notebook } = useNotebook(notebookId);

  const loadGraph = useSourceGraphStore((s) => s.loadGraph);
  const selectNode = useSourceGraphStore((s) => s.selectNode);
  const selectedNodeId = useSourceGraphStore((s) => s.selectedNodeId);

  useEffect(() => {
    loadGraph('notebook', notebookId);
  }, [loadGraph, notebookId]);

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] overflow-hidden">
      <div className="flex items-center gap-1 px-4 py-2 border-b border-gray-200 dark:border-gray-800 text-sm text-gray-500 dark:text-gray-400 bg-white dark:bg-gray-950">
        <Link to="/workspaces" className="hover:text-gray-900 dark:hover:text-gray-200 transition-colors">
          Workspaces
        </Link>
        <ChevronRight className="h-3.5 w-3.5" />
        <Link
          to={`/workspaces/${notebookId}`}
          className="hover:text-gray-900 dark:hover:text-gray-200 transition-colors"
        >
          {notebook?.name || 'Loading...'}
        </Link>
        <ChevronRight className="h-3.5 w-3.5" />
        <span className="text-gray-900 dark:text-gray-200 font-medium">
          Knowledge Graph
        </span>
      </div>

      <div className="flex flex-1 overflow-hidden">
        <GraphSidebar />
        <div className="flex-1 relative">
          <GraphCanvas
            notebookId={notebookId}
            draggable
            onSourceSelect={(sourceId) => selectNode(sourceId)}
            onSourceOpen={(sourceId) => navigate(`/sources/${sourceId}`)}
          />
        </div>
        {selectedNodeId && <NodeDetailsPanel />}
      </div>
    </div>
  );
}
