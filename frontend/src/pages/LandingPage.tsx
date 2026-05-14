import { Navigate } from 'react-router-dom';

export default function LandingPage() {
  // In all cases, redirect to dashboard
  // In XSUAA mode: AppRouter already authenticated, dashboard will load
  // In local mode: AuthGuard will redirect to /login if not authenticated
  return <Navigate to="/dashboard" replace />;
}
