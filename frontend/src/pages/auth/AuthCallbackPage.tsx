import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "@/lib/stores/auth-store";

export default function AuthCallbackPage() {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const checkXsuaaSession = useAuthStore((state) => state.checkXsuaaSession);

  useEffect(() => {
    const handleCallback = async () => {
      try {
        // Check for XSUAA session after login redirect
        const hasSession = await checkXsuaaSession();

        if (hasSession) {
          // Redirect to dashboard
          navigate("/dashboard", { replace: true });
        } else {
          // No session found, redirect to login
          setError("Authentication failed. Please try again.");
          setTimeout(() => {
            navigate("/", { replace: true });
          }, 2000);
        }
      } catch (err) {
        console.error("Auth callback error:", err);
        setError("Authentication error. Redirecting...");
        setTimeout(() => {
          navigate("/", { replace: true });
        }, 2000);
      }
    };

    handleCallback();
  }, [navigate, checkXsuaaSession]);

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <p className="text-red-500">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="text-center">
        <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-current border-r-transparent"></div>
        <p className="mt-4 text-muted-foreground">Completing authentication...</p>
      </div>
    </div>
  );
}
