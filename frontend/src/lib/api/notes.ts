import { apiClient } from './client';

export interface Note {
  id: string;
  title: string;
  content: string;
  content_html: string | null;
  notebook_id?: string;
  tags: string[];
  linked_notes: Array<{ id: string; title: string }>;
  backlinks: Array<{ id: string; title: string }>;
  is_bookmarked?: boolean;
  created: string;
  updated: string;
}

export interface NoteCreate {
  title: string;
  content: string;
  content_html?: string | null;
  notebook_id?: string;
  tags?: string[];
  linked_note_ids?: string[];
}

export interface NoteUpdate {
  title?: string;
  content?: string;
  content_html?: string | null;
  tags?: string[];
}

export const notesApi = {
  // List notes
  list: async (notebookId?: string): Promise<Note[]> => {
    const params = notebookId ? { notebook_id: notebookId } : {};
    const response = await apiClient.get('/notes', { params });
    return response.data;
  },

  // Get single note
  get: async (noteId: string): Promise<Note> => {
    const response = await apiClient.get(`/notes/${noteId}`);
    return response.data;
  },

  // Create note
  create: async (data: NoteCreate): Promise<Note> => {
    const response = await apiClient.post('/notes', data);
    return response.data;
  },

  // Update note
  update: async (noteId: string, data: NoteUpdate): Promise<Note> => {
    const response = await apiClient.put(`/notes/${noteId}`, data);
    return response.data;
  },

  // Delete note
  delete: async (noteId: string): Promise<void> => {
    await apiClient.delete(`/notes/${noteId}`);
  },

  // Link notes
  addLink: async (noteId: string, targetNoteId: string): Promise<void> => {
    await apiClient.post(`/notes/${noteId}/links`, { target_note_id: targetNoteId });
  },

  // Remove link
  removeLink: async (noteId: string, targetNoteId: string): Promise<void> => {
    await apiClient.delete(`/notes/${noteId}/links/${targetNoteId}`);
  },

  // Export single note as Markdown
  exportMarkdown: async (noteId: string): Promise<Blob> => {
    const response = await apiClient.get(`/notes/${noteId}/export/markdown`, {
      responseType: 'blob',
    });
    return response.data;
  },

  // Export single note as PDF
  exportPdf: async (noteId: string): Promise<Blob> => {
    const response = await apiClient.get(`/notes/${noteId}/export/pdf`, {
      responseType: 'blob',
    });
    return response.data;
  },

  // Export multiple notes as Markdown
  exportMultipleMarkdown: async (noteIds: string[]): Promise<Blob> => {
    const response = await apiClient.post('/notes/export/markdown', noteIds, {
      responseType: 'blob',
    });
    return response.data;
  },

  // Export multiple notes as PDF
  exportMultiplePdf: async (noteIds: string[]): Promise<Blob> => {
    const response = await apiClient.post('/notes/export/pdf', noteIds, {
      responseType: 'blob',
    });
    return response.data;
  },
};

// Helper function to download blob as file
export const downloadBlob = (blob: Blob, filename: string) => {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
};
