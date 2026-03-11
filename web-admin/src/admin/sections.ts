export type AdminSection = {
  id: string;
  label: string;
  path: string;
};

export const ADMIN_SECTIONS: AdminSection[] = [
  { id: "kpi", label: "Dashboard", path: "kpi" },
  { id: "users", label: "Users", path: "users" },
  { id: "teachers", label: "Teachers", path: "teachers" },
  { id: "calendar", label: "Calendar", path: "calendar" },
  { id: "audit", label: "Audit", path: "audit" },
  { id: "students", label: "Students", path: "students" },
  { id: "packages", label: "Packages", path: "packages" }
];
