import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  settingsLookupsApi,
  type LookupItem,
  type LookupListSummary,
} from "@/lib/api/settings-lookups";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Plus, Trash2, ChevronUp, ChevronDown, Save, List } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";
import { Can } from "@/components/auth/can";

const EMPTY_ITEM: LookupItem = {
  value: "",
  label: "",
  description: "",
  icon: "",
  color: "",
  active: true,
  sort_order: 0,
};

export default function SettingsLookupsPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [items, setItems] = useState<LookupItem[]>([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [newItem, setNewItem] = useState<LookupItem>(EMPTY_ITEM);

  const lists = useQuery({
    queryKey: ["lookups", "list"],
    queryFn: () => settingsLookupsApi.list(),
  });

  useEffect(() => {
    if (!selectedKey && lists.data && lists.data.length > 0) {
      setSelectedKey(lists.data[0].key);
    }
  }, [lists.data, selectedKey]);

  const detail = useQuery({
    queryKey: ["lookups", selectedKey],
    queryFn: () => settingsLookupsApi.get(selectedKey as string),
    enabled: !!selectedKey,
  });

  useEffect(() => {
    if (detail.data) {
      setItems(detail.data.items);
      setTitle(detail.data.title);
      setDescription(detail.data.description);
    }
  }, [detail.data]);

  const replaceMutation = useMutation({
    mutationFn: () =>
      settingsLookupsApi.replace(selectedKey as string, {
        title,
        description,
        items,
      }),
    onSuccess: () => {
      toast({ title: "Saved", description: "Lookup list updated." });
      queryClient.invalidateQueries({ queryKey: ["lookups"] });
      queryClient.invalidateQueries({ queryKey: ["lookup-options"] });
    },
    onError: (err: any) => {
      toast({
        title: "Failed to save",
        description: err?.response?.data?.detail || err?.message || "Unknown error",
        variant: "destructive",
      });
    },
  });

  const updateItemField = <K extends keyof LookupItem>(
    index: number,
    field: K,
    value: LookupItem[K]
  ) => {
    setItems((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], [field]: value };
      return next;
    });
  };

  const removeItem = (index: number) => {
    setItems((prev) => prev.filter((_, i) => i !== index));
  };

  const moveItem = (index: number, dir: -1 | 1) => {
    setItems((prev) => {
      const target = index + dir;
      if (target < 0 || target >= prev.length) return prev;
      const next = [...prev];
      [next[index], next[target]] = [next[target], next[index]];
      return next.map((item, i) => ({ ...item, sort_order: i + 1 }));
    });
  };

  const addItem = () => {
    if (!newItem.value.trim() || !newItem.label.trim()) {
      toast({
        title: "Missing fields",
        description: "Value and label are required.",
        variant: "destructive",
      });
      return;
    }
    if (!/^[a-z0-9_-]+$/.test(newItem.value)) {
      toast({
        title: "Invalid value",
        description: "Value must contain only lowercase letters, digits, underscores, and dashes.",
        variant: "destructive",
      });
      return;
    }
    if (items.some((i) => i.value === newItem.value)) {
      toast({
        title: "Duplicate value",
        description: `An item with value "${newItem.value}" already exists.`,
        variant: "destructive",
      });
      return;
    }
    setItems((prev) => [
      ...prev,
      { ...newItem, sort_order: prev.length + 1 },
    ]);
    setNewItem(EMPTY_ITEM);
  };

  return (
    <Can resource="settings" action="manage" fallback={
      <div className="p-8 text-center text-muted-foreground">
        You need admin permissions to manage lookup lists.
      </div>
    }>
      <div className="container mx-auto py-6 max-w-7xl">
        <div className="mb-6 flex items-center gap-3">
          <List className="h-7 w-7 text-indigo-600" />
          <div>
            <h1 className="text-2xl font-bold">Lookup Lists</h1>
            <p className="text-sm text-muted-foreground">
              Manage admin-curated dropdown values used across the app.
            </p>
          </div>
        </div>

        <div className="grid gap-6 md:grid-cols-[260px_1fr]">
          {/* Left sidebar: registered lists */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Registered lists</CardTitle>
            </CardHeader>
            <CardContent className="space-y-1 p-2">
              {lists.isLoading && (
                <div className="p-3 text-sm text-muted-foreground">Loading...</div>
              )}
              {!lists.isLoading && (lists.data ?? []).length === 0 && (
                <div className="p-3 text-sm text-muted-foreground">
                  No lookup lists registered yet.
                </div>
              )}
              {(lists.data ?? []).map((summary: LookupListSummary) => (
                <button
                  key={summary.key}
                  onClick={() => setSelectedKey(summary.key)}
                  className={`w-full rounded-md p-3 text-left transition-colors ${
                    selectedKey === summary.key
                      ? "bg-indigo-50 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300"
                      : "hover:bg-muted"
                  }`}
                >
                  <div className="font-medium text-sm">{summary.title}</div>
                  <div className="mt-1 flex gap-2">
                    <Badge variant="outline" className="text-xs">
                      {summary.active_count}/{summary.item_count} active
                    </Badge>
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground font-mono truncate">
                    {summary.key}
                  </div>
                </button>
              ))}
            </CardContent>
          </Card>

          {/* Right pane: list editor */}
          {selectedKey && (
            <Card>
              <CardHeader>
                <CardTitle>{title || selectedKey}</CardTitle>
                <CardDescription>{description}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-3 md:grid-cols-2">
                  <div>
                    <Label>Title</Label>
                    <Input
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                    />
                  </div>
                  <div>
                    <Label>Description</Label>
                    <Input
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                    />
                  </div>
                </div>

                <div>
                  <div className="mb-2 flex items-center justify-between">
                    <Label className="text-base">Items ({items.length})</Label>
                  </div>
                  <div className="space-y-2">
                    {items.length === 0 && (
                      <div className="p-4 rounded-md bg-muted text-sm text-muted-foreground text-center">
                        No items yet. Add one below.
                      </div>
                    )}
                    {items.map((item, index) => (
                      <div
                        key={item.value}
                        className="grid gap-2 p-3 rounded-md border bg-card md:grid-cols-[auto_1fr_1fr_auto_auto_auto]"
                      >
                        <div className="flex flex-col">
                          <Button
                            type="button"
                            size="icon"
                            variant="ghost"
                            className="h-6 w-6"
                            onClick={() => moveItem(index, -1)}
                            disabled={index === 0}
                          >
                            <ChevronUp className="h-4 w-4" />
                          </Button>
                          <Button
                            type="button"
                            size="icon"
                            variant="ghost"
                            className="h-6 w-6"
                            onClick={() => moveItem(index, 1)}
                            disabled={index === items.length - 1}
                          >
                            <ChevronDown className="h-4 w-4" />
                          </Button>
                        </div>
                        <div>
                          <Label className="text-xs">Label</Label>
                          <Input
                            value={item.label}
                            onChange={(e) =>
                              updateItemField(index, "label", e.target.value)
                            }
                          />
                        </div>
                        <div>
                          <Label className="text-xs">Value (slug)</Label>
                          <Input
                            value={item.value}
                            disabled
                            className="font-mono text-xs"
                          />
                        </div>
                        <div>
                          <Label className="text-xs">Color</Label>
                          <div className="flex gap-1 items-center">
                            <Input
                              type="color"
                              value={item.color || "#64748b"}
                              onChange={(e) =>
                                updateItemField(index, "color", e.target.value)
                              }
                              className="w-12 h-9 p-1"
                            />
                            <Input
                              value={item.color || ""}
                              onChange={(e) =>
                                updateItemField(index, "color", e.target.value)
                              }
                              placeholder="#hex"
                              className="font-mono text-xs"
                            />
                          </div>
                        </div>
                        <div>
                          <Label className="text-xs">Icon</Label>
                          <Input
                            value={item.icon || ""}
                            onChange={(e) =>
                              updateItemField(index, "icon", e.target.value)
                            }
                            placeholder="lucide name"
                          />
                        </div>
                        <div className="flex flex-col items-center justify-between gap-1">
                          <div className="flex items-center gap-1">
                            <Switch
                              checked={item.active}
                              onCheckedChange={(checked) =>
                                updateItemField(index, "active", checked)
                              }
                            />
                            <span className="text-xs text-muted-foreground">
                              {item.active ? "On" : "Off"}
                            </span>
                          </div>
                          <Button
                            type="button"
                            size="icon"
                            variant="ghost"
                            className="h-7 w-7 text-destructive"
                            onClick={() => removeItem(index)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Add new item form */}
                <div className="rounded-md border-2 border-dashed p-3">
                  <Label className="text-base mb-2 block">Add new item</Label>
                  <div className="grid gap-2 md:grid-cols-5">
                    <div>
                      <Label className="text-xs">Value (slug)</Label>
                      <Input
                        value={newItem.value}
                        onChange={(e) =>
                          setNewItem((p) => ({ ...p, value: e.target.value }))
                        }
                        placeholder="my_item"
                        className="font-mono"
                      />
                    </div>
                    <div>
                      <Label className="text-xs">Label</Label>
                      <Input
                        value={newItem.label}
                        onChange={(e) =>
                          setNewItem((p) => ({ ...p, label: e.target.value }))
                        }
                        placeholder="My Item"
                      />
                    </div>
                    <div>
                      <Label className="text-xs">Color</Label>
                      <Input
                        type="color"
                        value={newItem.color || "#64748b"}
                        onChange={(e) =>
                          setNewItem((p) => ({ ...p, color: e.target.value }))
                        }
                        className="h-9 p-1"
                      />
                    </div>
                    <div>
                      <Label className="text-xs">Icon</Label>
                      <Input
                        value={newItem.icon || ""}
                        onChange={(e) =>
                          setNewItem((p) => ({ ...p, icon: e.target.value }))
                        }
                        placeholder="lucide name"
                      />
                    </div>
                    <div className="flex items-end">
                      <Button type="button" onClick={addItem} className="w-full">
                        <Plus className="h-4 w-4 mr-1" /> Add
                      </Button>
                    </div>
                  </div>
                </div>

                <div className="flex justify-end gap-2 pt-2 border-t">
                  <Button
                    onClick={() => replaceMutation.mutate()}
                    disabled={replaceMutation.isPending}
                  >
                    <Save className="h-4 w-4 mr-1" />
                    {replaceMutation.isPending ? "Saving..." : "Save changes"}
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </Can>
  );
}
