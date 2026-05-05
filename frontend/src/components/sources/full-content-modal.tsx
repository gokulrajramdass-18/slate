"use client";

import { useState } from "react";
import { Copy, Download, Check } from "lucide-react";
import type { Source } from "@/lib/types";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";

interface FullContentModalProps {
  source: Source;
  trigger: React.ReactNode;
}

export function FullContentModal({ source, trigger }: FullContentModalProps) {
  const [copied, setCopied] = useState(false);

  const contentLength = source.full_text?.length || 0;
  const wordCount = source.full_text?.split(/\s+/).filter(Boolean).length || 0;

  const handleCopy = async () => {
    if (!source.full_text) return;

    try {
      await navigator.clipboard.writeText(source.full_text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error('Failed to copy:', error);
    }
  };

  const handleDownload = () => {
    if (!source.full_text) return;

    const blob = new Blob([source.full_text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${source.title.replace(/[^a-z0-9]/gi, '_').toLowerCase()}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <Dialog>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-w-4xl h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Full Content: {source.title}</DialogTitle>
          <DialogDescription>
            {contentLength.toLocaleString()} characters • {wordCount.toLocaleString()} words
          </DialogDescription>
        </DialogHeader>

        <div className="flex gap-2 mb-4">
          <Button variant="outline" size="sm" onClick={handleCopy}>
            {copied ? (
              <>
                <Check className="w-4 h-4 mr-2" />
                Copied
              </>
            ) : (
              <>
                <Copy className="w-4 h-4 mr-2" />
                Copy
              </>
            )}
          </Button>
          <Button variant="outline" size="sm" onClick={handleDownload}>
            <Download className="w-4 h-4 mr-2" />
            Download
          </Button>
        </div>

        <ScrollArea className="flex-1 border rounded-md bg-gray-50 dark:bg-gray-900">
          <pre className="p-4 text-sm whitespace-pre-wrap font-mono">
            {source.full_text}
          </pre>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}
