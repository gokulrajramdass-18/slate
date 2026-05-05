"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/lib/stores/auth-store";

export default function Home() {
  const router = useRouter();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  // Redirect authenticated users to dashboard
  useEffect(() => {
    if (isAuthenticated) {
      router.replace("/dashboard");
    }
  }, [isAuthenticated, router]);
  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-4 relative overflow-hidden">
      {/* Animated background gradient */}
      <div className="fixed inset-0 -z-10">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 via-purple-500/5 to-pink-500/5 animate-gradient-shift" />
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl animate-pulse-slow" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl animate-pulse-slow animation-delay-2000" />
      </div>

      {/* Logo in bottom left corner */}
      <div className="fixed bottom-8 left-8 text-4xl font-bold text-white/80 animate-fade-in animation-delay-1000">
        W
      </div>

      <main className="container flex max-w-4xl flex-col items-center gap-8 text-center">
        <div className="space-y-4 animate-fade-in-up">
          <h1 className="text-4xl font-bold tracking-tight sm:text-6xl bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 bg-clip-text text-transparent animate-gradient-shift">
            Slate
          </h1>
          <p className="text-xl text-muted-foreground sm:text-2xl animate-fade-in-up animation-delay-200">
            Your intelligent research workspace with privacy at its core
          </p>
        </div>

        <div className="space-y-2 animate-fade-in-up animation-delay-400">
          <p className="text-lg text-muted-foreground max-w-2xl">
            Process multi-modal content, perform semantic search, and chat with AI
            using your research as context. All data stays on your infrastructure.
          </p>
        </div>

        <div className="flex flex-col gap-4 sm:flex-row animate-fade-in-up animation-delay-600">
          <Button asChild size="lg" className="transition-all hover:scale-105 hover:shadow-lg">
            <Link href="/workspaces">Get Started</Link>
          </Button>
          <Button asChild variant="outline" size="lg" className="transition-all hover:scale-105 hover:shadow-lg">
            <Link href="/login">Sign In</Link>
          </Button>
        </div>

        <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-3 text-left">
          <div className="rounded-lg border bg-card p-6 transition-all hover:scale-105 hover:shadow-xl hover:border-blue-500/50 animate-fade-in-up animation-delay-800">
            <h3 className="font-semibold mb-2">Multi-Modal Processing</h3>
            <p className="text-sm text-muted-foreground">
              Process PDFs, videos, audio, web pages, HANA tables, and APIs
            </p>
          </div>
          <div className="rounded-lg border bg-card p-6 transition-all hover:scale-105 hover:shadow-xl hover:border-purple-500/50 animate-fade-in-up animation-delay-1000">
            <h3 className="font-semibold mb-2">Advanced Search</h3>
            <p className="text-sm text-muted-foreground">
              Keyword, vector, hybrid, and agentic RAG search strategies
            </p>
          </div>
          <div className="rounded-lg border bg-card p-6 transition-all hover:scale-105 hover:shadow-xl hover:border-pink-500/50 animate-fade-in-up animation-delay-1200">
            <h3 className="font-semibold mb-2">AI Chat</h3>
            <p className="text-sm text-muted-foreground">
              Chat with multiple AI providers using your research as context
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
