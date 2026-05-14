/**
 * Draft Workspace Sessions Component
 *
 * Shows in-progress guided workspace creation sessions
 * that the user can resume or delete.
 *
 * Accepts sessions and loading state as props so that
 * data fetching is parallelized at the parent level.
 */

'use client';

import { useState } from 'react';
import { useRouter } from '@/lib/routing/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog';
import { FileEdit, Trash2, Clock, Target } from 'lucide-react';
import { type GuidedSession } from '@/lib/api/guided-workspace';
import { useDeleteDraftSession } from '@/lib/hooks/use-api';
import { toast } from 'sonner';
import { formatDistanceToNow } from 'date-fns';

interface DraftWorkspaceSessionsProps {
  sessions: GuidedSession[];
  isLoading: boolean;
}

export function DraftWorkspaceSessions({ sessions, isLoading }: DraftWorkspaceSessionsProps) {
  const router = useRouter();
  const deleteMutation = useDeleteDraftSession();
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [sessionToDelete, setSessionToDelete] = useState<string | null>(null);

  const handleResume = (sessionId: string) => {
    router.push(`/workspaces/create/guided?session=${sessionId}`);
  };

  const handleDelete = async () => {
    if (!sessionToDelete) return;

    try {
      await deleteMutation.mutateAsync(sessionToDelete);
      toast.success('Draft workspace deleted');
      setDeleteDialogOpen(false);
      setSessionToDelete(null);
    } catch (error) {
      console.error('Failed to delete session:', error);
      toast.error('Failed to delete draft workspace');
    }
  };

  const openDeleteDialog = (sessionId: string) => {
    setSessionToDelete(sessionId);
    setDeleteDialogOpen(true);
  };

  const getStepLabel = (step?: string) => {
    const stepLabels: Record<string, string> = {
      goal_analysis: 'Goal Analysis',
      clarification: 'Clarification',
      resource_discovery: 'Resource Discovery',
      plan_generation: 'Plan Generation',
      workspace_creation: 'Finalize',
    };
    return stepLabels[step || ''] || 'Getting Started';
  };

  if (isLoading) {
    return (
      <Card className="shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-xl">
            <FileEdit className="h-5 w-5" />
            Draft Workspaces
          </CardTitle>
          <CardDescription className="mt-1.5">Resume your in-progress workspace setups</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <div className="text-muted-foreground text-sm">Loading drafts...</div>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!sessions || sessions.length === 0) {
    return null; // Don't show section if no drafts
  }

  return (
    <>
      <Card className="shadow-sm">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2 text-xl">
                <FileEdit className="h-5 w-5" />
                Draft Workspaces
              </CardTitle>
              <CardDescription className="mt-1.5">
                Resume your in-progress workspace setups. Drafts expire after 24 hours.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {sessions.map((session) => (
            <Card
              key={session.id}
              className="border-2 hover:border-primary/50 transition-colors shadow-sm"
            >
              <CardContent className="p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start gap-3 mb-3">
                      <div className="mt-0.5">
                        <Target className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-base line-clamp-2 mb-2">
                          {session.goal}
                        </p>
                        <div className="flex items-center gap-3 flex-wrap">
                          <Badge variant="secondary" className="text-xs font-medium">
                            {getStepLabel(session.current_step)}
                          </Badge>
                          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                            <Clock className="h-3.5 w-3.5" />
                            <span>
                              Updated {formatDistanceToNow(new Date(session.updated))} ago
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <Button
                      onClick={() => handleResume(session.id)}
                      size="default"
                      className="shadow-sm"
                    >
                      Resume
                    </Button>
                    <Button
                      onClick={() => openDeleteDialog(session.id)}
                      size="icon"
                      variant="ghost"
                      className="h-10 w-10"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </CardContent>
      </Card>

      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Draft Workspace?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete this draft workspace session. This action cannot be
              undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setSessionToDelete(null)}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
