"use client";

import { AdminGuard } from "@/components/layout/admin-guard";
import { AdminShell } from "@/components/layout/admin-shell";
import { usePathname } from "next/navigation";

const PUBLIC_ADMIN_PATH = "/admin/login";

/**
 * `/admin/login` is the one route under this segment that must stay reachable while
 * signed out, so it renders bare — guarding it would bounce the sign-in form to
 * itself. Exempting the single path here is simpler than splitting the segment into
 * a route group just to move one file.
 */
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  if (pathname === PUBLIC_ADMIN_PATH) {
    return <>{children}</>;
  }

  return (
    <AdminGuard>
      <AdminShell>{children}</AdminShell>
    </AdminGuard>
  );
}
