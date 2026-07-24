import { useState } from "react";
import { Routes, Route, NavLink } from "react-router-dom";
import { useTheme } from "./lib/ThemeContext";
import { useIsMobile } from "./lib/useIsMobile";
import Dashboard from "./pages/Dashboard";
import Review from "./pages/Review";
import Settings from "./pages/Settings";

const NAV_LINKS = [
  { to: "/", label: "Dashboard" },
  { to: "/review", label: "Needs Review" },
  { to: "/settings", label: "Settings" },
];

export default function App() {
  const { theme, toggle } = useTheme();
  const isMobile = useIsMobile();
  const [drawerOpen, setDrawerOpen] = useState(false);

  if (isMobile) {
    return (
      <div style={{ minHeight: "100vh" }}>
        {/* Top bar */}
        <div className="nav-surface" style={{
          position: "sticky", top: 0, zIndex: 50,
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "0 16px", height: 52,
        }}>
          <span className="brand" style={{ fontSize: 17 }}>Annex</span>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <button
              className="nav-icon-btn"
              onClick={toggle}
              title={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
            >
              {theme === "light" ? "🌙" : "☀️"}
            </button>
            <button className="nav-icon-btn" onClick={() => setDrawerOpen(o => !o)}>
              ☰
            </button>
          </div>
        </div>

        {/* Drawer overlay */}
        {drawerOpen && (
          <>
            <div
              onClick={() => setDrawerOpen(false)}
              style={{ position: "fixed", inset: 0, zIndex: 60, background: "rgba(0,0,0,.4)" }}
            />
            <div className="nav-surface" style={{
              position: "fixed", top: 0, right: 0, bottom: 0, zIndex: 70,
              width: 220,
              boxShadow: "-4px 0 16px rgba(0,0,0,.2)",
              display: "flex", flexDirection: "column", paddingTop: 16,
            }}>
              <div className="brand" style={{ fontSize: 17, padding: "0 20px 16px" }}>Annex</div>
              {NAV_LINKS.map(({ to, label }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={to === "/"}
                  onClick={() => setDrawerOpen(false)}
                  className={({ isActive }) => `nav-link nav-link--drawer${isActive ? " active" : ""}`}
                >
                  {label}
                </NavLink>
              ))}
            </div>
          </>
        )}

        {/* Bottom nav bar */}
        <nav className="nav-surface" style={{
          position: "fixed", bottom: 0, left: 0, right: 0, zIndex: 50,
          display: "flex",
        }}>
          {NAV_LINKS.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) => `nav-link nav-link--tab${isActive ? " active" : ""}`}
            >
              {label === "Needs Review" ? "Review" : label}
            </NavLink>
          ))}
        </nav>

        <main style={{ padding: "16px 16px 72px" }}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/review" element={<Review />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
      </div>
    );
  }

  // Desktop layout
  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      <nav className="nav-surface" style={{ width: 200, padding: "24px 16px", display: "flex", flexDirection: "column", flexShrink: 0 }}>
        <div className="brand" style={{ fontSize: 18, marginBottom: 32 }}>Annex</div>
        <div style={{ flex: 1 }}>
          {NAV_LINKS.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
            >
              {label}
            </NavLink>
          ))}
        </div>
        <button
          className="nav-icon-btn"
          onClick={toggle}
          title={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
          style={{ fontSize: 12, textAlign: "left", padding: "6px 10px" }}
        >
          {theme === "light" ? "Dark mode" : "Light mode"}
        </button>
      </nav>

      <main style={{ flex: 1, padding: 32, minWidth: 0 }}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/review" element={<Review />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  );
}
