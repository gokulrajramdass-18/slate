import { apiClient } from "./client";
import type {
  Microsite,
  MicrositeTemplate,
  MicrositeContent,
  MicrositeVersion,
  MicrositeGenerateRequest,
  MicrositeGenerateResponse,
  MicrositeContentUpdate,
  ModerationReport,
  PublishRequest,
  PublishResponse,
  AccessCheckResponse,
  ActiveVersionResponse,
} from "@/lib/types";

export const micrositesApi = {
  // ====== CRUD ======

  list: async (): Promise<Microsite[]> => {
    const { data } = await apiClient.get("/microsites");
    return data;
  },

  get: async (micrositeId: string): Promise<Microsite> => {
    const { data } = await apiClient.get(`/microsites/${micrositeId}`);
    return data;
  },

  // ====== Templates ======

  listTemplates: async (params?: {
    category?: string;
    is_custom?: boolean;
  }): Promise<MicrositeTemplate[]> => {
    const { data } = await apiClient.get("/microsites/templates", { params });
    return data.templates || [];
  },

  getTemplate: async (id: string): Promise<MicrositeTemplate> => {
    const { data } = await apiClient.get(`/microsites/templates/${id}`);
    return data;
  },

  // ====== Generation ======

  generate: async (
    micrositeId: string,
    request: MicrositeGenerateRequest
  ): Promise<MicrositeGenerateResponse> => {
    const { data } = await apiClient.post(
      `/microsites/${micrositeId}/generate`,
      request
    );
    return data;
  },

  // ====== Content ======

  getContent: async (micrositeId: string): Promise<{
    sections: MicrositeContent[];
    template: MicrositeTemplate | null;
    custom_css: string | null;
  }> => {
    const { data } = await apiClient.get(
      `/microsites/${micrositeId}/content`
    );
    return data;
  },

  updateContent: async (
    micrositeId: string,
    update: MicrositeContentUpdate
  ): Promise<{ updated_sections: MicrositeContent[]; new_version: number }> => {
    const { data } = await apiClient.put(
      `/microsites/${micrositeId}/content`,
      update
    );
    return data;
  },

  // ====== Preview ======

  getPreviewUrl: (micrositeId: string, version?: number): string => {
    const base = apiClient.defaults.baseURL || "";
    const versionParam = version ? `?version=${version}` : "";
    return `${base}/microsites/${micrositeId}/preview${versionParam}`;
  },

  getPreviewHtml: async (
    micrositeId: string,
    version?: number
  ): Promise<string> => {
    const params = version ? { version } : {};
    const { data } = await apiClient.get(
      `/microsites/${micrositeId}/preview`,
      { params, responseType: "text" }
    );
    return data;
  },

  // ====== Moderation ======

  moderate: async (
    micrositeId: string,
    sectionIds?: string[]
  ): Promise<ModerationReport> => {
    const { data } = await apiClient.post(
      `/microsites/${micrositeId}/moderate`,
      sectionIds ? { sections: sectionIds } : {}
    );
    return data;
  },

  getModerationHistory: async (
    micrositeId: string
  ): Promise<{ logs: any[]; summary: Record<string, any> }> => {
    const { data } = await apiClient.get(
      `/microsites/${micrositeId}/moderation-history`
    );
    return data;
  },

  // ====== Versions ======

  listVersions: async (micrositeId: string): Promise<MicrositeVersion[]> => {
    const { data } = await apiClient.get(
      `/microsites/${micrositeId}/versions`
    );
    return data.versions || [];
  },

  rollback: async (
    micrositeId: string,
    versionNumber: number
  ): Promise<{ microsite: any; restored_content: MicrositeContent[] }> => {
    const { data } = await apiClient.post(
      `/microsites/${micrositeId}/rollback`,
      { version_number: versionNumber }
    );
    return data;
  },

  // ====== Status Management ======

  publish: async (
    micrositeId: string,
    request?: PublishRequest
  ): Promise<PublishResponse> => {
    const { data } = await apiClient.post(
      `/microsites/${micrositeId}/publish`,
      request || {}
    );
    return data;
  },

  unpublish: async (micrositeId: string): Promise<void> => {
    await apiClient.post(`/microsites/${micrositeId}/unpublish`);
  },

  block: async (micrositeId: string, reason: string): Promise<void> => {
    await apiClient.post(`/microsites/${micrositeId}/block`, { reason });
  },

  checkAccess: async (micrositeId: string): Promise<AccessCheckResponse> => {
    const { data } = await apiClient.get(
      `/microsites/${micrositeId}/access-check`
    );
    return data;
  },

  getActiveVersion: async (
    micrositeId: string
  ): Promise<ActiveVersionResponse> => {
    const { data } = await apiClient.get(
      `/microsites/${micrositeId}/active-version`
    );
    return data;
  },
};
