import { LoginForm } from '@/components/auth/login-form';
import { Navigate } from 'react-router-dom';

export default function LoginPage() {
  // In XSUAA mode: AppRouter handles auth, redirect to dashboard
  const isXsuaaMode = typeof window !== "undefined" &&
    (window.location.port === "5001" || window.location.port === "5000" || import.meta.env.VITE_XSUAA_ENABLED === "true");

  if (isXsuaaMode) {
    return <Navigate to="/dashboard" replace />;
  }

  // Local mode: show login form
  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-blue-500/10 via-purple-500/10 to-pink-500/10">
      <div className="w-full max-w-md p-8">
        <div className="mb-8 text-center">
          <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
            Slate
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mt-2">
            Sign in to your account
          </p>
        </div>
        <LoginForm />
      </div>
    </div>
  );
}
