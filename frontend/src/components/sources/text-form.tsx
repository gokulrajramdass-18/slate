"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { TagInput } from "@/components/ui/tag-input";

interface TextFormProps {
  onSubmit: (data: { title: string; content: string; tags?: string[] }) => Promise<void>;
  isLoading?: boolean;
}

interface FormData {
  title: string;
  content: string;
}

export function TextForm({ onSubmit, isLoading = false }: TextFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormData>();

  const [tags, setTags] = useState<string[]>([]);

  const handleFormSubmit = async (data: FormData) => {
    await onSubmit({ ...data, tags });
  };

  return (
    <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-6">
      <div className="space-y-2">
        <Label htmlFor="title">
          Title <span className="text-red-500">*</span>
        </Label>
        <Input
          id="title"
          placeholder="My text note"
          {...register("title", { required: "Title is required" })}
          disabled={isLoading}
        />
        {errors.title && <p className="text-sm text-red-500">{errors.title.message}</p>}
      </div>

      <div className="space-y-2">
        <Label htmlFor="content">
          Content <span className="text-red-500">*</span>
        </Label>
        <textarea
          id="content"
          placeholder="Enter or paste your text here..."
          className="flex min-h-[300px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
          {...register("content", { required: "Content is required" })}
          disabled={isLoading}
        />
        {errors.content && <p className="text-sm text-red-500">{errors.content.message}</p>}
      </div>

      <TagInput
        label="Tags (optional)"
        value={tags}
        onChange={setTags}
        placeholder="Type and press Enter to add tags"
        disabled={isLoading}
      />

      <div className="flex justify-end gap-3">
        <Button type="submit" disabled={isLoading}>
          {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Add Text Source
        </Button>
      </div>
    </form>
  );
}
