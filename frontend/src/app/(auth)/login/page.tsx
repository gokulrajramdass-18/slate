"use client";

import { LoginForm } from "@/components/auth";
import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const isXsuaaEnabled = process.env.NEXT_PUBLIC_XSUAA_ENABLED === "true";

  useEffect(() => {
    // If XSUAA is enabled, redirect to the returnUrl or dashboard
    // The approuter will handle authentication
    if (isXsuaaEnabled) {
      const returnUrl = searchParams.get("returnUrl") || "/dashboard";
      console.log("[LoginPage] XSUAA enabled, redirecting to:", returnUrl);
      router.replace(returnUrl);
    }
  }, [isXsuaaEnabled, router, searchParams]);

  // If XSUAA is enabled, show loading while redirecting
  if (isXsuaaEnabled) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
          <p className="mt-4 text-muted-foreground">Redirecting to authentication...</p>
        </div>
      </div>
    );
  }

  return <LoginForm />;
}
