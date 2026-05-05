"use client";

import { useState, useEffect } from "react";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  GripVertical,
  Eye,
  EyeOff,
  Trash2,
  Edit,
  Save,
  X,
  Settings as SettingsIcon,
  Loader2,
  Plus,
} from "lucide-react";
import { MicrositeContent } from "@/lib/types";
import { toast } from "sonner";
import { RichTextEditor } from "./RichTextEditor";
import { apiClient } from "@/lib/api/client";

interface VisualEditorProps {
  sections: MicrositeContent[];
  micrositeId: string;
  onSave: (sections: MicrositeContent[]) => Promise<void>;
  onSettingsUpdate?: () => void;
}

interface SortableItemProps {
  section: MicrositeContent;
  onEdit: (section: MicrositeContent) => void;
  onToggleVisibility: (id: string) => void;
  onDelete: (id: string) => void;
}

function SortableItem({
  section,
  onEdit,
  onToggleVisibility,
  onDelete,
}: SortableItemProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: section.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <Card
      ref={setNodeRef}
      style={style}
      className={`p-4 ${!section.is_visible ? "opacity-50" : ""}`}
    >
      <div className="flex items-start gap-3">
        {/* Drag Handle */}
        <button
          {...attributes}
          {...listeners}
          className="mt-1 cursor-grab active:cursor-grabbing hover:text-primary"
        >
          <GripVertical className="w-5 h-5" />
        </button>

        {/* Content Preview */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <h3 className="font-semibold text-sm uppercase text-muted-foreground">
              {section.section_id}
            </h3>
            <span className="text-xs text-muted-foreground">
              Order: {section.sort_order}
            </span>
          </div>
          <div
            className="prose prose-sm dark:prose-invert max-w-none line-clamp-3"
            dangerouslySetInnerHTML={{ __html: section.content_html || "" }}
          />
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onEdit(section)}
            title="Edit section"
          >
            <Edit className="w-4 h-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onToggleVisibility(section.id)}
            title={section.is_visible ? "Hide section" : "Show section"}
          >
            {section.is_visible ? (
              <Eye className="w-4 h-4" />
            ) : (
              <EyeOff className="w-4 h-4" />
            )}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onDelete(section.id)}
            title="Delete section"
            className="text-destructive hover:text-destructive"
          >
            <Trash2 className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </Card>
  );
}

export function VisualEditor({ sections: initialSections, micrositeId, onSave, onSettingsUpdate }: VisualEditorProps) {
  const [sections, setSections] = useState<MicrositeContent[]>(initialSections);
  const [editingSection, setEditingSection] = useState<MicrositeContent | null>(null);
  const [editContent, setEditContent] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  // Site-level settings
  const [siteTitle, setSiteTitle] = useState("Microsite");
  const [logoUrl, setLogoUrl] = useState("");
  const [primaryColor, setPrimaryColor] = useState("#0066cc");
  const [footerText, setFooterText] = useState("");
  const [navItems, setNavItems] = useState<Array<{ label: string; url: string }>>([
    { label: "Home", url: "#" },
    { label: "About", url: "#about" },
    { label: "Content", url: "#content" },
    { label: "Contact", url: "#contact" },
  ]);
  const [isSavingSettings, setIsSavingSettings] = useState(false);

  // Load current microsite settings on mount
  useEffect(() => {
    const loadMicrositeSettings = async () => {
      try {
        const response = await apiClient.get(`/microsites/${micrositeId}`);
        const microsite = response.data;

        // Update site title
        if (microsite.title) {
          setSiteTitle(microsite.title);
        }

        // Parse generation_config to get custom settings
        if (microsite.generation_config) {
          const config = typeof microsite.generation_config === 'string'
            ? JSON.parse(microsite.generation_config)
            : microsite.generation_config;

          if (config.site_title) {
            setSiteTitle(config.site_title);
          }
          if (config.logo_url) {
            setLogoUrl(config.logo_url);
          }
          if (config.primary_color) {
            setPrimaryColor(config.primary_color);
          }
          if (config.footer_text) {
            setFooterText(config.footer_text);
          }
          if (config.nav_items && Array.isArray(config.nav_items)) {
            setNavItems(config.nav_items);
          }
        }
      } catch (error) {
        console.error("Failed to load microsite settings:", error);
      }
    };

    loadMicrositeSettings();
  }, [micrositeId]);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;

    if (over && active.id !== over.id) {
      setSections((items) => {
        const oldIndex = items.findIndex((item) => item.id === active.id);
        const newIndex = items.findIndex((item) => item.id === over.id);
        const reordered = arrayMove(items, oldIndex, newIndex);

        // Update order_num to reflect new positions
        return reordered.map((item, idx) => ({
          ...item,
          order_num: idx,
        }));
      });
    }
  };

  const handleEdit = (section: MicrositeContent) => {
    setEditingSection(section);
    setEditContent(section.content_html || "");
  };

  const handleSaveEdit = () => {
    if (!editingSection) return;

    setSections((prev) =>
      prev.map((s) =>
        s.id === editingSection.id
          ? { ...s, content_html: editContent }
          : s
      )
    );

    setEditingSection(null);
    setEditContent("");
    toast.success("Section updated");
  };

  const handleCancelEdit = () => {
    setEditingSection(null);
    setEditContent("");
  };

  const handleToggleVisibility = (id: string) => {
    setSections((prev) =>
      prev.map((s) =>
        s.id === id ? { ...s, is_visible: !s.is_visible } : s
      )
    );
  };

  const handleDelete = (id: string) => {
    if (confirm("Are you sure you want to delete this section?")) {
      setSections((prev) => prev.filter((s) => s.id !== id));
      toast.success("Section deleted");
    }
  };

  const handleAddSection = () => {
    const newSection: MicrositeContent = {
      id: `new-${Date.now()}`,
      microsite_id: micrositeId,
      section_id: "custom_section",
      section_type: "custom",
      content_html: "<h2>New Section</h2><p>Add your content here...</p>",
      content_json: undefined,
      sort_order: sections.length,
      is_visible: true,
      created: new Date().toISOString(),
      updated: new Date().toISOString(),
    };
    setSections((prev) => [...prev, newSection]);
    toast.success("New section added");
  };

  const handleSaveAll = async () => {
    setIsSaving(true);
    try {
      await onSave(sections);
      toast.success("Changes saved successfully");
    } catch (error: any) {
      toast.error(error.message || "Failed to save changes");
    } finally {
      setIsSaving(false);
    }
  };

  const handleSaveSiteSettings = async () => {
    setIsSavingSettings(true);
    try {
      console.log("Saving site settings for microsite:", micrositeId);
      console.log("Settings:", { siteTitle, logoUrl, primaryColor, footerText, navItems });

      // Call the settings update endpoint (does NOT regenerate content)
      const response = await apiClient.put(`/microsites/${micrositeId}/settings`, {
        site_title: siteTitle,
        logo_url: logoUrl,
        primary_color: primaryColor,
        footer_text: footerText,
        nav_items: navItems,
      });

      console.log("Response:", response.data);
      toast.success("Site settings updated successfully");
      setShowSettings(false);

      // Trigger data refetch via callback
      if (onSettingsUpdate) {
        onSettingsUpdate();
      }
    } catch (error: any) {
      console.error("Failed to save settings:", error);
      toast.error(error.response?.data?.detail || error.message || "Failed to update site settings");
    } finally {
      setIsSavingSettings(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Header with Save and Settings buttons */}
      <div className="flex justify-between items-center">
        <p className="text-sm text-muted-foreground">
          Drag sections to reorder, click edit to modify content
        </p>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => setShowSettings(true)}
          >
            <SettingsIcon className="w-4 h-4 mr-2" />
            Site Settings
          </Button>
          <Button onClick={handleSaveAll} disabled={isSaving}>
            <Save className="w-4 h-4 mr-2" />
            {isSaving ? "Saving..." : "Save All Changes"}
          </Button>
        </div>
      </div>

      {/* Sections List with Drag-and-Drop */}
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext
          items={sections.map((s) => s.id)}
          strategy={verticalListSortingStrategy}
        >
          <div className="space-y-3">
            {sections.map((section) => (
              <SortableItem
                key={section.id}
                section={section}
                onEdit={handleEdit}
                onToggleVisibility={handleToggleVisibility}
                onDelete={handleDelete}
              />
            ))}
          </div>
        </SortableContext>
      </DndContext>

      {/* Add Section Button */}
      <div className="mt-4">
        <Button
          variant="outline"
          className="w-full"
          onClick={handleAddSection}
        >
          <Plus className="w-4 h-4 mr-2" />
          Add New Section
        </Button>
      </div>

      {/* Edit Modal */}
      {editingSection && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-5xl max-h-[90vh] overflow-auto p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold">
                Edit Section: {editingSection.section_id}
              </h2>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleCancelEdit}
              >
                <X className="w-4 h-4" />
              </Button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium mb-2 block">
                  Content
                </label>
                <RichTextEditor
                  content={editContent}
                  onChange={setEditContent}
                  placeholder="Enter content here..."
                />
              </div>

              <div className="flex gap-2 justify-end border-t pt-4">
                <Button variant="outline" onClick={handleCancelEdit}>
                  Cancel
                </Button>
                <Button onClick={handleSaveEdit}>
                  <Save className="w-4 h-4 mr-2" />
                  Save Section
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}
      {/* Settings Modal */}
      {showSettings && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-2xl p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold">Site Settings</h2>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowSettings(false)}
              >
                <X className="w-4 h-4" />
              </Button>
            </div>

            <div className="space-y-4">
              {/* Site Title */}
              <div>
                <label className="text-sm font-medium mb-2 block">
                  Site Title
                </label>
                <Input
                  value={siteTitle}
                  onChange={(e) => setSiteTitle(e.target.value)}
                  placeholder="My Awesome Website"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  This appears in the header and browser tab
                </p>
              </div>

              {/* Logo URL */}
              <div>
                <label className="text-sm font-medium mb-2 block">
                  Logo URL (Optional)
                </label>
                <Input
                  value={logoUrl}
                  onChange={(e) => setLogoUrl(e.target.value)}
                  placeholder="https://example.com/logo.png"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Leave empty to show site initial instead
                </p>
              </div>

              {/* Primary Color */}
              <div>
                <label className="text-sm font-medium mb-2 block">
                  Primary Color
                </label>
                <div className="flex gap-2 items-center">
                  <Input
                    type="color"
                    value={primaryColor}
                    onChange={(e) => setPrimaryColor(e.target.value)}
                    className="w-20 h-10"
                  />
                  <Input
                    value={primaryColor}
                    onChange={(e) => setPrimaryColor(e.target.value)}
                    placeholder="#0066cc"
                    className="flex-1"
                  />
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  Main color for buttons, links, and accents
                </p>
              </div>

              {/* Footer Text */}
              <div>
                <label className="text-sm font-medium mb-2 block">
                  Footer Text (Optional)
                </label>
                <Textarea
                  value={footerText}
                  onChange={(e) => setFooterText(e.target.value)}
                  placeholder="© 2026 Your Company. All rights reserved."
                  rows={2}
                />
              </div>

              {/* Navigation Menu */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-sm font-medium">
                    Navigation Menu
                  </label>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setNavItems([...navItems, { label: "New Link", url: "#" }])}
                  >
                    <Plus className="w-4 h-4 mr-1" />
                    Add Item
                  </Button>
                </div>
                <div className="space-y-2">
                  {navItems.map((item, index) => (
                    <div key={index} className="flex gap-2 items-start">
                      <div className="flex-1 grid grid-cols-2 gap-2">
                        <Input
                          value={item.label}
                          onChange={(e) => {
                            const newItems = [...navItems];
                            newItems[index].label = e.target.value;
                            setNavItems(newItems);
                          }}
                          placeholder="Label (e.g. Home)"
                        />
                        <Input
                          value={item.url}
                          onChange={(e) => {
                            const newItems = [...navItems];
                            newItems[index].url = e.target.value;
                            setNavItems(newItems);
                          }}
                          placeholder="URL (e.g. #home)"
                        />
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          const newItems = navItems.filter((_, i) => i !== index);
                          setNavItems(newItems);
                        }}
                        className="text-destructive"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  Add, edit, or remove navigation menu items
                </p>
              </div>

              <div className="flex gap-2 justify-end border-t pt-4">
                <Button variant="outline" onClick={() => setShowSettings(false)} disabled={isSavingSettings}>
                  Cancel
                </Button>
                <Button onClick={handleSaveSiteSettings} disabled={isSavingSettings}>
                  {isSavingSettings ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    <>
                      <Save className="w-4 h-4 mr-2" />
                      Save Settings
                    </>
                  )}
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
