import { Routes, Route, NavLink } from "react-router-dom";
import { useTheme } from "./lib/ThemeContext";
import Dashboard from "./pages/Dashboard";
import Review from "./pages/Review";
import Settings from "./pages/Settings";

export default function App() {
  const { tokens, theme, toggle } = useTheme();

  return (
    <div style={{ display: "flex", minHeight: "100vh", fontFamily: "system-ui, sans-serif", background: tokens.bg, color: tokens.text }}>
      <nav style={{ width: 200, background: tokens.navBg, padding: "24px 16px", display: "flex", flexDirection: "column" }}>
        <div style={{ fontWeight: 700, fontSize: 18, marginBottom: 32, color: tokens.navTextActive }}>
          Annex
        </div>

        <div style={{ flex: 1 }}>
          {[
            { to: "/", label: "Dashboard" },
            { to: "/review", label: "Needs Review" },
            { to: "/settings", label: "Settings" },
          ].map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              style={({ isActive }) => ({
                display: "block",
                padding: "8px 12px",
                marginBottom: 4,
                borderRadius: 6,
                color: isActive ? tokens.navTextActive : tokens.navText,
                background: isActive ? tokens.navActive : "transparent",
                textDecoration: "none",
                fontSize: 14,
              })}
            >
              {label}
            </NavLink>
          ))}
        </div>

        <button
          onClick={toggle}
          title={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
          style={{
            background: "none",
            border: `1px solid ${tokens.navText}44`,
            borderRadius: 6,
            color: tokens.navText,
            padding: "6px 10px",
            cursor: "pointer",
            fontSize: 12,
            textAlign: "left",
          }}
        >
          {theme === "light" ? "Dark mode" : "Light mode"}
        </button>
      </nav>

      <main style={{ flex: 1, padding: 32 }}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/review" element={<Review />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  );
}
