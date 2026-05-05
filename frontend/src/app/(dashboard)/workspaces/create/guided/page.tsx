/**
 * Guided Workspace Creation Page
 *
 * Entry point for the AI-powered guided workspace creation wizard.
 */

import { Metadata } from 'next';
import { GuidedWorkspaceWizard } from '@/components/workspaces/guided-creation/GuidedWorkspaceWizard';

export const metadata: Metadata = {
  title: 'Create Workspace - Guided Setup',
  description: 'AI-powered guided workspace creation wizard',
};

export default function GuidedWorkspaceCreationPage() {
  return (
    <div className="h-full w-full bg-gradient-to-br from-background via-background to-primary/5 overflow-auto">
      <GuidedWorkspaceWizard />
    </div>
  );
}
