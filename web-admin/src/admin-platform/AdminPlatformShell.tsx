import { useMemo } from "react";
import type { AuthProvider } from "react-admin";
import { Admin, Resource } from "react-admin";

import { getCurrentUser } from "../features/auth/api";
import { adminPlatformDataProvider } from "./dataProvider";
import { BookingsList } from "./resources/bookings";
import { PackagesList } from "./resources/packages";
import { SlotsList } from "./resources/slots";
import { StudentsList } from "./resources/students";
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
        React-admin dataProvider is connected for teachers, students, slots,
        bookings, and packages. Student activate/deactivate and package cancel
        mutations are enabled with backend role checks.
      </p>
      <p className="summary">
        Next step (`ADM-06`) is internal SQLAdmin surface for support/debug,
        while legacy admin flow remains available for rollout safety.
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
        <Resource name="students" list={StudentsList} />
        <Resource name="slots" list={SlotsList} />
        <Resource name="bookings" list={BookingsList} />
        <Resource name="packages" list={PackagesList} />
      </Admin>
    </div>
  );
}
