"use client";

import { useForm } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Loader2 } from "lucide-react";
import type { Notebook, NotebookCreate } from "@/lib/types";

interface NotebookFormProps {
  notebook?: Notebook;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: NotebookCreate) => Promise<void>;
  isLoading?: boolean;
}

interface FormData {
  name: string;
  description: string;
  folder_id?: string;
  goal: string;
}

export function NotebookForm({
  notebook,
  open,
  onOpenChange,
  onSubmit,
  isLoading = false,
}: NotebookFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<FormData>({
    defaultValues: {
      name: notebook?.name || "",
      description: notebook?.description || "",
      folder_id: notebook?.folder_id || "",
      goal: notebook?.goal || "",
    },
  });

  const handleFormSubmit = async (data: FormData) => {
    try {
      await onSubmit(data);
      reset();
      onOpenChange(false);
    } catch (error) {
      // Error handling is done in the parent component
      console.error("Form submission error:", error);
    }
  };

  const handleClose = () => {
    if (!isLoading) {
      reset();
      onOpenChange(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[500px] bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800">
        <DialogHeader>
          <DialogTitle>{notebook ? "Edit Workspace" : "Create New Workspace"}</DialogTitle>
          <DialogDescription>
            {notebook
              ? "Update the details of your workspace."
              : "Create a new workspace to organize your research."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">
              Name <span className="text-red-500">*</span>
            </Label>
            <Input
              id="name"
              placeholder="My Research Project"
              {...register("name", { required: "Name is required" })}
              disabled={isLoading}
            />
            {errors.name && (
              <p className="text-sm text-red-500">{errors.name.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <textarea
              id="description"
              placeholder="Describe what this workspace is about..."
              className="flex min-h-[100px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              {...register("description")}
              disabled={isLoading}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="goal">
              Goal <span className="text-red-500">*</span>
            </Label>
            <textarea
              id="goal"
              placeholder="What do you want to achieve with this workspace?"
              className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              {...register("goal", { required: "Goal is required" })}
              disabled={isLoading}
            />
            {errors.goal && (
              <p className="text-sm text-red-500">{errors.goal.message}</p>
            )}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={handleClose}
              disabled={isLoading}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isLoading}>
              {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {notebook ? "Update" : "Create"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
