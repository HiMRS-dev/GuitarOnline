export type AdminSection = {
  id: string;
  label: string;
  path: string;
};

export const ADMIN_SECTIONS: AdminSection[] = [
  { id: "kpi", label: "Дашборд", path: "kpi" },
  { id: "users", label: "Пользователи", path: "users" },
  { id: "teachers", label: "Преподаватели", path: "teachers" },
  { id: "calendar", label: "Календарь", path: "calendar" },
  { id: "audit", label: "Аудит", path: "audit" },
  { id: "students", label: "Студенты", path: "students" },
  { id: "packages", label: "Пакеты", path: "packages" },
  { id: "platform", label: "Platform", path: "platform" }
];
