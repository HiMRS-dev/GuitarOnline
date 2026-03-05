export type AdminSection = {
  id: string;
  label: string;
  path: string;
};

export const ADMIN_SECTIONS: AdminSection[] = [
  { id: "teachers", label: "Teachers", path: "teachers" },
  { id: "calendar", label: "Calendar", path: "calendar" },
  { id: "students", label: "Students", path: "students" },
  { id: "packages", label: "Packages", path: "packages" },
  { id: "kpi", label: "KPI", path: "kpi" }
];
