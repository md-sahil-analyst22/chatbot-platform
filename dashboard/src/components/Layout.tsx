// ────────────────────────────────────────────────────────────────────────────────────────────
// 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
// What: The frame around every page: navigation on the side, the current page in the middle.
// ────────────────────────────────────────────────────────────────────────────────────────────
// From react-router-dom — page navigation by URL: NavLink = a menu link that highlights when
//   active; Outlet = where the current page appears.
import { NavLink, Outlet } from "react-router-dom";

// <Outlet /> is where the current page appears.
export function Layout() {
  // Return the page frame:
  return (
    // The outer box holding sidebar + content.
    <div className="shell">
      {/* The sidebar. */}
      <aside className="sidebar">
        {/* The product name at the top. */}
        <div className="brand">Saathi Studio</div>
        {/* The navigation menu: */}
        <nav>
          {/* a link to the bots list ('end' = highlight only on exactly '/'), */}
          <NavLink to="/" end>
            {/* its text; */}
            Bots
          </NavLink>
          {/* a link to the API keys page, */}
          <NavLink to="/settings/api-keys">
            {/* its text and a 'Pro' badge. */}
            API keys <span className="badge">Pro</span>
          </NavLink>
        </nav>
      </aside>
      {/* The main area. */}
      <main className="content">
        {/* The current page is drawn here. */}
        <Outlet />
      </main>
    </div>
  );
}
