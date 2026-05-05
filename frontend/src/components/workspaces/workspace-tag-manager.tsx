/**
 * Workspace Tag Manager Component
 *
 * Allows inline editing of workspace tags for classification and organization
 */

'use client';

import { useState, useRef, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { X, Plus, Tag, Check } from 'lucide-react';
import { toast } from 'sonner';
import { apiClient } from '@/lib/api/client';

interface WorkspaceTagManagerProps {
  workspaceId: string;
  tags: string[];
  onTagsUpdate?: (tags: string[]) => void;
}

// Color palette for tags - vibrant and distinct colors
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

export function WorkspaceTagManager({
  workspaceId,
  tags = [],
  onTagsUpdate,
}: WorkspaceTagManagerProps) {
  const queryClient = useQueryClient();
  const [isEditing, setIsEditing] = useState(false);
  const [newTag, setNewTag] = useState('');
  const [localTags, setLocalTags] = useState<string[]>(tags);
  const inputRef = useRef<HTMLInputElement>(null);

  // Update local tags when props change
  useEffect(() => {
    setLocalTags(tags);
  }, [tags]);

  // Focus input when entering edit mode
  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isEditing]);

  const updateTagsMutation = useMutation({
    mutationFn: async (newTags: string[]) => {
      const response = await apiClient.put(`/workspaces/${workspaceId}`, {
        tags: newTags,
      });
      return response.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['notebook', workspaceId] });
      queryClient.invalidateQueries({ queryKey: ['notebooks'] });
      setLocalTags(data.tags || []);
      if (onTagsUpdate) {
        onTagsUpdate(data.tags || []);
      }
      toast.success('Tags updated');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to update tags');
      // Revert to original tags on error
      setLocalTags(tags);
    },
  });

  const handleAddTag = () => {
    const trimmedTag = newTag.trim();

    if (!trimmedTag) {
      toast.error('Tag cannot be empty');
      return;
    }

    if (trimmedTag.length > 30) {
      toast.error('Tag is too long (max 30 characters)');
      return;
    }

    if (localTags.includes(trimmedTag)) {
      toast.error('Tag already exists');
      setNewTag('');
      return;
    }

    const updatedTags = [...localTags, trimmedTag];
    setLocalTags(updatedTags);
    updateTagsMutation.mutate(updatedTags);
    setNewTag('');
  };

  const handleRemoveTag = (tagToRemove: string) => {
    const updatedTags = localTags.filter((tag) => tag !== tagToRemove);
    setLocalTags(updatedTags);
    updateTagsMutation.mutate(updatedTags);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAddTag();
    } else if (e.key === 'Escape') {
      setIsEditing(false);
      setNewTag('');
    }
  };

  const handleFinishEditing = () => {
    if (newTag.trim()) {
      handleAddTag();
    }
    setIsEditing(false);
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      {/* Existing Tags */}
      {localTags.length > 0 ? (
        localTags.map((tag) => (
          <Badge
            key={tag}
            className={`text-xs px-2.5 py-1 flex items-center gap-1.5 transition-all border ${getTagColor(tag)} ${
              isEditing ? 'hover:opacity-80' : 'hover:shadow-sm'
            }`}
          >
            <Tag className="w-3 h-3" />
            {tag}
            {isEditing && (
              <button
                onClick={() => handleRemoveTag(tag)}
                className="ml-1 hover:bg-black/10 dark:hover:bg-white/10 rounded-full p-0.5 transition-colors"
                disabled={updateTagsMutation.isPending}
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </Badge>
        ))
      ) : (
        !isEditing && (
          <span className="text-xs text-muted-foreground italic">No tags</span>
        )
      )}

      {/* Add Tag Input */}
      {isEditing && (
        <div className="flex items-center gap-1">
          <Input
            ref={inputRef}
            type="text"
            value={newTag}
            onChange={(e) => setNewTag(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Add tag..."
            className="h-7 text-xs w-32 px-2"
            disabled={updateTagsMutation.isPending}
            maxLength={30}
          />
          <Button
            size="sm"
            variant="ghost"
            onClick={handleAddTag}
            disabled={!newTag.trim() || updateTagsMutation.isPending}
            className="h-7 w-7 p-0"
          >
            <Check className="w-3.5 h-3.5" />
          </Button>
        </div>
      )}

      {/* Edit/Done Toggle Button */}
      {isEditing ? (
        <Button
          size="sm"
          variant="outline"
          onClick={handleFinishEditing}
          disabled={updateTagsMutation.isPending}
          className="h-7 text-xs px-2"
        >
          Done
        </Button>
      ) : (
        <Button
          size="sm"
          variant="ghost"
          onClick={() => setIsEditing(true)}
          className="h-7 text-xs px-2 gap-1"
        >
          <Plus className="w-3 h-3" />
          {localTags.length > 0 ? 'Edit Tags' : 'Add Tags'}
        </Button>
      )}
    </div>
  );
}
