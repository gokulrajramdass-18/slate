"use client";

import { useState } from "react";
import Editor from "@monaco-editor/react";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Save, Loader2 } from "lucide-react";
import { MicrositeContent } from "@/lib/types";
import { toast } from "sonner";
import { apiClient } from "@/lib/api/client";

interface CodeEditorPanelProps {
  sections: MicrositeContent[];
  micrositeId: string;
  onSave: (sections: MicrositeContent[]) => Promise<void>;
}

export function CodeEditorPanel({ sections, micrositeId, onSave }: CodeEditorPanelProps) {
  // Build complete HTML document with header/footer for editing
  const buildFullHTML = () => {
    const hero = sections.find(s => s.section_id === "hero");
    const main = sections.filter(s => !["hero", "footer"].includes(s.section_id));
    const footer = sections.find(s => s.section_id === "footer");

    let html = `<!--
  MICROSITE HTML EDITOR

  This editor shows the content sections of your microsite.
  The header (logo + navigation) and footer wrapper are automatically generated.

  Structure:
  - HERO SECTION: Banner at the top
  - MAIN SECTIONS: Body content
  - FOOTER SECTION: Footer content

  DO NOT remove the section comments (<!-- ... -->), they help preserve structure when saving.
-->\n\n`;

    if (hero) html += `<!-- HERO SECTION -->\n${hero.content_html || ""}\n\n`;
    html += `<!-- MAIN SECTIONS -->\n`;
    main.forEach(s => {
      html += `<!-- Section: ${s.section_id} -->\n${s.content_html || ""}\n\n`;
    });
    if (footer) html += `<!-- FOOTER SECTION -->\n${footer.content_html || ""}\n`;

    return html;
  };

  const [htmlCode, setHtmlCode] = useState(buildFullHTML());
  const [cssCode, setCssCode] = useState(
    `/* Add your custom CSS here */

/* Example: Change primary color */
:root {
  --primary-color: #0066cc;
}

/* Example: Custom heading styles */
h1 {
  font-size: 2.5rem;
  color: var(--primary-color);
}

/* Example: Custom section styling */
.content-section {
  padding: 2rem;
  border-radius: 12px;
}
`
  );
  const [activeTab, setActiveTab] = useState<"html" | "css">("html");
  const [isSaving, setIsSaving] = useState(false);
  const [previewKey, setPreviewKey] = useState(0);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      // Parse the edited HTML back into sections
      const updatedSections = [...sections];

      // Extract sections using comments as delimiters
      const heroMatch = htmlCode.match(/<!-- HERO SECTION -->\n([\s\S]*?)(?=<!-- |$)/);
      const footerMatch = htmlCode.match(/<!-- FOOTER SECTION -->\n([\s\S]*?)$/);
      const mainMatch = htmlCode.match(/<!-- MAIN SECTIONS -->\n([\s\S]*?)(?=<!-- FOOTER|$)/);

      if (heroMatch) {
        const heroSection = updatedSections.find(s => s.section_id === "hero");
        if (heroSection) heroSection.content_html = heroMatch[1].trim();
      }

      if (footerMatch) {
        const footerSection = updatedSections.find(s => s.section_id === "footer");
        if (footerSection) footerSection.content_html = footerMatch[1].trim();
      }

      if (mainMatch) {
        // For main sections, just update them all with the main content
        // This is a simplified approach - could be improved to preserve individual sections
        const mainSections = updatedSections.filter(s => !["hero", "footer"].includes(s.section_id));
        if (mainSections.length > 0) {
          const mainHTML = mainMatch[1].trim();
          // Split by section comments if they exist
          const sectionParts = mainHTML.split(/<!-- Section: .*? -->\n/);
          mainSections.forEach((section, idx) => {
            if (sectionParts[idx + 1]) {
              section.content_html = sectionParts[idx + 1].trim();
            }
          });
        }
      }

      // Build the update payload
      await apiClient.put(`/microsites/${micrositeId}/content`, {
        sections: updatedSections.map((s) => ({
          section_id: s.id,
          content_html: s.content_html,
          content_json: s.content_json,
        })),
        custom_css: cssCode,
      });

      toast.success("Code saved successfully");

      // Refresh preview
      setPreviewKey(prev => prev + 1);
    } catch (error: any) {
      toast.error(error.message || "Failed to save code");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="grid grid-cols-2 gap-4 h-[calc(100vh-250px)]">
      {/* Code Editor Side */}
      <div className="border rounded-lg overflow-hidden flex flex-col bg-white dark:bg-gray-950">
        <div className="border-b p-3 flex items-center justify-between bg-muted/30">
          <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as "html" | "css")} className="flex-1">
            <TabsList>
              <TabsTrigger value="html">HTML</TabsTrigger>
              <TabsTrigger value="css">CSS</TabsTrigger>
            </TabsList>
          </Tabs>
          <Button onClick={handleSave} disabled={isSaving} size="sm" className="ml-2">
            {isSaving ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Save className="w-4 h-4 mr-2" />
            )}
            Save
          </Button>
        </div>

        <div className="flex-1">
          {activeTab === "html" && (
            <Editor
              height="100%"
              defaultLanguage="html"
              value={htmlCode}
              onChange={(value) => setHtmlCode(value || "")}
              theme="vs-dark"
              options={{
                minimap: { enabled: false },
                fontSize: 14,
                lineNumbers: "on",
                wordWrap: "on",
                automaticLayout: true,
                scrollBeyondLastLine: false,
                padding: { top: 16, bottom: 16 },
              }}
            />
          )}
          {activeTab === "css" && (
            <Editor
              height="100%"
              defaultLanguage="css"
              value={cssCode}
              onChange={(value) => setCssCode(value || "")}
              theme="vs-dark"
              options={{
                minimap: { enabled: false },
                fontSize: 14,
                lineNumbers: "on",
                wordWrap: "on",
                automaticLayout: true,
                scrollBeyondLastLine: false,
                padding: { top: 16, bottom: 16 },
              }}
            />
          )}
        </div>
      </div>

      {/* Preview Side */}
      <div className="border rounded-lg overflow-hidden flex flex-col bg-white dark:bg-gray-950">
        <div className="border-b p-3 bg-muted/30">
          <h3 className="font-medium">Live Preview</h3>
        </div>
        <div className="flex-1 overflow-auto">
          <iframe
            key={previewKey}
            src={`/api/microsites/${micrositeId}/preview?t=${Date.now()}`}
            className="w-full h-full border-0"
            sandbox="allow-scripts allow-same-origin"
            title="Microsite Preview"
          />
        </div>
      </div>
    </div>
  );
}
