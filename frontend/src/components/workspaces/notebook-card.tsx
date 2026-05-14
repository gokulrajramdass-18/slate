"use client";

import React from "react";
import { Link } from 'react-router-dom';
import { useState } from "react";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Folder, MoreVertical, Edit, Trash2, Eye, Archive, Tag, Sparkles, Copy } from "lucide-react";
import { formatRelativeTime } from "@/lib/utils";
import type { Notebook } from "@/lib/types";
import { DeleteNotebookDialog } from "./delete-notebook-dialog";
import { BookmarkButton } from "@/components/bookmarks/bookmark-button";

// Color palette for tags - same as tag manager
const TAG_COLORS = [
  'bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-800',
  'bg-purple-100 text-purple-700 border-purple-200 dark:bg-purple-900/30 dark:text-purple-300 dark:border-purple-800',
  'bg-green-100 text-green-700 border-green-200 dark:bg-green-900/30 dark:text-green-300 dark:border-green-800',
  'bg-pink-100 text-pink-700 border-pink-200 dark:bg-pink-900/30 dark:text-pink-300 dark:border-pink-800',
  'bg-orange-100 text-orange-700 border-orange-200 dark:bg-orange-900/30 dark:text-orange-300 dark:border-orange-800',
  'bg-teal-100 text-teal-700 border-teal-200 dark:bg-teal-900/30 dark:text-teal-300 dark:border-teal-800',
  'bg-indigo-100 text-indigo-700 border-indigo-200 dark:bg-indigo-900/30 dark:text-indigo-300 dark:border-indigo-800',
  'bg-rose-100 text-rose-700 border-rose-200 dark:bg-rose-900/30 dark:text-rose-300 dark:border-rose-800',
  'bg-cyan-100 text-cyan-700 border-cyan-200 dark:bg-cyan-900/30 dark:text-cyan-300 dark:border-cyan-800',
  'bg-amber-100 text-amber-700 border-amber-200 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-800',
];

// Generate consistent color for a tag based on its name
const getTagColor = (tag: string): string => {
  let hash = 0;
  for (let i = 0; i < tag.length; i++) {
    hash = tag.charCodeAt(i) + ((hash << 5) - hash);
  }
  const index = Math.abs(hash) % TAG_COLORS.length;
  return TAG_COLORS[index];
};

const MemoizedBookmarkButton = React.memo(BookmarkButton);

interface NotebookCardProps {
  notebook: Notebook;
  onEdit?: (notebook: Notebook) => void;
  onDuplicate?: (notebook: Notebook) => void;
  sourceCount?: number;
}

export const NotebookCard = React.memo(function NotebookCard({ notebook, onEdit, onDuplicate, sourceCount = 0 }: NotebookCardProps) {
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);

  return (
    <>
      <Card className="hover:shadow-xl hover:scale-[1.02] transition-all duration-300 cursor-pointer h-full flex flex-col hover:border-purple-500/30">
        <CardHeader className="flex-row items-start justify-between space-y-0 pb-2">
          <div className="flex-1">
            <Link to={`/workspaces/${notebook.id}`}>
              <CardTitle className="flex items-center gap-2 text-xl hover:text-primary-600 transition-colors">
                {notebook.has_plan ? (
                  <div className="p-1.5 rounded-lg bg-gradient-to-br from-purple-100 to-blue-100 dark:from-purple-900/30 dark:to-blue-900/30 transition-transform hover:scale-110">
                    <Sparkles className="w-4 h-4 text-purple-600 dark:text-purple-400" />
                  </div>
                ) : (
                  <Folder className="w-5 h-5 text-primary-600 transition-transform hover:scale-110" />
                )}
                {notebook.name}
              </CardTitle>
            </Link>
            {notebook.has_plan && (
              <Badge variant="secondary" className="mt-2 text-xs bg-gradient-to-r from-purple-100 to-blue-100 dark:from-purple-900/40 dark:to-blue-900/40 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-800 animate-pulse-slow">
                <Sparkles className="w-3 h-3 mr-1" />
                AI-Guided
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-1">
            <MemoizedBookmarkButton
              entityType="notebook"
              entityId={notebook.id}
              isBookmarked={notebook.is_bookmarked}
            />
            <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-8 w-8 transition-all hover:scale-110">
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800 animate-fade-in">
              <DropdownMenuItem asChild className="transition-all hover:scale-[1.02]">
                <Link to={`/workspaces/${notebook.id}`} className="flex items-center cursor-pointer">
                  <Eye className="mr-2 h-4 w-4" />
                  View
                </Link>
              </DropdownMenuItem>
              {onEdit && (
                <DropdownMenuItem onClick={() => onEdit(notebook)} className="transition-all hover:scale-[1.02]">
                  <Edit className="mr-2 h-4 w-4" />
                  Edit
                </DropdownMenuItem>
              )}
              {onDuplicate && (
                <DropdownMenuItem onClick={() => onDuplicate(notebook)} className="transition-all hover:scale-[1.02]">
                  <Copy className="mr-2 h-4 w-4" />
                  Duplicate
                </DropdownMenuItem>
              )}
              <DropdownMenuItem className="transition-all hover:scale-[1.02]">
                <Archive className="mr-2 h-4 w-4" />
                {notebook.archived ? "Unarchive" : "Archive"}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={() => setShowDeleteDialog(true)}
                className="text-red-600 focus:text-red-600"
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          </div>
        </CardHeader>

        <CardContent className="flex-1">
          <Link to={`/workspaces/${notebook.id}`}>
            <CardDescription className="line-clamp-2 min-h-[40px]">
              {notebook.description || "No description provided"}
            </CardDescription>
          </Link>

          {/* Tags */}
          {notebook.tags && notebook.tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-3">
              {notebook.tags.slice(0, 3).map((tag) => (
                <Badge
                  key={tag}
                  className={`text-[10px] px-2 py-0.5 font-medium border ${getTagColor(tag)}`}
                >
                  {tag}
                </Badge>
              ))}
              {notebook.tags.length > 3 && (
                <Badge
                  variant="secondary"
                  className="text-[10px] px-2 py-0.5 font-medium"
                >
                  +{notebook.tags.length - 3}
                </Badge>
              )}
            </div>
          )}
        </CardContent>

        <CardFooter className="flex items-center justify-between text-sm text-gray-500 dark:text-gray-400 border-t pt-4">
          <div className="flex items-center gap-4">
            <Badge variant="secondary" className="text-xs">
              {sourceCount} {sourceCount === 1 ? "source" : "sources"}
            </Badge>
            {notebook.archived && (
              <Badge variant="outline" className="text-xs">
                <Archive className="w-3 h-3 mr-1" />
                Archived
              </Badge>
            )}
          </div>
          <span className="text-xs">Updated {formatRelativeTime(notebook.updated)}</span>
        </CardFooter>
      </Card>

      <DeleteNotebookDialog
        notebook={notebook}
        open={showDeleteDialog}
        onOpenChange={setShowDeleteDialog}
      />
    </>
  );
}, (prevProps, nextProps) => {
  return prevProps.notebook.id === nextProps.notebook.id &&
         prevProps.notebook.updated === nextProps.notebook.updated &&
         prevProps.sourceCount === nextProps.sourceCount;
});
