import { NavLink, Outlet } from "react-router-dom";

import { ADMIN_SECTIONS } from "./sections";

type AdminLayoutProps = {
  onSignOut: () => void;
};

export function AdminLayout({ onSignOut }: AdminLayoutProps) {
  return (
    <main className="admin-shell">
      <header className="admin-nav">
        <div className="admin-nav-brand">
          <p className="eyebrow">GuitarOnline</p>
          <h2>Админка</h2>
        </div>
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
        <button type="button" className="admin-signout-btn" onClick={onSignOut}>
          Выйти
        </button>
      </header>

      <section className="admin-content">
        <Outlet />
      </section>
    </main>
  );
}
