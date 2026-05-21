import { apiClient } from "./client";

export interface LookupItem {
  value: string;
  label: string;
  description?: string | null;
  icon?: string | null;
  color?: string | null;
  active: boolean;
  sort_order: number;
}

export interface LookupItemUpdate {
  label?: string;
  description?: string | null;
  icon?: string | null;
  color?: string | null;
  active?: boolean;
  sort_order?: number;
}

export interface LookupList {
  title: string;
  description: string;
  items: LookupItem[];
}

export interface LookupListSummary {
  key: string;
  title: string;
  description: string;
  item_count: number;
  active_count: number;
}

export interface LookupOption {
  value: string;
  label: string;
  description?: string | null;
  icon?: string | null;
  color?: string | null;
  sort_order: number;
}

export const settingsLookupsApi = {
  list: async (): Promise<LookupListSummary[]> => {
    const { data } = await apiClient.get("/settings/lookups");
    return data;
  },

  get: async (key: string): Promise<LookupList> => {
    const { data } = await apiClient.get(`/settings/lookups/${key}`);
    return data;
  },

  getOptions: async (key: string): Promise<LookupOption[]> => {
    const { data } = await apiClient.get(`/settings/lookups/${key}/options`);
    return data;
  },

  replace: async (key: string, payload: LookupList): Promise<LookupList> => {
    const { data } = await apiClient.put(`/settings/lookups/${key}`, payload);
    return data;
  },

  addItem: async (key: string, item: LookupItem): Promise<LookupItem> => {
    const { data } = await apiClient.post(
      `/settings/lookups/${key}/items`,
      item
    );
    return data;
  },

  updateItem: async (
    key: string,
    value: string,
    patch: LookupItemUpdate
  ): Promise<LookupItem> => {
    const { data } = await apiClient.patch(
      `/settings/lookups/${key}/items/${value}`,
      patch
    );
    return data;
  },

  deleteItem: async (key: string, value: string): Promise<void> => {
    await apiClient.delete(`/settings/lookups/${key}/items/${value}`);
  },
};
