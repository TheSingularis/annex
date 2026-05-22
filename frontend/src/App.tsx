import { Routes, Route, NavLink } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Review from "./pages/Review";
import Settings from "./pages/Settings";

export default function App() {
  return (
    <div style={{ display: "flex", minHeight: "100vh", fontFamily: "system-ui, sans-serif" }}>
      <nav style={{ width: 200, background: "#1a1a2e", color: "#eee", padding: "24px 16px" }}>
        <div style={{ fontWeight: 700, fontSize: 18, marginBottom: 32, color: "#fff" }}>
          Annex
        </div>
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
              color: isActive ? "#fff" : "#aaa",
              background: isActive ? "#16213e" : "transparent",
              textDecoration: "none",
              fontSize: 14,
            })}
          >
            {label}
          </NavLink>
        ))}
      </nav>

      <main style={{ flex: 1, padding: 32, background: "#f8f9fa" }}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/review" element={<Review />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  );
}
