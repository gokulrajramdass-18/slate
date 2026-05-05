"use client";

import { useState, useRef } from "react";
import { useForm } from "react-hook-form";
import { Upload, X, FileText, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { TagInput } from "@/components/ui/tag-input";
import { cn } from "@/lib/utils";

interface FileUploadFormProps {
  onSubmit: (data: { file: File; title?: string; tags?: string[] }) => Promise<void>;
  isLoading?: boolean;
}

interface FormData {
  title: string;
}

export function FileUploadForm({ onSubmit, isLoading = false }: FileUploadFormProps) {
  const [file, setFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [tags, setTags] = useState<string[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormData>();

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleFormSubmit = async (data: FormData) => {
    if (!file) return;
    await onSubmit({ file, title: data.title || file.name, tags });
  };

  return (
    <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-6">
      {/* File Drop Zone */}
      <div>
        <Label>File</Label>
        <Card
          className={cn(
            "mt-2 border-2 border-dashed transition-colors",
            dragActive
              ? "border-primary-600 bg-primary-50 dark:bg-primary-950"
              : "border-gray-300 dark:border-gray-700",
            file ? "bg-gray-50 dark:bg-gray-900" : ""
          )}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          <CardContent className="p-8">
            {file ? (
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <FileText className="w-8 h-8 text-primary-600" />
                  <div>
                    <p className="font-medium">{file.name}</p>
                    <p className="text-sm text-gray-500">
                      {(file.size / 1024 / 1024).toFixed(2)} MB
                    </p>
                  </div>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setFile(null)}
                  disabled={isLoading}
                >
                  <X className="w-4 h-4" />
                </Button>
              </div>
            ) : (
              <div className="text-center">
                <Upload className="w-12 h-12 mx-auto mb-4 text-gray-400" />
                <p className="text-lg font-medium mb-2">Drop file here or click to browse</p>
                <p className="text-sm text-gray-500 mb-4">
                  Supports PDF, Word, PowerPoint, Excel, text files
                </p>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isLoading}
                >
                  Choose File
                </Button>
                <input
                  ref={fileInputRef}
                  type="file"
                  className="hidden"
                  onChange={handleFileChange}
                  accept=".pdf,.doc,.docx,.ppt,.pptx,.xlsx,.xls,.txt,.md,.csv,.json,.xml,.log,.py,.js,.java,.cpp,.c,.h,.sql,.html,.css"
                />
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Title */}
      <div className="space-y-2">
        <Label htmlFor="title">Title (optional)</Label>
        <Input
          id="title"
          placeholder={file ? file.name : "Enter a title for this source"}
          {...register("title")}
          disabled={isLoading}
        />
        {errors.title && <p className="text-sm text-red-500">{errors.title.message}</p>}
      </div>

      {/* Tags */}
      <TagInput
        label="Tags (optional)"
        value={tags}
        onChange={setTags}
        placeholder="Type and press Enter to add tags"
        disabled={isLoading}
      />

      {/* Submit */}
      <div className="flex justify-end gap-3">
        <Button type="submit" disabled={!file || isLoading}>
          {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Upload Source
        </Button>
      </div>
    </form>
  );
}
