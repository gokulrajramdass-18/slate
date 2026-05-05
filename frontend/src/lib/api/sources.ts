import { apiClient, uploadConfig } from "./client";
import type { Source, SourceCreate, SyncConfig } from "@/lib/types";

export const sourcesApi = {
  // List all sources
  list: async (params?: {
    source_type?: string;
    notebook_id?: string;
  }): Promise<Source[]> => {
    const { data } = await apiClient.get("/sources", { params });
    return data;
  },

  // Get single source
  get: async (id: string): Promise<Source> => {
    const { data } = await apiClient.get(`/sources/${id}`);
    return data;
  },

  // Create text/URL/YouTube source
  create: async (source: SourceCreate): Promise<Source> => {
    console.log("sourcesApi.create called with:", JSON.stringify(source, null, 2));
    const { data } = await apiClient.post("/sources", source);
    return data;
  },

  // Upload file source
  uploadFile: async (file: File, title?: string, notebookId?: string): Promise<Source> => {
    const formData = new FormData();
    formData.append("file", file);
    if (title) formData.append("title", title);
    if (notebookId) formData.append("notebook_id", notebookId);

    // Upload to S3/MinIO via files endpoint
    const { data: uploadResponse } = await apiClient.post("/files/upload", formData, uploadConfig);

    // Create source record from uploaded file
    // Note: asset_data will be handled by backend via connection_config
    const sourceData = {
      title: title || file.name,
      source_type: "file",
      notebook_id: notebookId || "default",
      url: uploadResponse.url,
      connection_config: {
        file_id: uploadResponse.id,
        filename: uploadResponse.filename,
        object_name: uploadResponse.object_name,
        size: uploadResponse.size,
        content_type: uploadResponse.content_type,
        uploaded_at: uploadResponse.uploaded_at,
      },
    };

    const { data } = await apiClient.post("/sources", sourceData);
    return data;
  },

  // Update source
  update: async (id: string, source: Partial<Source>): Promise<Source> => {
    const { data } = await apiClient.put(`/sources/${id}`, source);
    return data;
  },

  // Delete source
  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/sources/${id}`);
  },

  // Trigger sync for source
  sync: async (id: string): Promise<SyncConfig> => {
    const { data } = await apiClient.post(`/sources/${id}/sync`);
    return data;
  },

  // Regenerate embeddings for source
  regenerateEmbeddings: async (id: string): Promise<{ success: boolean; job_id: string; message: string }> => {
    const { data } = await apiClient.post(`/sources/${id}/regenerate-embeddings`);
    return data;
  },

  // HANA Table Source
  hanaTable: {
    testConnection: async (config: {
      host: string;
      port: number;
      database: string;
      username: string;
      password: string;
      schema?: string;
      encrypt?: boolean;
    }): Promise<{ success: boolean; message: string; server_version?: string; latency_ms?: number }> => {
      const { data } = await apiClient.post("/sources/hana-table/test-connection", {
        connection: {
          host: config.host,
          port: config.port,
          database: config.database,
          user: config.username,
          password: config.password,
          schema: config.schema,
          encrypt: config.encrypt !== false, // default to true
        }
      });
      return data;
    },

    getTables: async (config: {
      host: string;
      port: number;
      database: string;
      username: string;
      password: string;
      schema?: string;
      encrypt?: boolean;
    }): Promise<Array<{
      schema_name: string;
      table_name: string;
      table_type: string;
      record_count?: number;
      columns?: string[];
    }>> => {
      const { data } = await apiClient.post("/sources/hana-table/list-tables", {
        connection: {
          host: config.host,
          port: config.port,
          database: config.database,
          user: config.username,
          password: config.password,
          schema: config.schema,
          encrypt: config.encrypt !== false,
        },
        schema_filter: config.schema || config.username.toUpperCase(),
      });

      if (!data.success) {
        console.error("Failed to fetch HANA tables:", data.message);
        throw new Error(data.message || "Failed to fetch tables");
      }

      return data.tables || [];
    },

    getSchema: async (config: any, table: string): Promise<any> => {
      const { data } = await apiClient.post("/sources/hana-table/schema", {
        ...config,
        table,
      });
      return data;
    },

    create: async (sourceData: {
      name: string;
      notebook_id?: string;
      description?: string;
      config: any;
      sync_frequency: string;
    }): Promise<Source> => {
      const { data } = await apiClient.post("/sources/hana-table", sourceData);
      return data;
    },
  },

  // API Source
  api: {
    test: async (config: {
      endpoint: string;
      auth_type: string;
      headers?: Record<string, string>;
      auth_config?: any;
    }): Promise<{ success: boolean; message: string; preview?: any }> => {
      const { data } = await apiClient.post("/sources/api/test", config);
      return data;
    },

    initiateOAuth: async (config: {
      client_id: string;
      auth_url: string;
      scope?: string;
      redirect_uri: string;
    }): Promise<{ authorization_url: string; state: string }> => {
      const { data } = await apiClient.post("/sources/api/oauth2/authorize", config);
      return data;
    },

    create: async (sourceData: {
      title: string;
      connection_config: any;
      sync_config?: any;
    }): Promise<Source> => {
      const { data } = await apiClient.post("/sources/api", {
        ...sourceData,
        source_type: "api",
      });
      return data;
    },
  },
};
