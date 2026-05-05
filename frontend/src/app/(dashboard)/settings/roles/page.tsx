"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { rolesApi, Role, RolePermission } from "@/lib/api/roles";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Plus, Edit, Trash2, Shield, Lock } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";
import { Can } from "@/components/auth/can";

interface RoleFormData {
  name: string;
  display_name: string;
  description: string;
}

interface PermissionFormData {
  resource_type: string;
  action: string;
  scope: "own" | "team" | "all";
}

const RESOURCE_TYPES = [
  { value: "workspace", label: "Workspace" },
  { value: "source", label: "Source" },
  { value: "chat_session", label: "Chat Session" },
  { value: "agent", label: "Agent" },
  { value: "tool", label: "Tool" },
  { value: "hana_connection", label: "HANA Connection" },
  { value: "api_connection", label: "API Connection" },
  { value: "microsite", label: "Microsite" },
  { value: "user", label: "User" },
  { value: "role", label: "Role" },
];

const ACTIONS = [
  { value: "create", label: "Create" },
  { value: "read", label: "Read" },
  { value: "update", label: "Update" },
  { value: "delete", label: "Delete" },
  { value: "execute", label: "Execute" },
  { value: "share", label: "Share" },
  { value: "publish", label: "Publish" },
];

const SCOPES = [
  { value: "own", label: "Own", description: "Only resources user created" },
  { value: "team", label: "Team", description: "Resources from user's team" },
  { value: "all", label: "All", description: "All resources in system" },
];

export default function RolesPage() {
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [editingRole, setEditingRole] = useState<Role | null>(null);
  const [selectedRole, setSelectedRole] = useState<Role | null>(null);
  const [isPermissionDialogOpen, setIsPermissionDialogOpen] = useState(false);
  const [formData, setFormData] = useState<RoleFormData>({
    name: "",
    display_name: "",
    description: "",
  });
  const [editData, setEditData] = useState<Partial<RoleFormData>>({});
  const [permissionData, setPermissionData] = useState<PermissionFormData>({
    resource_type: "",
    action: "",
    scope: "own",
  });

  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data: roles, isLoading } = useQuery({
    queryKey: ["roles"],
    queryFn: () => rolesApi.list(),
  });

  const { data: permissions } = useQuery({
    queryKey: ["role-permissions", selectedRole?.id],
    queryFn: () => {
      if (!selectedRole) return [];
      return rolesApi.getPermissions(selectedRole.id);
    },
    enabled: !!selectedRole,
  });

  const createMutation = useMutation({
    mutationFn: rolesApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["roles"] });
      setIsCreateDialogOpen(false);
      setFormData({ name: "", display_name: "", description: "" });
      toast({
        title: "Role created",
        description: "The role has been created successfully.",
      });
    },
    onError: (error: any) => {
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to create role",
        variant: "destructive",
      });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<RoleFormData> }) =>
      rolesApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["roles"] });
      setEditingRole(null);
      toast({
        title: "Role updated",
        description: "The role has been updated successfully.",
      });
    },
    onError: (error: any) => {
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to update role",
        variant: "destructive",
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: rolesApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["roles"] });
      toast({
        title: "Role deleted",
        description: "The role has been deleted successfully.",
      });
    },
    onError: (error: any) => {
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to delete role",
        variant: "destructive",
      });
    },
  });

  const addPermissionMutation = useMutation({
    mutationFn: ({
      roleId,
      permission,
    }: {
      roleId: string;
      permission: PermissionFormData;
    }) => rolesApi.addPermission(roleId, permission),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["role-permissions"] });
      setIsPermissionDialogOpen(false);
      setPermissionData({ resource_type: "", action: "", scope: "own" });
      toast({
        title: "Permission added",
        description: "The permission has been added successfully.",
      });
    },
    onError: (error: any) => {
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to add permission",
        variant: "destructive",
      });
    },
  });

  const removePermissionMutation = useMutation({
    mutationFn: ({
      roleId,
      permissionId,
    }: {
      roleId: string;
      permissionId: string;
    }) => rolesApi.removePermission(roleId, permissionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["role-permissions"] });
      toast({
        title: "Permission removed",
        description: "The permission has been removed successfully.",
      });
    },
    onError: (error: any) => {
      toast({
        title: "Error",
        description:
          error.response?.data?.detail || "Failed to remove permission",
        variant: "destructive",
      });
    },
  });

  const handleCreate = () => {
    createMutation.mutate(formData);
  };

  const handleEdit = (role: Role) => {
    setEditingRole(role);
    setEditData({
      display_name: role.display_name,
      description: role.description,
    });
  };

  const handleUpdate = () => {
    if (editingRole) {
      updateMutation.mutate({ id: editingRole.id, data: editData });
    }
  };

  const handleAddPermission = () => {
    if (selectedRole) {
      addPermissionMutation.mutate({
        roleId: selectedRole.id,
        permission: permissionData,
      });
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-lg">Loading roles...</div>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">Role Management</h1>
        <Can resource="role" action="create">
          <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="mr-2 h-4 w-4" />
                Create Role
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create New Role</DialogTitle>
                <DialogDescription>
                  Create a custom role with specific permissions.
                </DialogDescription>
              </DialogHeader>
              <div className="grid gap-4 py-4">
                <div className="grid gap-2">
                  <Label htmlFor="name">Name (identifier)</Label>
                  <Input
                    id="name"
                    value={formData.name}
                    onChange={(e) =>
                      setFormData({ ...formData, name: e.target.value })
                    }
                    placeholder="analyst"
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="display_name">Display Name</Label>
                  <Input
                    id="display_name"
                    value={formData.display_name}
                    onChange={(e) =>
                      setFormData({ ...formData, display_name: e.target.value })
                    }
                    placeholder="Data Analyst"
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="description">Description</Label>
                  <Textarea
                    id="description"
                    value={formData.description}
                    onChange={(e) =>
                      setFormData({ ...formData, description: e.target.value })
                    }
                    placeholder="Can view all data but only edit own reports"
                  />
                </div>
              </div>
              <DialogFooter>
                <Button
                  variant="outline"
                  onClick={() => setIsCreateDialogOpen(false)}
                >
                  Cancel
                </Button>
                <Button onClick={handleCreate} disabled={createMutation.isPending}>
                  {createMutation.isPending ? "Creating..." : "Create"}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </Can>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
        {roles?.map((role: Role) => (
          <Card key={role.id}>
            <CardHeader>
              <div className="flex justify-between items-start">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <Shield className="h-5 w-5" />
                    {role.display_name}
                  </CardTitle>
                  <CardDescription className="mt-1">
                    {role.description}
                  </CardDescription>
                </div>
                <div className="flex gap-1">
                  {role.is_system_role && (
                    <Badge variant="secondary" className="flex items-center gap-1">
                      <Lock className="h-3 w-3" />
                      System
                    </Badge>
                  )}
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setSelectedRole(role)}
                >
                  View Permissions
                </Button>
                <Can resource="role" action="update">
                  {!role.is_system_role && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleEdit(role)}
                    >
                      <Edit className="h-4 w-4" />
                    </Button>
                  )}
                </Can>
                <Can resource="role" action="delete">
                  {!role.is_system_role && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        if (
                          confirm(
                            `Are you sure you want to delete ${role.display_name}?`
                          )
                        ) {
                          deleteMutation.mutate(role.id);
                        }
                      }}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  )}
                </Can>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {selectedRole && (
        <Card>
          <CardHeader>
            <div className="flex justify-between items-center">
              <CardTitle>
                Permissions for {selectedRole.display_name}
              </CardTitle>
              <div className="flex gap-2">
                <Can resource="role" action="update">
                  {!selectedRole.is_system_role && (
                    <Dialog
                      open={isPermissionDialogOpen}
                      onOpenChange={setIsPermissionDialogOpen}
                    >
                      <DialogTrigger asChild>
                        <Button size="sm">
                          <Plus className="mr-2 h-4 w-4" />
                          Add Permission
                        </Button>
                      </DialogTrigger>
                      <DialogContent>
                        <DialogHeader>
                          <DialogTitle>Add Permission</DialogTitle>
                          <DialogDescription>
                            Grant a new permission to this role.
                          </DialogDescription>
                        </DialogHeader>
                        <div className="grid gap-4 py-4">
                          <div className="grid gap-2">
                            <Label>Resource Type</Label>
                            <Select
                              value={permissionData.resource_type}
                              onValueChange={(value) =>
                                setPermissionData({
                                  ...permissionData,
                                  resource_type: value,
                                })
                              }
                            >
                              <SelectTrigger>
                                <SelectValue placeholder="Select resource type" />
                              </SelectTrigger>
                              <SelectContent>
                                {RESOURCE_TYPES.map((rt) => (
                                  <SelectItem key={rt.value} value={rt.value}>
                                    {rt.label}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                          <div className="grid gap-2">
                            <Label>Action</Label>
                            <Select
                              value={permissionData.action}
                              onValueChange={(value) =>
                                setPermissionData({
                                  ...permissionData,
                                  action: value,
                                })
                              }
                            >
                              <SelectTrigger>
                                <SelectValue placeholder="Select action" />
                              </SelectTrigger>
                              <SelectContent>
                                {ACTIONS.map((action) => (
                                  <SelectItem key={action.value} value={action.value}>
                                    {action.label}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                          <div className="grid gap-2">
                            <Label>Scope</Label>
                            <Select
                              value={permissionData.scope}
                              onValueChange={(value: any) =>
                                setPermissionData({
                                  ...permissionData,
                                  scope: value,
                                })
                              }
                            >
                              <SelectTrigger>
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                {SCOPES.map((scope) => (
                                  <SelectItem key={scope.value} value={scope.value}>
                                    <div>
                                      <div className="font-medium">{scope.label}</div>
                                      <div className="text-xs text-muted-foreground">
                                        {scope.description}
                                      </div>
                                    </div>
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                        </div>
                        <DialogFooter>
                          <Button
                            variant="outline"
                            onClick={() => setIsPermissionDialogOpen(false)}
                          >
                            Cancel
                          </Button>
                          <Button
                            onClick={handleAddPermission}
                            disabled={
                              !permissionData.resource_type ||
                              !permissionData.action ||
                              addPermissionMutation.isPending
                            }
                          >
                            {addPermissionMutation.isPending
                              ? "Adding..."
                              : "Add Permission"}
                          </Button>
                        </DialogFooter>
                      </DialogContent>
                    </Dialog>
                  )}
                </Can>
                <Button variant="ghost" size="sm" onClick={() => setSelectedRole(null)}>
                  Close
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Resource Type</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Scope</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {permissions?.map((permission: RolePermission) => (
                  <TableRow key={permission.id}>
                    <TableCell className="font-medium">
                      {RESOURCE_TYPES.find((rt) => rt.value === permission.resource_type)
                        ?.label || permission.resource_type}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">
                        {ACTIONS.find((a) => a.value === permission.action)?.label ||
                          permission.action}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          permission.scope === "all"
                            ? "default"
                            : permission.scope === "team"
                            ? "secondary"
                            : "outline"
                        }
                      >
                        {permission.scope}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Can resource="role" action="update">
                        {!selectedRole.is_system_role && (
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() =>
                              removePermissionMutation.mutate({
                                roleId: selectedRole.id,
                                permissionId: permission.id,
                              })
                            }
                          >
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        )}
                      </Can>
                    </TableCell>
                  </TableRow>
                ))}
                {(!permissions || permissions.length === 0) && (
                  <TableRow>
                    <TableCell colSpan={4} className="text-center text-muted-foreground">
                      No permissions assigned
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {editingRole && (
        <Dialog open={!!editingRole} onOpenChange={() => setEditingRole(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Edit Role</DialogTitle>
              <DialogDescription>
                Update role information (name cannot be changed)
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="grid gap-2">
                <Label>Name (read-only)</Label>
                <Input value={editingRole.name} disabled />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="edit-display-name">Display Name</Label>
                <Input
                  id="edit-display-name"
                  value={editData.display_name}
                  onChange={(e) =>
                    setEditData({ ...editData, display_name: e.target.value })
                  }
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="edit-description">Description</Label>
                <Textarea
                  id="edit-description"
                  value={editData.description}
                  onChange={(e) =>
                    setEditData({ ...editData, description: e.target.value })
                  }
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setEditingRole(null)}>
                Cancel
              </Button>
              <Button onClick={handleUpdate} disabled={updateMutation.isPending}>
                {updateMutation.isPending ? "Updating..." : "Update"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
