"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { TagInput } from "@/components/ui/tag-input";

interface UrlFormProps {
  onSubmit: (data: { url: string; title?: string; tags?: string[] }) => Promise<void>;
  isLoading?: boolean;
}

interface FormData {
  url: string;
  title: string;
}

export function UrlForm({ onSubmit, isLoading = false }: UrlFormProps) {
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
        <Label htmlFor="url">
          URL <span className="text-red-500">*</span>
        </Label>
        <Input
          id="url"
          type="url"
          placeholder="https://example.com/article"
          {...register("url", {
            required: "URL is required",
            pattern: {
              value: /^https?:\/\/.+/i,
              message: "Please enter a valid URL",
            },
          })}
          disabled={isLoading}
        />
        {errors.url && <p className="text-sm text-red-500">{errors.url.message}</p>}
      </div>

      <div className="space-y-2">
        <Label htmlFor="title">Title (optional)</Label>
        <Input
          id="title"
          placeholder="Article title (auto-detected if not provided)"
          {...register("title")}
          disabled={isLoading}
        />
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
          Add URL Source
        </Button>
      </div>
    </form>
  );
}
