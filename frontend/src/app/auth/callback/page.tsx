"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuthStore } from "@/lib/stores/auth-store";
import { Loader2 } from "lucide-react";

/**
 * XSUAA OAuth2 Callback Component
 *
 * Handles the OAuth2 callback from XSUAA:
 * 1. Extracts authorization code from URL
 * 2. Exchanges code for access token
 * 3. Stores token in auth store
 * 4. Redirects to original destination or dashboard
 */
function CallbackHandler() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const authStore = useAuthStore() as any;

  useEffect(() => {
    const processCallback = async () => {
      try {
        // Get authorization code and state from URL
        const code = searchParams.get("code");
        const state = searchParams.get("state");
        const errorParam = searchParams.get("error");
        const errorDescription = searchParams.get("error_description");

        // Check for error from XSUAA
        if (errorParam) {
          throw new Error(
            errorDescription || `XSUAA error: ${errorParam}`
          );
        }

        // Validate required parameters
        if (!code) {
          throw new Error("Authorization code not found in callback URL");
        }

        if (!state) {
          throw new Error("State parameter not found in callback URL");
        }

        // Exchange code for token via auth store
        const targetUrl = await authStore.handleXSUAACallback(code, state);

        // Redirect using Next.js router (more reliable than window.location)
        console.log('[Callback] Redirecting to:', targetUrl);
        router.replace(targetUrl || '/workspaces');

      } catch (err) {
        console.error("XSUAA callback error:", err);
        setError(
          err instanceof Error ? err.message : "Authentication failed"
        );
      }
    };

    processCallback();
  }, [searchParams, authStore, router]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 to-primary-100 dark:from-gray-900 dark:to-gray-800">
        <div className="max-w-md w-full bg-white dark:bg-gray-800 shadow-lg rounded-lg p-8">
          <div className="text-center">
            <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-red-100 dark:bg-red-900/20">
              <svg
                className="h-6 w-6 text-red-600 dark:text-red-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </div>
            <h3 className="mt-4 text-lg font-medium text-gray-900 dark:text-white">
              Authentication Failed
            </h3>
            <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
              {error}
            </p>
            <button
              onClick={() => router.push("/")}
              className="mt-6 inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm bg-primary text-primary-foreground hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
            >
              Try Again
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 to-primary-100 dark:from-gray-900 dark:to-gray-800">
      <div className="text-center">
        <Loader2 className="mx-auto h-12 w-12 animate-spin text-primary" />
        <p className="mt-4 text-lg text-gray-600 dark:text-gray-300">
          Completing authentication...
        </p>
        <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
          Please wait while we log you in
        </p>
      </div>
    </div>
  );
}

/**
 * XSUAA Callback Page with Suspense Boundary
 *
 * Next.js App Router requires Suspense when using useSearchParams()
 */
export default function XSUAACallbackPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 to-primary-100 dark:from-gray-900 dark:to-gray-800">
        <div className="text-center">
          <Loader2 className="mx-auto h-12 w-12 animate-spin text-primary" />
          <p className="mt-4 text-lg text-gray-600 dark:text-gray-300">
            Loading...
          </p>
        </div>
      </div>
    }>
      <CallbackHandler />
    </Suspense>
  );
}
