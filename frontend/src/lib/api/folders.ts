import { apiClient } from "./client";

export interface Folder {
  id: string;
  name: string;
  parent_id: string | null;
  notebook_count: number;
  created: string;
  updated: string;
}

export interface FolderCreate {
  name: string;
  parent_id?: string;
}

export interface FolderUpdate {
  name?: string;
  parent_id?: string;
}

export interface Tag {
  id: string;
  name: string;
  notebook_count: number;
}

export interface TagCreate {
  name: string;
}

// ==================== Folder API ====================

export const createFolder = async (data: FolderCreate): Promise<Folder> => {
  const response = await apiClient.post("/folders", data);
  return response.data;
};

export const listFolders = async (): Promise<Folder[]> => {
  const response = await apiClient.get("/folders");
  return response.data;
};

export const getFolder = async (folderId: string): Promise<Folder> => {
  const response = await apiClient.get(`/folders/${folderId}`);
  return response.data;
};

export const updateFolder = async (
  folderId: string,
  data: FolderUpdate
): Promise<Folder> => {
  const response = await apiClient.put(`/folders/${folderId}`, data);
  return response.data;
};

export const deleteFolder = async (folderId: string): Promise<void> => {
  await apiClient.delete(`/folders/${folderId}`);
};

// ==================== Tag API ====================

export const createTag = async (data: TagCreate): Promise<Tag> => {
  const response = await apiClient.post("/folders/tags", data);
  return response.data;
};

export const listTags = async (): Promise<Tag[]> => {
  const response = await apiClient.get("/folders/tags");
  return response.data;
};

export const deleteTag = async (tagId: string): Promise<void> => {
  await apiClient.delete(`/folders/tags/${tagId}`);
};
