import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Folder, Plus, Trash2, Edit2, Tag, Info, HelpCircle, FolderTree, Tags } from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Badge } from "@/components/ui/badge";
import {
  createFolder,
  listFolders,
  deleteFolder,
  createTag,
  listTags,
  deleteTag,
  type Folder as FolderType,
  type Tag as TagType,
} from "@/lib/api/folders";
import { SettingsHeader } from "@/components/settings/settings-header";

export default function SettingsFoldersPage() {
  const [folders, setFolders] = useState<FolderType[]>([]);
  const [tags, setTags] = useState<TagType[]>([]);
  const [showFolderDialog, setShowFolderDialog] = useState(false);
  const [showTagDialog, setShowTagDialog] = useState(false);
  const [folderName, setFolderName] = useState("");
  const [tagName, setTagName] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  // Load folders and tags on mount
  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setIsLoading(true);
      const [foldersData, tagsData] = await Promise.all([
        listFolders(),
        listTags(),
      ]);
      setFolders(foldersData);
      setTags(tagsData);
    } catch (error: any) {
      console.error("Failed to load folders and tags:", error);
      toast.error("Failed to load folders and tags");
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateFolder = async () => {
    if (!folderName.trim()) {
      toast.error("Please enter a folder name");
      return;
    }

    try {
      const newFolder = await createFolder({ name: folderName });
      setFolders([...folders, newFolder]);
      toast.success("Folder created successfully");
      setFolderName("");
      setShowFolderDialog(false);
    } catch (error: any) {
      console.error("Failed to create folder:", error);
      toast.error(error.response?.data?.detail || "Failed to create folder");
    }
  };

  const handleCreateTag = async () => {
    if (!tagName.trim()) {
      toast.error("Please enter a tag name");
      return;
    }

    try {
      const newTag = await createTag({ name: tagName });
      setTags([...tags, newTag]);
      toast.success("Tag created successfully");
      setTagName("");
      setShowTagDialog(false);
    } catch (error: any) {
      console.error("Failed to create tag:", error);
      toast.error(error.response?.data?.detail || "Failed to create tag");
    }
  };

  const handleDeleteFolder = async (folderId: string) => {
    try {
      await deleteFolder(folderId);
      setFolders(folders.filter((f) => f.id !== folderId));
      toast.success("Folder deleted");
    } catch (error: any) {
      console.error("Failed to delete folder:", error);
      toast.error(error.response?.data?.detail || "Failed to delete folder");
    }
  };

  const handleDeleteTag = async (tagId: string) => {
    try {
      await deleteTag(tagId);
      setTags(tags.filter((t) => t.id !== tagId));
      toast.success("Tag deleted");
    } catch (error: any) {
      console.error("Failed to delete tag:", error);
      toast.error(error.response?.data?.detail || "Failed to delete tag");
    }
  };

  return (
    <TooltipProvider>
      <div className="space-y-6">
        <SettingsHeader
          title="Folders & Tags"
          description="Organize your workspaces with folders and tags for better project management"
        />

        {/* Comparison Card - New! */}
        <Card className="border-blue-200 dark:border-blue-900 bg-blue-50/50 dark:bg-blue-950/20">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <Info className="w-4 h-4 text-blue-600" />
              When to use Folders vs Tags?
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid md:grid-cols-2 gap-4">
              {/* Folders Column */}
              <div className="space-y-2 p-3 bg-white dark:bg-gray-900 rounded-lg border">
                <div className="flex items-center gap-2">
                  <FolderTree className="w-4 h-4 text-amber-600" />
                  <h3 className="font-semibold text-sm">📁 Folders</h3>
                </div>
                <p className="text-xs text-gray-600 dark:text-gray-400">
                  <strong>Hierarchical organization</strong> - One workspace = one folder
                </p>
                <div className="space-y-1.5">
                  <p className="text-xs font-medium text-gray-700 dark:text-gray-300">Use for:</p>
                  <ul className="text-xs text-gray-600 dark:text-gray-400 space-y-1 pl-3">
                    <li className="flex items-start gap-1.5">
                      <span className="text-green-600 mt-0.5">✓</span>
                      <span>Client projects (e.g., "ACME Corp", "XYZ Ltd")</span>
                    </li>
                    <li className="flex items-start gap-1.5">
                      <span className="text-green-600 mt-0.5">✓</span>
                      <span>Departments (e.g., "Sales", "Engineering")</span>
                    </li>
                    <li className="flex items-start gap-1.5">
                      <span className="text-green-600 mt-0.5">✓</span>
                      <span>Time periods (e.g., "Q1 2026", "2025")</span>
                    </li>
                    <li className="flex items-start gap-1.5">
                      <span className="text-green-600 mt-0.5">✓</span>
                      <span>Workflows (e.g., "Active", "Archived")</span>
                    </li>
                  </ul>
                </div>
              </div>

              {/* Tags Column */}
              <div className="space-y-2 p-3 bg-white dark:bg-gray-900 rounded-lg border">
                <div className="flex items-center gap-2">
                  <Tags className="w-4 h-4 text-purple-600" />
                  <h3 className="font-semibold text-sm">🏷️ Tags</h3>
                </div>
                <p className="text-xs text-gray-600 dark:text-gray-400">
                  <strong>Flexible categorization</strong> - Multiple tags per workspace
                </p>
                <div className="space-y-1.5">
                  <p className="text-xs font-medium text-gray-700 dark:text-gray-300">Use for:</p>
                  <ul className="text-xs text-gray-600 dark:text-gray-400 space-y-1 pl-3">
                    <li className="flex items-start gap-1.5">
                      <span className="text-green-600 mt-0.5">✓</span>
                      <span>Topics (e.g., "data-analysis", "machine-learning")</span>
                    </li>
                    <li className="flex items-start gap-1.5">
                      <span className="text-green-600 mt-0.5">✓</span>
                      <span>Priority (e.g., "urgent", "low-priority")</span>
                    </li>
                    <li className="flex items-start gap-1.5">
                      <span className="text-green-600 mt-0.5">✓</span>
                      <span>Status (e.g., "in-progress", "review")</span>
                    </li>
                    <li className="flex items-start gap-1.5">
                      <span className="text-green-600 mt-0.5">✓</span>
                      <span>Tools (e.g., "sap-hana", "python", "api")</span>
                    </li>
                  </ul>
                </div>
              </div>
            </div>

            {/* Example */}
            <div className="p-3 bg-white dark:bg-gray-900 rounded-lg border border-green-200 dark:border-green-900">
              <p className="text-xs font-medium text-gray-700 dark:text-gray-300 mb-2 flex items-center gap-1.5">
                <span className="text-green-600">💡</span> Example Workspace:
              </p>
              <div className="flex items-center gap-2 flex-wrap text-xs">
                <span className="text-gray-600 dark:text-gray-400">"Customer Feedback Analysis"</span>
                <span className="text-gray-400">→</span>
                <div className="flex items-center gap-1">
                  <Folder className="w-3 h-3 text-amber-600" />
                  <Badge variant="outline" className="text-xs h-5">Client Projects / ACME Corp</Badge>
                </div>
                <span className="text-gray-400">+</span>
                <div className="flex items-center gap-1">
                  <Tag className="w-3 h-3 text-purple-600" />
                  <Badge className="text-xs h-5 bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300">data-analysis</Badge>
                  <Badge className="text-xs h-5 bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300">urgent</Badge>
                  <Badge className="text-xs h-5 bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300">q1-2026</Badge>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Folders Section */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div className="space-y-1">
              <CardTitle className="flex items-center gap-2">
                <Folder className="w-5 h-5" />
                Folders
                <Tooltip>
                  <TooltipTrigger asChild>
                    <HelpCircle className="w-4 h-4 text-gray-400 cursor-help" />
                  </TooltipTrigger>
                  <TooltipContent className="max-w-xs">
                    <p className="text-xs">
                      Folders provide hierarchical structure like a file system. Each workspace belongs to exactly one folder.
                    </p>
                  </TooltipContent>
                </Tooltip>
              </CardTitle>
              <CardDescription>Create folders to organize workspaces hierarchically</CardDescription>
            </div>
            <Dialog open={showFolderDialog} onOpenChange={setShowFolderDialog}>
              <DialogTrigger asChild>
                <Button size="sm">
                  <Plus className="w-4 h-4 mr-2" />
                  New Folder
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Create Folder</DialogTitle>
                </DialogHeader>
                <div className="space-y-4">
                  <div>
                    <Label>Folder Name</Label>
                    <Input
                      value={folderName}
                      onChange={(e) => setFolderName(e.target.value)}
                      placeholder="e.g., Client Projects, Research, Q1 2026"
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleCreateFolder();
                      }}
                    />
                    <p className="text-xs text-gray-500 mt-1.5">
                      💡 Tip: Use clear, descriptive names like "Client Projects" or "Engineering Team"
                    </p>
                  </div>
                  <div className="flex justify-end gap-2">
                    <Button variant="outline" onClick={() => setShowFolderDialog(false)}>
                      Cancel
                    </Button>
                    <Button onClick={handleCreateFolder}>Create</Button>
                  </div>
                </div>
              </DialogContent>
            </Dialog>
          </CardHeader>
          <CardContent>
            {folders.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <Folder className="w-12 h-12 mx-auto mb-3 text-gray-400" />
                <p className="font-medium mb-1">No folders yet</p>
                <p className="text-sm text-gray-400 mb-4">Create your first folder to organize workspaces</p>
                <div className="text-xs text-left max-w-md mx-auto space-y-1.5 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                  <p className="font-medium text-gray-700 dark:text-gray-300">Example folders you might create:</p>
                  <ul className="space-y-1 pl-3">
                    <li className="text-gray-600 dark:text-gray-400">📁 Client Projects</li>
                    <li className="text-gray-600 dark:text-gray-400">📁 Internal Research</li>
                    <li className="text-gray-600 dark:text-gray-400">📁 Sales Team</li>
                    <li className="text-gray-600 dark:text-gray-400">📁 Product Development</li>
                  </ul>
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                {folders.map((folder) => (
                  <div
                    key={folder.id}
                    className="flex items-center justify-between p-3 border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800"
                  >
                    <div className="flex items-center gap-3">
                      <Folder className="w-4 h-4 text-gray-500" />
                      <div>
                        <p className="font-medium">{folder.name}</p>
                        <p className="text-sm text-gray-500">
                          {folder.notebook_count || 0} workspaces
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button variant="ghost" size="sm">
                        <Edit2 className="w-4 h-4" />
                      </Button>
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button variant="ghost" size="sm">
                            <Trash2 className="w-4 h-4 text-red-600" />
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Delete Folder</AlertDialogTitle>
                            <AlertDialogDescription>
                              Are you sure? Workspaces in this folder will not be deleted, but will become uncategorized.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction onClick={() => handleDeleteFolder(folder.id)}>
                              Delete
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Tags Section */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div className="space-y-1">
              <CardTitle className="flex items-center gap-2">
                <Tag className="w-5 h-5" />
                Tags
                <Tooltip>
                  <TooltipTrigger asChild>
                    <HelpCircle className="w-4 h-4 text-gray-400 cursor-help" />
                  </TooltipTrigger>
                  <TooltipContent className="max-w-xs">
                    <p className="text-xs">
                      Tags allow flexible, multi-dimensional categorization. A workspace can have many tags for cross-functional filtering.
                    </p>
                  </TooltipContent>
                </Tooltip>
              </CardTitle>
              <CardDescription>Manage tags for flexible workspace categorization</CardDescription>
            </div>
            <Dialog open={showTagDialog} onOpenChange={setShowTagDialog}>
              <DialogTrigger asChild>
                <Button size="sm">
                  <Plus className="w-4 h-4 mr-2" />
                  New Tag
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Create Tag</DialogTitle>
                </DialogHeader>
                <div className="space-y-4">
                  <div>
                    <Label>Tag Name</Label>
                    <Input
                      value={tagName}
                      onChange={(e) => setTagName(e.target.value)}
                      placeholder="e.g., urgent, data-analysis, machine-learning"
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleCreateTag();
                      }}
                    />
                    <p className="text-xs text-gray-500 mt-1.5">
                      💡 Tip: Use kebab-case (lowercase with hyphens) for consistency
                    </p>
                  </div>
                  <div className="flex justify-end gap-2">
                    <Button variant="outline" onClick={() => setShowTagDialog(false)}>
                      Cancel
                    </Button>
                    <Button onClick={handleCreateTag}>Create</Button>
                  </div>
                </div>
              </DialogContent>
            </Dialog>
          </CardHeader>
          <CardContent>
            {tags.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <Tag className="w-12 h-12 mx-auto mb-3 text-gray-400" />
                <p className="font-medium mb-1">No tags yet</p>
                <p className="text-sm text-gray-400 mb-4">Create tags to categorize your workspaces</p>
                <div className="text-xs text-left max-w-md mx-auto space-y-1.5 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                  <p className="font-medium text-gray-700 dark:text-gray-300">Example tags you might create:</p>
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    <Badge variant="outline" className="text-xs">urgent</Badge>
                    <Badge variant="outline" className="text-xs">data-analysis</Badge>
                    <Badge variant="outline" className="text-xs">machine-learning</Badge>
                    <Badge variant="outline" className="text-xs">sap-hana</Badge>
                    <Badge variant="outline" className="text-xs">in-progress</Badge>
                    <Badge variant="outline" className="text-xs">q1-2026</Badge>
                    <Badge variant="outline" className="text-xs">research</Badge>
                    <Badge variant="outline" className="text-xs">customer-facing</Badge>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex flex-wrap gap-2">
                {tags.map((tag) => (
                  <div
                    key={tag.id}
                    className="flex items-center gap-2 px-3 py-1 bg-gray-100 dark:bg-gray-800 rounded-full"
                  >
                    <Tag className="w-3 h-3" />
                    <span className="text-sm">{tag.name}</span>
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <button className="text-gray-500 hover:text-red-600">
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>Delete Tag</AlertDialogTitle>
                          <AlertDialogDescription>
                            Are you sure you want to delete this tag? It will be removed from all workspaces that use it.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Cancel</AlertDialogCancel>
                          <AlertDialogAction onClick={() => handleDeleteTag(tag.id)}>
                            Delete
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </TooltipProvider>
  );
}
