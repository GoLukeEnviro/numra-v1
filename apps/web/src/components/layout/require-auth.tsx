"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useLocale } from "@/i18n/context";
import { LoadingState } from "@/components/ui/states";

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  const { t } = useLocale();
  const router = useRouter();

  useEffect(() => {
    if (status === "anonymous") {
      router.replace("/login");
    }
  }, [status, router]);

  if (status === "checking") {
    return (
      <div className="flex min-h-[60vh] items-center justify-center p-6">
        <LoadingState label={t("shell.checkingSession")} />
      </div>
    );
  }

  if (status === "anonymous") {
    return null;
  }

  return <>{children}</>;
}
