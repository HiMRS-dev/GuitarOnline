import { NavLink, Outlet } from "react-router-dom";

import { ADMIN_SECTIONS } from "./sections";

type AdminLayoutProps = {
  onSignOut: () => void;
};

export function AdminLayout({ onSignOut }: AdminLayoutProps) {
  return (
    <main className="admin-shell">
      <aside className="admin-nav">
        <p className="eyebrow">GuitarOnline</p>
        <h2>Админка</h2>
        <nav className="admin-nav-list">
          {ADMIN_SECTIONS.map((section) => (
            <NavLink
              key={section.id}
              to={`/admin/${section.path}`}
              className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}
            >
              {section.label}
            </NavLink>
          ))}
        </nav>
        <button type="button" onClick={onSignOut}>
          Выйти
        </button>
      </aside>

      <section className="admin-content">
        <Outlet />
      </section>
    </main>
  );
}
