import { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Upload, FileText, File as FileIcon } from "lucide-react";
import { toast } from "sonner";
import { apiClient } from "@/lib/api/client";

interface DocumentUploadDialogProps {
  workspaceId: string;
  onUploadComplete: () => void;
  trigger?: React.ReactNode;
}

export function DocumentUploadDialog({
  workspaceId,
  onUploadComplete,
  trigger
}: DocumentUploadDialogProps) {
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [isUploading, setIsUploading] = useState(false);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      // Validate file type
      const allowedExtensions = ['.pdf', '.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt'];
      const fileExtension = selectedFile.name.substring(selectedFile.name.lastIndexOf('.')).toLowerCase();

      if (!allowedExtensions.includes(fileExtension)) {
        toast.error('Invalid file type. Only PDF, DOCX, XLS, and PPT files are allowed.');
        return;
      }

      setFile(selectedFile);
      // Auto-populate title with filename (without extension)
      if (!title) {
        const nameWithoutExt = selectedFile.name.substring(0, selectedFile.name.lastIndexOf('.'));
        setTitle(nameWithoutExt);
      }
    }
  };

  const handleUpload = async () => {
    if (!file) {
      toast.error("Please select a file");
      return;
    }

    setIsUploading(true);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('notebook_id', workspaceId);
      if (title) formData.append('title', title);
      if (description) formData.append('description', description);

      const { data } = await apiClient.post('/workspace-documents/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      toast.success(`Document "${data.title}" uploaded successfully`);

      // Reset form
      setFile(null);
      setTitle("");
      setDescription("");
      setOpen(false);

      // Trigger refresh
      onUploadComplete();
    } catch (error: any) {
      console.error('Upload failed:', error);
      toast.error(error.response?.data?.detail || "Failed to upload document");
    } finally {
      setIsUploading(false);
    }
  };

  const getFileIcon = () => {
    if (!file) return <FileIcon className="w-12 h-12 text-gray-400" />;

    const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    if (ext === '.pdf') return <FileText className="w-12 h-12 text-red-500" />;
    if (['.docx', '.doc'].includes(ext)) return <FileText className="w-12 h-12 text-blue-500" />;
    if (['.xlsx', '.xls'].includes(ext)) return <FileText className="w-12 h-12 text-green-500" />;
    if (['.pptx', '.ppt'].includes(ext)) return <FileText className="w-12 h-12 text-orange-500" />;

    return <FileText className="w-12 h-12 text-gray-400" />;
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger || (
          <Button size="sm" variant="outline" className="h-8 text-xs">
            <Upload className="w-3.5 h-3.5 mr-1.5" />
            Upload Document
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Upload Document</DialogTitle>
          <p className="text-sm text-muted-foreground mt-1">
            Upload PDF, Word, Excel, or PowerPoint documents to your workspace
          </p>
        </DialogHeader>

        <div className="space-y-6 mt-4">
          {/* File Upload Area */}
          <div className="space-y-3">
            <Label>Select File</Label>
            <div
              className="border-2 border-dashed rounded-lg p-8 text-center hover:border-primary/50 transition-colors cursor-pointer"
              onClick={() => document.getElementById('file-input')?.click()}
            >
              {file ? (
                <div className="space-y-3">
                  {getFileIcon()}
                  <div>
                    <p className="font-medium">{file.name}</p>
                    <p className="text-sm text-muted-foreground">
                      {formatFileSize(file.size)}
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      setFile(null);
                    }}
                  >
                    Remove
                  </Button>
                </div>
              ) : (
                <div className="space-y-3">
                  <Upload className="w-12 h-12 text-gray-400 mx-auto" />
                  <div>
                    <p className="font-medium">Click to upload or drag and drop</p>
                    <p className="text-sm text-muted-foreground">
                      PDF, DOCX, XLS, PPT (max 50MB)
                    </p>
                  </div>
                </div>
              )}
            </div>
            <input
              id="file-input"
              type="file"
              className="hidden"
              accept=".pdf,.docx,.doc,.xlsx,.xls,.pptx,.ppt"
              onChange={handleFileChange}
            />
          </div>

          {/* Title Input */}
          <div className="space-y-2">
            <Label htmlFor="title">
              Title <span className="text-muted-foreground font-normal">(optional)</span>
            </Label>
            <Input
              id="title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Custom title for this document"
              disabled={!file}
            />
            <p className="text-xs text-muted-foreground">
              Leave empty to use the filename
            </p>
          </div>

          {/* Description Input */}
          <div className="space-y-2">
            <Label htmlFor="description">
              Description <span className="text-muted-foreground font-normal">(optional)</span>
            </Label>
            <Textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Add a brief description of this document"
              rows={3}
              disabled={!file}
            />
          </div>

          {/* Action Buttons */}
          <div className="flex justify-end gap-3 pt-4 border-t">
            <Button
              variant="outline"
              onClick={() => {
                setOpen(false);
                setFile(null);
                setTitle("");
                setDescription("");
              }}
              disabled={isUploading}
            >
              Cancel
            </Button>
            <Button
              onClick={handleUpload}
              disabled={!file || isUploading}
            >
              {isUploading ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2" />
                  Uploading...
                </>
              ) : (
                <>
                  <Upload className="w-4 h-4 mr-2" />
                  Upload Document
                </>
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
