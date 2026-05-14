import { GuidedWorkspaceWizard } from '@/components/workspaces/guided-creation/GuidedWorkspaceWizard';

export default function GuidedWorkspaceCreatePage() {
  return (
    <div className="h-full w-full bg-gradient-to-br from-background via-background to-primary/5 overflow-auto">
      <GuidedWorkspaceWizard />
    </div>
  );
}
