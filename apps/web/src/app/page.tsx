"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { LoadingState } from "@/components/ui/states";

export default function RootPage() {
  const { status } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "authenticated") router.replace("/dashboard");
    if (status === "anonymous") router.replace("/login");
  }, [status, router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-6">
      <LoadingState label="Loading Numra…" />
    </div>
  );
}
