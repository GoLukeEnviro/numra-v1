import type { deAdmin } from "@/i18n/messages/de/admin";

/** Admin console: login, dashboard, user management, audit log. Mirrors `messages/de/admin.ts` 1:1. */
export const enAdmin: Record<keyof typeof deAdmin, string> = {
  // Navigation
  "admin.nav.admin": "Admin",
  "admin.nav.console": "Admin console",
  "admin.nav.overview": "Overview",
  "admin.nav.users": "Users",
  "admin.nav.audit": "Audit log",
  "admin.nav.backToApp": "Back to the app",

  // Guard
  "admin.guard.checking": "Checking your session…",
  "admin.guard.deniedTitle": "No access",
  "admin.guard.deniedBody": "This account has no administration rights.",
  "admin.guard.backToDashboard": "Go to your dashboard",

  // Login
  "admin.login.title": "Admin access",
  "admin.login.subtitle": "Sign in with your Numra account.",
  "admin.login.hint": "This area is reserved for administrators.",
  "admin.login.email": "Email",
  "admin.login.password": "Password",
  "admin.login.submit": "Sign in",
  "admin.login.networkError": "Could not reach the server.",
  "admin.login.notAdminTitle": "No administration access",
  "admin.login.notAdminBody": "This account has no administration rights.",

  // Dashboard
  "admin.dashboard.title": "Admin overview",
  "admin.dashboard.subtitle": "Operational figures from the backend, shown unchanged.",
  "admin.dashboard.loading": "Loading figures…",
  "admin.stats.totalUsers": "Total users",
  "admin.stats.activeUsers": "Active users",
  "admin.stats.disabledUsers": "Disabled users",
  "admin.stats.registrations7": "Registrations in the last 7 days",
  "admin.stats.registrations30": "Registrations in the last 30 days",
  "admin.stats.activeSessions": "Active sessions",
  "admin.stats.totalPeople": "Profiles",
  "admin.stats.totalCalculations": "Calculations",
  "admin.stats.totalReports": "Reports",

  // User list
  "admin.users.title": "Users",
  "admin.users.subtitle": "Search, filter and manage accounts.",
  "admin.users.loading": "Loading users…",
  "admin.users.searchLabel": "Search by email",
  "admin.users.searchPlaceholder": "e.g. name@example.com",
  "admin.users.searchSubmit": "Search",
  "admin.users.roleLabel": "Role",
  "admin.users.statusLabel": "Status",
  "admin.users.allRoles": "All roles",
  "admin.users.allStatuses": "Any status",
  "admin.users.roleUserLabel": "Standard account",
  "admin.users.roleAdminLabel": "Administrator",
  "admin.users.statusActive": "Active",
  "admin.users.statusDisabled": "Disabled",
  "admin.users.tableCaption": "User accounts",
  "admin.users.colEmail": "Email",
  "admin.users.colRole": "Role",
  "admin.users.colStatus": "Status",
  "admin.users.colRegistered": "Registered on",
  "admin.users.colLastLogin": "Last login",
  "admin.users.colSessions": "Active sessions",
  "admin.users.colPeople": "Profiles",
  "admin.users.colCalculations": "Calculations",
  "admin.users.colReports": "Reports",
  "admin.users.colRelationships": "Relationships",
  "admin.users.empty": "No users found",
  "admin.users.emptyHint": "Adjust the search or the filters.",
  "admin.users.openDetail": "Open account",

  // Pagination
  "admin.pagination.total": "results in total",
  "admin.pagination.page": "Page",
  "admin.pagination.prev": "Previous",
  "admin.pagination.next": "Next",

  // User detail
  "admin.userDetail.title": "User account",
  "admin.userDetail.loading": "Loading the account…",
  "admin.userDetail.back": "Back to the user list",
  "admin.userDetail.metadataTitle": "Account data",
  "admin.userDetail.usageTitle": "Usage",
  "admin.userDetail.colId": "User ID",
  "admin.userDetail.actionsTitle": "Actions",
  "admin.userDetail.disable": "Disable account",
  "admin.userDetail.enable": "Enable account",
  "admin.userDetail.revoke": "Revoke all sessions",
  "admin.userDetail.selfLockHint":
    "You cannot disable your own account — the backend rejects it as well.",
  "admin.userDetail.disableConfirmTitle": "Disable this account?",
  "admin.userDetail.disableConfirmBody":
    "The person will no longer be able to sign in and is signed out on every device.",
  "admin.userDetail.enableConfirmTitle": "Enable this account?",
  "admin.userDetail.enableConfirmBody": "The person will be able to sign in again.",
  "admin.userDetail.revokeConfirmTitle": "Revoke all sessions?",
  "admin.userDetail.revokeConfirmBody":
    "Every device of this person is signed out. The account itself stays active.",
  "admin.userDetail.disableSuccess": "The account has been disabled.",
  "admin.userDetail.enableSuccess": "The account has been enabled.",
  "admin.userDetail.revokeSuccess": "All sessions have been revoked.",

  // Dialog
  "admin.dialog.confirm": "Confirm",
  "admin.dialog.cancel": "Cancel",

  // Audit log
  "admin.audit.title": "Audit log",
  "admin.audit.subtitle": "Recorded administration events.",
  "admin.audit.loading": "Loading events…",
  "admin.audit.actionLabel": "Action",
  "admin.audit.allActions": "All actions",
  "admin.audit.targetLabel": "Target user ID",
  "admin.audit.targetPlaceholder": "UUID",
  "admin.audit.apply": "Apply filters",
  "admin.audit.reset": "Reset",
  "admin.audit.tableCaption": "Audit events",
  "admin.audit.colTime": "Timestamp",
  "admin.audit.colAction": "Action",
  "admin.audit.colActor": "Actor ID",
  "admin.audit.colTarget": "Target ID",
  "admin.audit.colMetadata": "Metadata",
  "admin.audit.noMetadata": "None",
  "admin.audit.empty": "No events found",
  "admin.audit.emptyHint": "Nothing was recorded for these filters.",

  // Shared
  "admin.common.retry": "Try again",
  "admin.common.never": "Never",
  "admin.common.errorTitle": "Something went wrong",
};
