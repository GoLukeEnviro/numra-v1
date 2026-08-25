"use client";

import { api, type AdminUserOut, type UserRole } from "@/api/client";
import { RoleBadge, StatusBadge } from "@/components/admin/user-badges";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { useLocale } from "@/i18n/context";
import { useAsync } from "@/lib/use-async";
import { formatDateTime } from "@/lib/utils";
import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { useState, type FormEvent } from "react";

const PAGE_SIZE = 25;

type RoleFilter = "" | UserRole;
type StatusFilter = "" | "active" | "disabled";

function statusToFlag(status: StatusFilter): boolean | undefined {
  if (status === "active") return true;
  if (status === "disabled") return false;
  return undefined;
}

function UserRow({ user }: { user: AdminUserOut }) {
  const { t } = useLocale();
  return (
    <tr className="border-t border-white/10 hover:bg-white/5">
      <td className="px-3 py-3">
        <Link
          href={`/admin/users/${user.id}`}
          className="text-sm text-ivory underline-offset-2 hover:text-gold hover:underline"
        >
          {user.email}
        </Link>
      </td>
      <td className="px-3 py-3">
        <RoleBadge role={user.role} />
      </td>
      <td className="px-3 py-3">
        <StatusBadge isActive={user.is_active} />
      </td>
      <td className="whitespace-nowrap px-3 py-3 text-sm text-muted">
        {formatDateTime(user.created_at)}
      </td>
      <td className="whitespace-nowrap px-3 py-3 text-sm text-muted">
        {user.last_login_at ? formatDateTime(user.last_login_at) : t("admin.common.never")}
      </td>
      <td className="px-3 py-3 text-right text-sm text-text">{user.active_session_count}</td>
      <td className="px-3 py-3 text-right text-sm text-text">{user.people_count}</td>
      <td className="px-3 py-3 text-right text-sm text-text">{user.calculation_count}</td>
      <td className="px-3 py-3 text-right text-sm text-text">{user.report_count}</td>
      <td className="px-3 py-3 text-right text-sm text-text">{user.relationship_count}</td>
    </tr>
  );
}

function UserCard({ user }: { user: AdminUserOut }) {
  const { t } = useLocale();
  const counts: [string, number][] = [
    [t("admin.users.colSessions"), user.active_session_count],
    [t("admin.users.colPeople"), user.people_count],
    [t("admin.users.colCalculations"), user.calculation_count],
    [t("admin.users.colReports"), user.report_count],
    [t("admin.users.colRelationships"), user.relationship_count],
  ];

  return (
    <Link
      href={`/admin/users/${user.id}`}
      className="group block rounded-xl border border-white/10 bg-surface p-4 transition-colors hover:border-gold/40"
    >
      <span className="block break-all text-sm text-ivory">{user.email}</span>
      <span className="mt-2 flex flex-wrap items-center gap-1.5">
        <RoleBadge role={user.role} />
        <StatusBadge isActive={user.is_active} />
      </span>
      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
        <dt className="text-muted">{t("admin.users.colRegistered")}</dt>
        <dd className="text-right text-text">{formatDateTime(user.created_at)}</dd>
        <dt className="text-muted">{t("admin.users.colLastLogin")}</dt>
        <dd className="text-right text-text">
          {user.last_login_at ? formatDateTime(user.last_login_at) : t("admin.common.never")}
        </dd>
        {counts.map(([label, value]) => (
          <div key={label} className="col-span-2 flex justify-between">
            <dt className="text-muted">{label}</dt>
            <dd className="text-text">{value}</dd>
          </div>
        ))}
      </dl>
      <span className="mt-3 inline-flex items-center gap-1 text-xs text-muted transition-colors group-hover:text-gold">
        {t("admin.users.openDetail")}
        <ArrowRight className="h-3 w-3" aria-hidden="true" />
      </span>
    </Link>
  );
}

export default function AdminUsersPage() {
  const { t } = useLocale();
  const [searchDraft, setSearchDraft] = useState("");
  const [search, setSearch] = useState("");
  const [role, setRole] = useState<RoleFilter>("");
  const [status, setStatus] = useState<StatusFilter>("");
  const [page, setPage] = useState(1);

  // Every filter is a server query parameter — the page never narrows an already
  // fetched list client-side, so what is counted in `total` is what is filtered.
  const usersState = useAsync(
    () =>
      api.admin.users.list({
        search: search || undefined,
        role: role || undefined,
        isActive: statusToFlag(status),
        page,
        pageSize: PAGE_SIZE,
      }),
    [search, role, status, page],
  );

  function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPage(1);
    setSearch(searchDraft.trim());
  }

  const data = usersState.status === "success" ? usersState.data : null;
  const pageCount = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <div className="animate-rise-in">
      <header className="mb-6">
        <h1 className="font-serif text-3xl text-ivory">{t("admin.users.title")}</h1>
        <p className="mt-1 text-sm text-muted">{t("admin.users.subtitle")}</p>
      </header>

      <form
        onSubmit={handleSearch}
        className="mb-6 grid gap-3 rounded-xl border border-white/10 bg-surface p-4 sm:grid-cols-2 lg:grid-cols-4"
      >
        <div className="sm:col-span-2 lg:col-span-2">
          <Label htmlFor="user-search">{t("admin.users.searchLabel")}</Label>
          <Input
            id="user-search"
            type="search"
            value={searchDraft}
            placeholder={t("admin.users.searchPlaceholder")}
            onChange={(e) => setSearchDraft(e.target.value)}
          />
        </div>
        <div>
          <Label htmlFor="user-role">{t("admin.users.roleLabel")}</Label>
          <Select
            id="user-role"
            value={role}
            onChange={(e) => {
              setPage(1);
              setRole(e.target.value as RoleFilter);
            }}
          >
            <option value="">{t("admin.users.allRoles")}</option>
            <option value="USER">USER — {t("admin.users.roleUserLabel")}</option>
            <option value="ADMIN">ADMIN — {t("admin.users.roleAdminLabel")}</option>
          </Select>
        </div>
        <div>
          <Label htmlFor="user-status">{t("admin.users.statusLabel")}</Label>
          <Select
            id="user-status"
            value={status}
            onChange={(e) => {
              setPage(1);
              setStatus(e.target.value as StatusFilter);
            }}
          >
            <option value="">{t("admin.users.allStatuses")}</option>
            <option value="active">{t("admin.users.statusActive")}</option>
            <option value="disabled">{t("admin.users.statusDisabled")}</option>
          </Select>
        </div>
        <div className="sm:col-span-2 lg:col-span-4">
          <Button type="submit" variant="secondary" size="sm">
            {t("admin.users.searchSubmit")}
          </Button>
        </div>
      </form>

      {usersState.status === "loading" && <LoadingState label={t("admin.users.loading")} />}
      {usersState.status === "error" && (
        <ErrorState
          error={usersState.error}
          onRetry={usersState.reload}
          title={t("admin.common.errorTitle")}
        />
      )}

      {data && data.items.length === 0 && (
        <EmptyState title={t("admin.users.empty")} description={t("admin.users.emptyHint")} />
      )}

      {data && data.items.length > 0 && (
        <>
          {/* Phones get real cards; the table only exists from md up, and even there it
              scrolls inside its own container so the body never scrolls sideways. */}
          <div className="flex flex-col gap-3 md:hidden">
            {data.items.map((user) => (
              <UserCard key={user.id} user={user} />
            ))}
          </div>

          <div className="hidden overflow-x-auto rounded-xl border border-white/10 bg-surface md:block">
            <table className="w-full min-w-[60rem] border-collapse text-left">
              <caption className="sr-only">{t("admin.users.tableCaption")}</caption>
              <thead>
                <tr className="text-xs uppercase tracking-wide text-muted">
                  <th scope="col" className="px-3 py-3 font-medium">{t("admin.users.colEmail")}</th>
                  <th scope="col" className="px-3 py-3 font-medium">{t("admin.users.colRole")}</th>
                  <th scope="col" className="px-3 py-3 font-medium">{t("admin.users.colStatus")}</th>
                  <th scope="col" className="px-3 py-3 font-medium">{t("admin.users.colRegistered")}</th>
                  <th scope="col" className="px-3 py-3 font-medium">{t("admin.users.colLastLogin")}</th>
                  <th scope="col" className="px-3 py-3 text-right font-medium">{t("admin.users.colSessions")}</th>
                  <th scope="col" className="px-3 py-3 text-right font-medium">{t("admin.users.colPeople")}</th>
                  <th scope="col" className="px-3 py-3 text-right font-medium">{t("admin.users.colCalculations")}</th>
                  <th scope="col" className="px-3 py-3 text-right font-medium">{t("admin.users.colReports")}</th>
                  <th scope="col" className="px-3 py-3 text-right font-medium">{t("admin.users.colRelationships")}</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((user) => (
                  <UserRow key={user.id} user={user} />
                ))}
              </tbody>
            </table>
          </div>

          <nav
            aria-label={t("admin.pagination.page")}
            className="mt-4 flex flex-wrap items-center justify-between gap-3"
          >
            <p className="text-sm text-muted">
              {data.total} {t("admin.pagination.total")}
            </p>
            <div className="flex items-center gap-3">
              <Button
                variant="secondary"
                size="sm"
                disabled={data.page <= 1}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
              >
                {t("admin.pagination.prev")}
              </Button>
              <span className="text-sm text-text">
                {t("admin.pagination.page")} {data.page} / {pageCount}
              </span>
              <Button
                variant="secondary"
                size="sm"
                disabled={data.page >= pageCount}
                onClick={() => setPage((current) => current + 1)}
              >
                {t("admin.pagination.next")}
              </Button>
            </div>
          </nav>
        </>
      )}
    </div>
  );
}
