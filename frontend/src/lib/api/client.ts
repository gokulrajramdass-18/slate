import axios, { AxiosError, AxiosRequestConfig } from "axios";
import { useAuthStore } from "@/lib/stores/auth-store";
import { API_BASE_URL } from "@/lib/config/api";

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 600000, // 10 minutes for long-running operations
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor for auth token
apiClient.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().token;
    const userId = useAuthStore.getState().user?.id;
    const isAuthenticated = useAuthStore.getState().isAuthenticated;

    console.log('[apiClient] Request interceptor:', {
      url: config.url,
      hasToken: !!token,
      userId,
      isAuthenticated,
      tokenPreview: token ? `${token.substring(0, 20)}...` : 'none'
    });

    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    // Add user ID header for multi-tenant endpoints
    // Only set if not already provided in the request
    if (!config.headers['X-User-ID']) {
      // Use user ID if available, otherwise use 'default-user' as fallback
      config.headers['X-User-ID'] = userId || 'default-user';
    }

    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for error handling and token refresh
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    console.log('[apiClient] Response error:', {
      status: error.response?.status,
      url: error.config?.url,
      method: error.config?.method,
      errorMessage: error.message
    });

    // Log validation errors for debugging
    if (error.response?.status === 422) {
      console.error("Validation error:", error.response.data);
      console.error("Request data:", error.config?.data);
      console.error("Request URL:", error.config?.url);
      console.error("Response headers:", error.response.headers);
      console.error("Full error:", error);
    }

    // Handle 401 - try to refresh token
    if (error.response?.status === 401) {
      console.log('[apiClient] Got 401, attempting token refresh...');
      const originalRequest = error.config;

      // Avoid infinite loop - don't retry if this IS the refresh request
      if (originalRequest?.url?.includes("/auth/refresh")) {
        console.log('[apiClient] Refresh request failed, logging out');
        useAuthStore.getState().logout();
        if (typeof window !== "undefined") {
          window.location.href = "/login";
        }
        return Promise.reject(error);
      }

      // Avoid retry if already retried
      if ((originalRequest as any)._retry) {
        console.log('[apiClient] Already retried, logging out');
        useAuthStore.getState().logout();
        if (typeof window !== "undefined") {
          window.location.href = "/login";
        }
        return Promise.reject(error);
      }

      (originalRequest as any)._retry = true;

      try {
        console.log('[apiClient] Refreshing token...');
        // Try to refresh the token
        await useAuthStore.getState().refreshAccessToken();

        // Retry the original request with new token
        const token = useAuthStore.getState().token;
        console.log('[apiClient] Token refreshed, retrying request with new token');
        if (originalRequest && token) {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          return apiClient(originalRequest);
        }
      } catch (refreshError) {
        console.log('[apiClient] Token refresh failed, logging out');
        // Refresh failed, logout and redirect
        useAuthStore.getState().logout();
        if (typeof window !== "undefined") {
          window.location.href = "/login";
        }
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

export { apiClient };

// Helper for multipart/form-data uploads
export const uploadConfig: AxiosRequestConfig = {
  headers: {
    "Content-Type": "multipart/form-data",
  },
};
