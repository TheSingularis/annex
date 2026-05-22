import { useState } from "react";
import { Routes, Route, NavLink, useNavigate } from "react-router-dom";
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
  const { tokens, theme, toggle } = useTheme();
  const isMobile = useIsMobile();
  const [drawerOpen, setDrawerOpen] = useState(false);

  const navLinkStyle = (isActive: boolean): React.CSSProperties => ({
    display: "block",
    padding: isMobile ? "12px 20px" : "8px 12px",
    marginBottom: isMobile ? 0 : 4,
    borderRadius: isMobile ? 0 : 6,
    color: isActive ? tokens.navTextActive : tokens.navText,
    background: isActive ? tokens.navActive : "transparent",
    textDecoration: "none",
    fontSize: 14,
    borderBottom: isMobile ? `1px solid ${tokens.border}` : undefined,
  });

  if (isMobile) {
    return (
      <div style={{ minHeight: "100vh", fontFamily: "system-ui, sans-serif", background: tokens.bg, color: tokens.text }}>
        {/* Top bar */}
        <div style={{
          position: "sticky", top: 0, zIndex: 50,
          background: tokens.navBg, borderBottom: `1px solid ${tokens.border}`,
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "0 16px", height: 52,
        }}>
          <span style={{ fontWeight: 700, fontSize: 17, color: tokens.navTextActive }}>Annex</span>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <button
              onClick={toggle}
              style={{ background: "none", border: "none", color: tokens.navText, cursor: "pointer", fontSize: 18, padding: 4 }}
              title={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
            >
              {theme === "light" ? "🌙" : "☀️"}
            </button>
            <button
              onClick={() => setDrawerOpen(o => !o)}
              style={{ background: "none", border: `1px solid ${tokens.navText}44`, borderRadius: 6, color: tokens.navText, cursor: "pointer", fontSize: 18, padding: "4px 8px", lineHeight: 1 }}
            >
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
            <div style={{
              position: "fixed", top: 0, right: 0, bottom: 0, zIndex: 70,
              width: 220, background: tokens.navBg,
              boxShadow: "-4px 0 16px rgba(0,0,0,.2)",
              display: "flex", flexDirection: "column", paddingTop: 16,
            }}>
              <div style={{ fontWeight: 700, fontSize: 17, color: tokens.navTextActive, padding: "0 20px 16px" }}>Annex</div>
              {NAV_LINKS.map(({ to, label }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={to === "/"}
                  onClick={() => setDrawerOpen(false)}
                  style={({ isActive }) => navLinkStyle(isActive)}
                >
                  {label}
                </NavLink>
              ))}
            </div>
          </>
        )}

        {/* Bottom nav bar */}
        <nav style={{
          position: "fixed", bottom: 0, left: 0, right: 0, zIndex: 50,
          background: tokens.navBg, borderTop: `1px solid ${tokens.border}`,
          display: "flex",
        }}>
          {NAV_LINKS.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              style={({ isActive }) => ({
                flex: 1, textAlign: "center", padding: "10px 4px 8px",
                color: isActive ? tokens.navTextActive : tokens.navText,
                textDecoration: "none", fontSize: 11, fontWeight: isActive ? 600 : 400,
                borderTop: isActive ? `2px solid ${tokens.navTextActive}` : "2px solid transparent",
              })}
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
    <div style={{ display: "flex", minHeight: "100vh", fontFamily: "system-ui, sans-serif", background: tokens.bg, color: tokens.text }}>
      <nav style={{ width: 200, background: tokens.navBg, padding: "24px 16px", display: "flex", flexDirection: "column", flexShrink: 0 }}>
        <div style={{ fontWeight: 700, fontSize: 18, marginBottom: 32, color: tokens.navTextActive }}>Annex</div>
        <div style={{ flex: 1 }}>
          {NAV_LINKS.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              style={({ isActive }) => navLinkStyle(isActive)}
            >
              {label}
            </NavLink>
          ))}
        </div>
        <button
          onClick={toggle}
          title={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
          style={{
            background: "none", border: `1px solid ${tokens.navText}44`,
            borderRadius: 6, color: tokens.navText, padding: "6px 10px",
            cursor: "pointer", fontSize: 12, textAlign: "left",
          }}
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
