// ────────────────────────────────────────────────────────────────────────────────────────────
// 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
// What: The frame around every page: navigation on the side, the current page in the middle.
// ────────────────────────────────────────────────────────────────────────────────────────────
import { NavLink, Outlet } from "react-router-dom";

// <Outlet /> is where the current page appears.
export function Layout() {
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">Saathi Studio</div>
        <nav>
          <NavLink to="/" end>
            Bots
          </NavLink>
          <NavLink to="/settings/api-keys">
            API keys <span className="badge">Pro</span>
          </NavLink>
        </nav>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
