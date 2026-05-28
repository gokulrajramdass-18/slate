"use client";

import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Copy, Plus, Trash2, ExternalLink, Mail } from "lucide-react";
import { toast } from "sonner";

interface Microsite {
  id: string;
  title: string;
  description: string | null;
  slug: string;
  theme: string;
  is_active: boolean;
  access_url: string;
  allowed_emails: string[];
}

interface MicrositeDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  notebookId: string;
  notebookTitle: string;
}

export function MicrositeDialog({ open, onOpenChange, notebookId, notebookTitle }: MicrositeDialogProps) {
  const [microsites, setMicrosites] = useState<Microsite[]>([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);

  // Form states
  const [title, setTitle] = useState(notebookTitle);
  const [description, setDescription] = useState("");
  const [theme, setTheme] = useState("light");
  const [newEmail, setNewEmail] = useState("");
  const [selectedMicrosite, setSelectedMicrosite] = useState<string | null>(null);

  const fetchMicrosites = async () => {
    try {
      setLoading(true);
      const response = await fetch(`/api/microsites?notebook_id=${notebookId}`);
      if (response.ok) {
        const data = await response.json();
        setMicrosites(data);
      }
    } catch (error) {
      console.error("Failed to fetch microsites:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    try {
      setCreating(true);
      const response = await fetch("/api/microsites", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          notebook_id: notebookId,
          title,
          description,
          theme,
        }),
      });

      if (response.ok) {
        toast.success("Microsite created successfully");
        setTitle(notebookTitle);
        setDescription("");
        setTheme("light");
        await fetchMicrosites();
      } else {
        toast.error("Failed to create microsite");
      }
    } catch (error) {
      toast.error("Failed to create microsite");
    } finally {
      setCreating(false);
    }
  };

  const handleAddEmail = async (micrositeId: string) => {
    if (!newEmail.trim()) {
      toast.error("Please enter an email address");
      return;
    }

    try {
      const response = await fetch(`/api/microsites/${micrositeId}/access`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: newEmail }),
      });

      if (response.ok) {
        toast.success("Email added");
        setNewEmail("");
        await fetchMicrosites();
      } else {
        toast.error("Failed to add email");
      }
    } catch (error) {
      toast.error("Failed to add email");
    }
  };

  const handleRemoveEmail = async (micrositeId: string, email: string) => {
    try {
      const response = await fetch(`/api/microsites/${micrositeId}/access/${email}`, {
        method: "DELETE",
      });

      if (response.ok) {
        toast.success("Email removed");
        await fetchMicrosites();
      } else {
        toast.error("Failed to remove email");
      }
    } catch (error) {
      toast.error("Failed to remove email");
    }
  };

  const handleDelete = async (micrositeId: string) => {
    if (!confirm("Are you sure you want to delete this microsite?")) {
      return;
    }

    try {
      const response = await fetch(`/api/microsites/${micrositeId}`, {
        method: "DELETE",
      });

      if (response.ok) {
        toast.success("Microsite deleted");
        await fetchMicrosites();
      } else {
        toast.error("Failed to delete microsite");
      }
    } catch (error) {
      toast.error("Failed to delete microsite");
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success("Copied to clipboard");
  };

  // Fetch microsites when dialog opens
  useState(() => {
    if (open) {
      fetchMicrosites();
    }
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Manage Microsites</DialogTitle>
        </DialogHeader>

        <div className="space-y-6">
          {/* Create New Microsite */}
          <Card>
            <CardContent className="pt-6">
              <h3 className="text-lg font-semibold mb-4">Create New Microsite</h3>
              <div className="space-y-4">
                <div>
                  <Label>Title</Label>
                  <Input
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="My Research Project"
                  />
                </div>

                <div>
                  <Label>Description (optional)</Label>
                  <Textarea
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Describe what this microsite contains..."
                    rows={3}
                  />
                </div>

                <div>
                  <Label>Theme</Label>
                  <Select value={theme} onValueChange={setTheme}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="light">Light</SelectItem>
                      <SelectItem value="dark">Dark</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <Button onClick={handleCreate} disabled={creating || !title.trim()}>
                  Create Microsite
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Existing Microsites */}
          {loading ? (
            <div className="text-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto"></div>
            </div>
          ) : microsites.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              No microsites yet. Create one to share your notebook!
            </div>
          ) : (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">Your Microsites</h3>
              {microsites.map((microsite) => (
                <Card key={microsite.id}>
                  <CardContent className="pt-6">
                    <div className="space-y-4">
                      <div className="flex items-start justify-between">
                        <div>
                          <h4 className="font-semibold">{microsite.title}</h4>
                          {microsite.description && (
                            <p className="text-sm text-gray-500 mt-1">{microsite.description}</p>
                          )}
                          <div className="flex items-center gap-2 mt-2">
                            <Badge variant={microsite.is_active ? "default" : "secondary"}>
                              {microsite.is_active ? "Active" : "Inactive"}
                            </Badge>
                            <Badge variant="outline">{microsite.theme}</Badge>
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDelete(microsite.id)}
                        >
                          <Trash2 className="w-4 h-4 text-red-600" />
                        </Button>
                      </div>

                      <div className="space-y-2">
                        <Label>Public URL</Label>
                        <div className="flex gap-2">
                          <Input
                            value={`${window.location.origin}${microsite.access_url}`}
                            readOnly
                            className="flex-1"
                          />
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => copyToClipboard(`${window.location.origin}${microsite.access_url}`)}
                          >
                            <Copy className="w-4 h-4" />
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => window.open(`${window.location.origin}${microsite.access_url}`, "_blank")}
                          >
                            <ExternalLink className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>

                      <div className="space-y-2">
                        <Label>Allowed Email Addresses</Label>
                        <div className="flex gap-2">
                          <Input
                            value={selectedMicrosite === microsite.id ? newEmail : ""}
                            onChange={(e) => {
                              setSelectedMicrosite(microsite.id);
                              setNewEmail(e.target.value);
                            }}
                            placeholder="email@example.com"
                            type="email"
                          />
                          <Button
                            size="sm"
                            onClick={() => handleAddEmail(microsite.id)}
                            disabled={!newEmail.trim()}
                          >
                            <Plus className="w-4 h-4 mr-2" />
                            Add
                          </Button>
                        </div>

                        {microsite.allowed_emails.length === 0 ? (
                          <p className="text-sm text-gray-500">No email addresses added yet</p>
                        ) : (
                          <div className="flex flex-wrap gap-2 mt-2">
                            {microsite.allowed_emails.map((email) => (
                              <Badge key={email} variant="secondary" className="flex items-center gap-2">
                                <Mail className="w-3 h-3" />
                                {email}
                                <button
                                  onClick={() => handleRemoveEmail(microsite.id, email)}
                                  className="ml-1 hover:text-red-600"
                                >
                                  ×
                                </button>
                              </Badge>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
