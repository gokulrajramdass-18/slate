import { useQuery } from "@tanstack/react-query";
import { searchApi } from "@/lib/api/search";
import type { UnifiedSearchRequest, UnifiedSearchResult } from "@/lib/types";

interface UseUnifiedSearchOptions {
  enabled?: boolean;
  staleTime?: number;
}

export function useUnifiedSearch(
  request: UnifiedSearchRequest,
  options?: UseUnifiedSearchOptions
) {
  return useQuery({
    queryKey: ["unified-search", request],
    queryFn: async () => {
      const response = await searchApi.unifiedSearch(request);
      return response;
    },
    enabled: options?.enabled !== false && !!request.query,
    staleTime: options?.staleTime || 5 * 60 * 1000, // 5 minutes default
  });
}

export function useUnifiedSearchResults(
  request: UnifiedSearchRequest,
  options?: UseUnifiedSearchOptions
) {
  const query = useUnifiedSearch(request, options);

  return {
    ...query,
    results: query.data?.results || [],
    totalResults: query.data?.total_results || 0,
    sources: query.data?.sources || { main_search: 0, bookmarks: 0 },
    metadata: query.data?.metadata || {},
  };
}
