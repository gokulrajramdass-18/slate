import { useQuery } from "@tanstack/react-query";
import {
  settingsLookupsApi,
  type LookupOption,
} from "@/lib/api/settings-lookups";

/**
 * Fetch the active items of a lookup list for use in a dropdown.
 *
 * Falls back to the supplied `fallback` list if the request fails or returns
 * an empty list, so consumer dropdowns always render something.
 */
export function useLookupList(key: string, fallback: LookupOption[]) {
  const query = useQuery({
    queryKey: ["lookup-options", key],
    queryFn: () => settingsLookupsApi.getOptions(key),
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });

  const remote = query.data ?? [];
  const options = remote.length > 0 ? remote : fallback;

  return {
    options,
    isLoading: query.isLoading,
    isFallback: !query.isSuccess || remote.length === 0,
    refetch: query.refetch,
  };
}
