import { useMemo } from "react";
import type { AuthProvider } from "react-admin";
import { Admin, Resource } from "react-admin";

import { getCurrentUser } from "../features/auth/api";
import { adminPlatformDataProvider } from "./dataProvider";
import { TeachersList, TeachersShow } from "./resources/teachers";

type AdminPlatformShellProps = {
  onSignOut: () => void;
};

function resolveStatusCode(error: unknown): number | null {
  if (typeof error !== "object" || error === null) {
    return null;
  }
  const candidate = error as {
    status?: unknown;
    response?: {
      status?: unknown;
    };
  };
  if (typeof candidate.status === "number") {
    return candidate.status;
  }
  if (typeof candidate.response?.status === "number") {
    return candidate.response.status;
  }
  return null;
}

function AdminPlatformDashboard() {
  return (
    <article className="card section-page admin-platform-dashboard">
      <p className="eyebrow">React-admin Shell</p>
      <h1>Admin Platform (beta)</h1>
      <p className="summary">
        React-admin dataProvider is now connected for teachers (list/show).
        Next step (`ADM-05`) is rolling out additional resources and mutations.
      </p>
    </article>
  );
}

export function AdminPlatformShell({ onSignOut }: AdminPlatformShellProps) {
  const authProvider = useMemo<AuthProvider>(
    () => ({
      login: async () => undefined,
      logout: async () => {
        onSignOut();
      },
      checkAuth: async () => {
        const currentUser = await getCurrentUser();
        if (currentUser.role.name !== "admin") {
          onSignOut();
          throw new Error("Admin role is required");
        }
      },
      checkError: async (error: unknown) => {
        const statusCode = resolveStatusCode(error);
        if (statusCode === 401 || statusCode === 403) {
          onSignOut();
          throw new Error("Unauthorized");
        }
      },
      getIdentity: async () => {
        const currentUser = await getCurrentUser();
        return {
          id: currentUser.id,
          fullName: currentUser.email
        };
      },
      getPermissions: async () => "admin"
    }),
    [onSignOut]
  );

  return (
    <div className="admin-platform-shell">
      <Admin
        title="GuitarOnline Admin Platform"
        basename="/admin/platform"
        dashboard={AdminPlatformDashboard}
        dataProvider={adminPlatformDataProvider}
        authProvider={authProvider}
        requireAuth
        disableTelemetry
      >
        <Resource name="teachers" list={TeachersList} show={TeachersShow} />
      </Admin>
    </div>
  );
}
