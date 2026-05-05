"use client";

import { useState, useCallback, useEffect, useRef, useMemo } from "react";
import dynamic from "next/dynamic";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Save,
  Maximize2,
  Minimize2,
  RefreshCw,
  Loader2,
  Code2,
} from "lucide-react";
import { toast } from "sonner";

const MonacoEditor = dynamic(() => import("@monaco-editor/react").then((mod) => mod.default), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-full bg-muted/30">
      <Loader2 className="w-6 h-6 animate-spin" />
    </div>
  ),
});

interface CodeEditorProps {
  micrositeId: string;
  initialHtml: string;
  initialCss: string;
  initialJs: string;
  onSave: (html: string, css: string, js: string) => Promise<void>;
  isSaving?: boolean;
}

export function CodeEditor({
  micrositeId,
  initialHtml,
  initialCss,
  initialJs,
  onSave,
  isSaving,
}: CodeEditorProps) {
  const [html, setHtml] = useState(initialHtml);
  const [css, setCss] = useState(initialCss);
  const [js, setJs] = useState(initialJs);
  const [activeTab, setActiveTab] = useState("html");
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const previewTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setHtml(initialHtml);
    setCss(initialCss);
    setJs(initialJs);
    setHasChanges(false);
  }, [initialHtml, initialCss, initialJs]);

  const previewDoc = useMemo(() => {
    return `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>${css}</style>
</head>
<body>
${html}
<script>${js}<\/script>
</body>
</html>`;
  }, [html, css, js]);

  const updatePreview = useCallback(() => {
    if (iframeRef.current) {
      const doc = iframeRef.current.contentDocument;
      if (doc) {
        doc.open();
        doc.write(previewDoc);
        doc.close();
      }
    }
  }, [previewDoc]);

  useEffect(() => {
    if (previewTimerRef.current) {
      clearTimeout(previewTimerRef.current);
    }
    previewTimerRef.current = setTimeout(updatePreview, 500);
    return () => {
      if (previewTimerRef.current) {
        clearTimeout(previewTimerRef.current);
      }
    };
  }, [updatePreview]);

  const handleChange = useCallback(
    (value: string | undefined, tab: string) => {
      const val = value || "";
      if (tab === "html") setHtml(val);
      else if (tab === "css") setCss(val);
      else if (tab === "js") setJs(val);
      setHasChanges(true);
    },
    []
  );

  const handleSave = async () => {
    try {
      await onSave(html, css, js);
      setHasChanges(false);
      toast.success("Code saved");
    } catch {
      toast.error("Failed to save code");
    }
  };

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "s") {
        e.preventDefault();
        if (hasChanges && !isSaving) {
          handleSave();
        }
      }
    },
    [hasChanges, isSaving]
  );

  const editorOptions = {
    minimap: { enabled: false },
    fontSize: 13,
    lineNumbers: "on" as const,
    wordWrap: "on" as const,
    scrollBeyondLastLine: false,
    automaticLayout: true,
    tabSize: 2,
  };

  return (
    <div
      className={`flex flex-col ${
        isFullscreen
          ? "fixed inset-0 z-50 bg-background"
          : "h-[600px]"
      }`}
      onKeyDown={handleKeyDown}
    >
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 border-b bg-muted/30">
        <div className="flex items-center gap-2">
          <Code2 className="w-4 h-4" />
          <span className="text-sm font-medium">Code Editor</span>
          {hasChanges && (
            <Badge variant="secondary" className="text-xs">
              Unsaved changes
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={updatePreview}
            title="Refresh preview"
          >
            <RefreshCw className="w-4 h-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsFullscreen(!isFullscreen)}
            title={isFullscreen ? "Exit fullscreen" : "Fullscreen"}
          >
            {isFullscreen ? (
              <Minimize2 className="w-4 h-4" />
            ) : (
              <Maximize2 className="w-4 h-4" />
            )}
          </Button>
          <Button
            size="sm"
            onClick={handleSave}
            disabled={!hasChanges || isSaving}
          >
            {isSaving ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Save className="w-4 h-4 mr-2" />
            )}
            Save
          </Button>
        </div>
      </div>

      {/* Split View */}
      <div className="flex-1 flex min-h-0">
        {/* Editor Panel */}
        <div className="w-1/2 flex flex-col border-r">
          <Tabs
            value={activeTab}
            onValueChange={setActiveTab}
            className="flex flex-col h-full"
          >
            <TabsList className="rounded-none border-b h-auto p-0 bg-transparent">
              <TabsTrigger
                value="html"
                className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent px-4 py-2"
              >
                HTML
              </TabsTrigger>
              <TabsTrigger
                value="css"
                className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent px-4 py-2"
              >
                CSS
              </TabsTrigger>
              <TabsTrigger
                value="js"
                className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent px-4 py-2"
              >
                JavaScript
              </TabsTrigger>
            </TabsList>

            <TabsContent value="html" className="flex-1 m-0">
              <MonacoEditor
                height="100%"
                language="html"
                value={html}
                onChange={(v) => handleChange(v, "html")}
                options={editorOptions}
                theme="vs-dark"
              />
            </TabsContent>
            <TabsContent value="css" className="flex-1 m-0">
              <MonacoEditor
                height="100%"
                language="css"
                value={css}
                onChange={(v) => handleChange(v, "css")}
                options={editorOptions}
                theme="vs-dark"
              />
            </TabsContent>
            <TabsContent value="js" className="flex-1 m-0">
              <MonacoEditor
                height="100%"
                language="javascript"
                value={js}
                onChange={(v) => handleChange(v, "js")}
                options={editorOptions}
                theme="vs-dark"
              />
            </TabsContent>
          </Tabs>
        </div>

        {/* Preview Panel */}
        <div className="w-1/2 flex flex-col">
          <div className="px-4 py-2 border-b bg-muted/30 text-xs text-muted-foreground">
            Live Preview
          </div>
          <div className="flex-1 bg-white">
            <iframe
              ref={iframeRef}
              className="w-full h-full border-0"
              sandbox="allow-scripts allow-same-origin"
              title="Live Preview"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
