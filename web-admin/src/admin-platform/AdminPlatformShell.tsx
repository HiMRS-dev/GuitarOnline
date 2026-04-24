import { useMemo } from "react";
import type { AuthProvider, DataProvider } from "react-admin";
import { Admin } from "react-admin";

import { getCurrentUser } from "../features/auth/api";

type AdminPlatformShellProps = {
  onSignOut: () => void;
};

function notImplementedDataProviderError(resource: string): Error {
  return new Error(
    `[ADM-04] DataProvider for resource "${resource}" is not connected yet.`
  );
}

const adminPlatformDataProvider: DataProvider = {
  async getList(resource, params) {
    void resource;
    void params;
    return { data: [], total: 0 };
  },
  async getOne(resource, params) {
    void params;
    throw notImplementedDataProviderError(resource);
  },
  async getMany(resource, params) {
    void resource;
    void params;
    return { data: [] };
  },
  async getManyReference(resource, params) {
    void resource;
    void params;
    return { data: [], total: 0 };
  },
  async create(resource, params) {
    void params;
    throw notImplementedDataProviderError(resource);
  },
  async update(resource, params) {
    void params;
    throw notImplementedDataProviderError(resource);
  },
  async updateMany(resource, params) {
    void params;
    throw notImplementedDataProviderError(resource);
  },
  async delete(resource, params) {
    void params;
    throw notImplementedDataProviderError(resource);
  },
  async deleteMany(resource, params) {
    void params;
    throw notImplementedDataProviderError(resource);
  }
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
        React-admin shell is mounted on an isolated route. Next step (`ADM-04`) is
        connecting the dataProvider to real API resources.
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
      />
    </div>
  );
}
