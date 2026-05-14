import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { searchApi } from "@/lib/api/search";
import { workspacesApi } from "@/lib/api/workspaces";
import { Card, CardContent } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { Search, Loader2, Bookmark } from "lucide-react";
import { toast } from "sonner";
import { SearchBar } from "@/components/search/search-bar";
import { StrategyGrid } from "@/components/search/strategy-selector";
import { StrategyOptions } from "@/components/search/strategy-options";
import { FilterPanel } from "@/components/search/filter-panel";
import { ResultCard } from "@/components/search/result-card";
import type { SearchStrategy, SearchResult, SearchRequest, UnifiedSearchRequest, UnifiedSearchResult } from "@/lib/types";

export default function SearchPage() {
  const navigate = useNavigate();
  const [strategy, setStrategy] = useState<SearchStrategy>("hybrid");
  const [strategyConfig, setStrategyConfig] = useState<Record<string, any>>({});
  const [filters, setFilters] = useState<SearchRequest["filters"]>();
  const [results, setResults] = useState<SearchResult[] | UnifiedSearchResult[]>([]);
  const [rememberSettings, setRememberSettings] = useState(false);
  const [useUnifiedSearch, setUseUnifiedSearch] = useState(true);
  const [bookmarkBoost, setBookmarkBoost] = useState(1.5);
  const [lastQuery, setLastQuery] = useState<string>("");
  const [searchSources, setSearchSources] = useState<{ main_search: number; bookmarks: number }>({ main_search: 0, bookmarks: 0 });

  const { data: notebooks } = useQuery({
    queryKey: ["notebooks"],
    queryFn: () => workspacesApi.list(),
  });

  const searchMutation = useMutation({
    mutationFn: async (request: SearchRequest | UnifiedSearchRequest) => {
      if (useUnifiedSearch && "include_bookmarks" in request) {
        return searchApi.unifiedSearch(request as UnifiedSearchRequest);
      }
      return { results: await searchApi.search(request as SearchRequest), sources: null };
    },
    onSuccess: (data) => {
      if (data && typeof data === 'object' && 'results' in data && Array.isArray(data.results)) {
        setResults(data.results);
        if ('sources' in data && data.sources) {
          setSearchSources(data.sources);
          toast.success(
            `Found ${data.results.length} results (${data.sources.main_search} from search, ${data.sources.bookmarks} bookmarked)`
          );
        } else {
          toast.success(`Found ${data.results.length} results`);
        }
      } else if (Array.isArray(data)) {
        setResults(data);
        toast.success(`Found ${data.length} results`);
      }

      if (rememberSettings) {
        localStorage.setItem("searchStrategy", strategy);
        localStorage.setItem("searchConfig", JSON.stringify(strategyConfig));
        localStorage.setItem("useUnifiedSearch", useUnifiedSearch.toString());
      }
    },
    onError: () => {
      toast.error("Search failed");
    },
  });

  const handleSearch = (query: string, searchStrategy: SearchStrategy) => {
    setLastQuery(query);

    if (useUnifiedSearch) {
      const unifiedRequest: UnifiedSearchRequest = {
        query,
        strategy: searchStrategy,
        filters,
        limit: 20,
        include_bookmarks: true,
        bookmark_boost: bookmarkBoost,
        config_override: strategyConfig,
      };
      searchMutation.mutate(unifiedRequest);
    } else {
      const request: SearchRequest = {
        query,
        strategy: searchStrategy,
        filters,
        limit: 20,
        config_override: strategyConfig,
      };
      searchMutation.mutate(request);
    }
  };

  const handleOpenSource = (sourceId: string) => {
    navigate(`/sources/${sourceId}`);
  };

  return (
    <div className="p-6 h-full overflow-auto">
      <div className="space-y-6 max-w-7xl mx-auto">
      <div className="animate-fade-in-up">
        <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 bg-clip-text text-transparent">Search</h1>
        <p className="text-gray-500 dark:text-gray-400">
          Search across all your sources with multiple strategies
        </p>
      </div>

      <Card className="animate-fade-in-up animation-delay-200">
        <CardContent className="pt-6 space-y-4">
          <SearchBar
            onSearch={handleSearch}
            isLoading={searchMutation.isPending}
            strategy={strategy}
          />

          <Separator />

          <div className="flex items-center gap-4 flex-wrap">
            <FilterPanel
              filters={filters}
              onFiltersChange={setFilters}
              notebooks={notebooks}
            />
            <div className="flex items-center gap-4 ml-auto">
              <div className="flex items-center gap-2">
                <Switch
                  id="unified-search"
                  checked={useUnifiedSearch}
                  onCheckedChange={setUseUnifiedSearch}
                />
                <Label htmlFor="unified-search" className="text-sm cursor-pointer flex items-center gap-1">
                  <Bookmark className="w-3.5 h-3.5" />
                  Include Bookmarks
                </Label>
              </div>
              <div className="flex items-center gap-2">
                <Switch
                  id="remember-settings"
                  checked={rememberSettings}
                  onCheckedChange={setRememberSettings}
                />
                <Label htmlFor="remember-settings" className="text-sm cursor-pointer">
                  Remember settings
                </Label>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <div>
        <h2 className="text-lg font-semibold mb-3">Search Strategy</h2>
        <StrategyGrid value={strategy} onChange={setStrategy} />
      </div>

      <StrategyOptions
        strategy={strategy}
        config={strategyConfig}
        onChange={setStrategyConfig}
      />

      {results.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
                Search Results
              </h2>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                Found <span className="font-semibold text-primary">{results.length}</span> results for{" "}
                <span className="font-semibold">"{lastQuery}"</span> using{" "}
                <span className="font-semibold capitalize">{strategy.replace('_', ' ')}</span> strategy
                {useUnifiedSearch && searchSources && (
                  <>
                    {" · "}
                    <span className="text-xs">
                      {searchSources.main_search} from search, {searchSources.bookmarks} bookmarked
                    </span>
                  </>
                )}
              </p>
            </div>
          </div>

          <div className="space-y-3">
            {results.map((result) => {
              const isUnifiedResult = "is_bookmarked" in result;
              return (
                <div key={result.id} className="relative">
                  {isUnifiedResult && result.is_bookmarked && (
                    <div className="absolute -left-2 top-3 z-10">
                      <Badge variant="secondary" className="bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200 text-xs px-1.5 py-0.5">
                        <Bookmark className="w-3 h-3 fill-current" />
                      </Badge>
                    </div>
                  )}
                  <ResultCard
                    result={result}
                    onOpen={handleOpenSource}
                  />
                </div>
              );
            })}
          </div>
        </div>
      )}

      {searchMutation.isPending && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Loader2 className="w-12 h-12 text-primary-600 animate-spin mb-4" />
            <p className="text-gray-500 text-center">Searching...</p>
          </CardContent>
        </Card>
      )}

      {!searchMutation.isPending && results.length === 0 && !lastQuery && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Search className="w-12 h-12 text-gray-400 mb-4" />
            <p className="text-gray-500 text-center font-medium">Start searching your sources</p>
            <p className="text-sm text-gray-400 text-center mt-2">
              Enter a query above to search across all your content
            </p>
          </CardContent>
        </Card>
      )}

      {!searchMutation.isPending && results.length === 0 && lastQuery && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Search className="w-12 h-12 text-gray-400 mb-4" />
            <p className="text-gray-500 text-center font-medium">No results found</p>
            <p className="text-sm text-gray-400 text-center mt-2">
              Try adjusting your search query or filters
            </p>
          </CardContent>
        </Card>
      )}
      </div>
    </div>
  );
}
