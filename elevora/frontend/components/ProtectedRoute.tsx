"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth-context";

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !user) {
      router.replace("/login");
    }
  }, [isLoading, user, router]);

  if (isLoading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center text-ink-600">
        Loading…
      </div>
    );
  }

  if (!user) {
    // Redirect is in flight; render nothing to avoid a flash of protected content.
    return null;
  }

  return <>{children}</>;
}
