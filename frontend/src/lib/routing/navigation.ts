import {
  useNavigate,
  useLocation,
  useSearchParams as useReactRouterSearchParams,
  useParams,
} from 'react-router-dom';

/**
 * Wraps React Router's useNavigate with a Next.js-compatible API.
 * Provides push/replace/back/forward/refresh/prefetch and pathname.
 */
export function useRouter() {
  const navigate = useNavigate();
  const location = useLocation();

  return {
    push: (href: string) => navigate(href),
    replace: (href: string) => navigate(href, { replace: true }),
    back: () => navigate(-1),
    forward: () => navigate(1),
    refresh: () => navigate(0),
    prefetch: (_href: string) => {
      // No-op: React Router does not support prefetching the way Next.js does.
    },
    pathname: location.pathname,
  };
}

/**
 * Wraps React Router's useSearchParams with a Next.js-compatible read-only API
 * plus mutation helpers (set/delete/append) that update the URL.
 */
export function useSearchParams() {
  const [searchParams, setSearchParams] = useReactRouterSearchParams();

  return {
    get: (key: string) => searchParams.get(key),
    getAll: (key: string) => searchParams.getAll(key),
    has: (key: string) => searchParams.has(key),
    keys: () => searchParams.keys(),
    values: () => searchParams.values(),
    entries: () => searchParams.entries(),
    forEach: (
      callback: (value: string, key: string, parent: URLSearchParams) => void,
    ) => searchParams.forEach(callback),
    toString: () => searchParams.toString(),
    set: (key: string, value: string) => {
      const next = new URLSearchParams(searchParams);
      next.set(key, value);
      setSearchParams(next);
    },
    delete: (key: string) => {
      const next = new URLSearchParams(searchParams);
      next.delete(key);
      setSearchParams(next);
    },
    append: (key: string, value: string) => {
      const next = new URLSearchParams(searchParams);
      next.append(key, value);
      setSearchParams(next);
    },
  };
}

/**
 * Returns the current pathname, mirroring Next.js's usePathname hook.
 */
export function usePathname(): string {
  const location = useLocation();
  return location.pathname;
}

export { useParams, useLocation };
