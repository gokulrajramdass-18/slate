"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { evaluationApi } from "@/lib/api/evaluations";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Upload, FileText, Loader2, CheckCircle, XCircle } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";

interface DatasetUploadModalProps {
  /** Bind the dataset to a specific agent. Omit to create an unbound dataset
   * (usable from the global Evaluations page against any agent). */
  agentId?: string;
  /** When set, the dataset is created as a workflow eval target. */
  workflowId?: string;
  onClose: () => void;
  onSuccess: () => void;
}

export function DatasetUploadModal({ agentId, workflowId, onClose, onSuccess }: DatasetUploadModalProps) {
  const { toast } = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [scoringMethod, setScoringMethod] = useState("llm_judge");

  const uploadMutation = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error("No file selected");

      const formData = new FormData();
      formData.append("file", file);
      formData.append("name", name || file.name.replace(/\.[^/.]+$/, ""));
      formData.append("description", description);
      if (agentId) formData.append("agent_id", agentId);
      if (workflowId) {
        formData.append("workflow_id", workflowId);
        formData.append("target_type", "workflow");
      }
      formData.append("scoring_method", scoringMethod);
      formData.append("criteria", JSON.stringify(["accuracy", "relevance", "completeness"]));

      return evaluationApi.uploadDataset(formData);
    },
    onSuccess: () => {
      toast({
        title: "Dataset uploaded",
        description: "Your evaluation dataset has been uploaded successfully",
      });
      onSuccess();
    },
    onError: (error: any) => {
      toast({
        title: "Upload failed",
        description: error.message || "Failed to upload dataset",
        variant: "destructive",
      });
    },
  });

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
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  const handleFile = (selectedFile: File) => {
    const validExtensions = [".csv", ".json", ".jsonl"];
    const fileExtension = selectedFile.name.toLowerCase().match(/\.[^/.]+$/)?.[0];

    if (!fileExtension || !validExtensions.includes(fileExtension)) {
      toast({
        title: "Invalid file format",
        description: "Please upload a CSV, JSON, or JSONL file",
        variant: "destructive",
      });
      return;
    }

    setFile(selectedFile);
    if (!name) {
      setName(selectedFile.name.replace(/\.[^/.]+$/, ""));
    }
  };

  const handleUpload = () => {
    if (!file) {
      toast({
        title: "No file selected",
        description: "Please select a file to upload",
        variant: "destructive",
      });
      return;
    }

    uploadMutation.mutate();
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Upload Evaluation Dataset</DialogTitle>
          <DialogDescription>
            Upload a CSV, JSON, or JSONL file with test cases to evaluate your agent
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* File Upload Area */}
          <div>
            <Label>Dataset File</Label>
            <div
              className={`mt-2 border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                dragActive
                  ? "border-primary bg-primary/5"
                  : "border-gray-300 dark:border-gray-700 hover:border-primary/50"
              }`}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
            >
              {file ? (
                <div className="space-y-3">
                  <FileText className="h-12 w-12 mx-auto text-primary" />
                  <div>
                    <p className="font-medium">{file.name}</p>
                    <p className="text-sm text-muted-foreground">
                      {(file.size / 1024).toFixed(2)} KB
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setFile(null)}
                  >
                    Remove
                  </Button>
                </div>
              ) : (
                <>
                  <Upload className="h-12 w-12 mx-auto text-muted-foreground mb-3" />
                  <p className="text-sm text-muted-foreground mb-2">
                    Drag and drop your file here, or
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => document.getElementById("file-input")?.click()}
                  >
                    Browse Files
                  </Button>
                  <input
                    id="file-input"
                    type="file"
                    accept=".csv,.json,.jsonl"
                    className="hidden"
                    onChange={handleFileInput}
                  />
                  <p className="text-xs text-muted-foreground mt-3">
                    Supported formats: CSV, JSON, JSONL
                  </p>
                </>
              )}
            </div>
          </div>

          {/* Dataset Name */}
          <div>
            <Label htmlFor="name">Dataset Name</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., QA Test Cases"
              className="mt-2"
            />
          </div>

          {/* Description */}
          <div>
            <Label htmlFor="description">Description (Optional)</Label>
            <Textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief description of this dataset..."
              rows={2}
              className="mt-2"
            />
          </div>

          {/* Scoring Method */}
          <div>
            <Label htmlFor="scoring">Scoring Method</Label>
            <Select value={scoringMethod} onValueChange={setScoringMethod}>
              <SelectTrigger className="mt-2">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="llm_judge">
                  <div>
                    <div className="font-medium">LLM Judge</div>
                    <div className="text-xs text-muted-foreground">
                      AI evaluates quality across criteria
                    </div>
                  </div>
                </SelectItem>
                <SelectItem value="exact_match">
                  <div>
                    <div className="font-medium">Exact Match</div>
                    <div className="text-xs text-muted-foreground">
                      String comparison for factual answers
                    </div>
                  </div>
                </SelectItem>
                <SelectItem value="semantic_similarity">
                  <div>
                    <div className="font-medium">Semantic Similarity</div>
                    <div className="text-xs text-muted-foreground">
                      Embedding-based similarity
                    </div>
                  </div>
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Format Examples */}
          <div className="p-4 bg-muted rounded-lg">
            <h4 className="font-medium text-sm mb-2">File Format Examples:</h4>
            <div className="space-y-2 text-xs font-mono">
              <div>
                <span className="font-semibold">CSV:</span>
                <pre className="mt-1 p-2 bg-background rounded">
                  input,expected_output,category,tags
                  "What is 2+2?","4",math,"basic"
                </pre>
              </div>
              <div>
                <span className="font-semibold">JSON:</span>
                <pre className="mt-1 p-2 bg-background rounded">
                  {`[{"input": "...", "expected_output": "...", "category": "..."}]`}
                </pre>
              </div>
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={uploadMutation.isPending}>
            Cancel
          </Button>
          <Button onClick={handleUpload} disabled={!file || uploadMutation.isPending}>
            {uploadMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Uploading...
              </>
            ) : (
              <>
                <Upload className="h-4 w-4 mr-2" />
                Upload Dataset
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
