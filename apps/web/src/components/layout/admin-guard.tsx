"use client";

import { LinkButton } from "@/components/ui/link-button";
import { LoadingState } from "@/components/ui/states";
import { useLocale } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";
import { ShieldAlert } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

/**
 * Gates the admin console for `/admin`, `/admin/users`, `/admin/users/[id]` and
 * `/admin/audit`. `/admin/login` deliberately renders outside this guard (see
 * `app/admin/layout.tsx`), otherwise the sign-in form would redirect to itself.
 *
 * IMPORTANT: this is NOT the security boundary. It only decides what a browser
 * bothers to render. Authorization is enforced server-side by `require_admin` on
 * the FastAPI admin router — a USER session gets 403 and an anonymous one 401 on
 * every `/v1/admin/*` call, no matter what this component does. Never move an
 * authorization decision here.
 */
export function AdminGuard({ children }: { children: React.ReactNode }) {
  const { status, user } = useAuth();
  const router = useRouter();
  const { t } = useLocale();

  useEffect(() => {
    if (status === "anonymous") {
      router.replace("/admin/login");
    }
  }, [status, router]);

  if (status === "checking") {
    return (
      <div className="flex min-h-[60vh] items-center justify-center p-6">
        <LoadingState label={t("admin.guard.checking")} />
      </div>
    );
  }

  // Nothing is rendered while the redirect is in flight — an anonymous visitor
  // must never see admin chrome, not even for a frame.
  if (status === "anonymous") {
    return null;
  }

  if (user?.role !== "ADMIN") {
    return (
      <div className="flex min-h-[60vh] items-center justify-center p-6">
        <div
          role="alert"
          className="flex max-w-md flex-col items-start gap-3 rounded-xl border border-white/10 bg-surface p-6 shadow-elevated"
        >
          <span className="flex items-center gap-2 text-gold">
            <ShieldAlert className="h-5 w-5" aria-hidden="true" />
            <h1 className="font-serif text-lg text-ivory">{t("admin.guard.deniedTitle")}</h1>
          </span>
          <p className="text-sm text-text">{t("admin.guard.deniedBody")}</p>
          <LinkButton href="/dashboard" variant="secondary" size="sm">
            {t("admin.guard.backToDashboard")}
          </LinkButton>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
