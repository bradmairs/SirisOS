import { useCallback, useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Menu } from "lucide-react";
import { onUnauthorised, session } from "./api/client";
import { Dock } from "./components/Dock";
import { LogoMark } from "./components/Logo";
import { Sidebar } from "./components/Sidebar";
import { Wallpaper } from "./components/Wallpaper";
import { Assistant } from "./screens/Assistant";
import { Brain } from "./screens/Brain";
import { Engineering } from "./screens/Engineering";
import { Home, useApps } from "./screens/Home";
import { Login } from "./screens/Login";

export function App() {
  const [user, setUser] = useState<string | null>(session.token() ? session.user() : null);
  useEffect(() => onUnauthorised(() => setUser(null)), []);

  return (
    <BrowserRouter>
      <Wallpaper />
      {user === null ? <Login onLogin={setUser} /> : <Shell user={user} onSignOut={() => { session.clear(); setUser(null); }} />}
    </BrowserRouter>
  );
}

function Shell({ user, onSignOut }: { user: string; onSignOut: () => void }) {
  const { apps } = useApps(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const closeMenu = useCallback(() => setMenuOpen(false), []);

  return (
    <div className="frame">
      <Sidebar apps={apps} user={user} open={menuOpen} onClose={closeMenu} onSignOut={onSignOut} />
      <header className="topbar">
        <button type="button" className="icon-link topbar__menu" onClick={() => setMenuOpen(true)} aria-label="Open menu">
          <Menu size={20} aria-hidden="true" />
        </button>
        <LogoMark size={30} />
        <span className="topbar__word">SIRIS<b>OS</b></span>
      </header>
      <main className="shell">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/assistant" element={<Assistant />} />
          <Route path="/brain" element={<Brain />} />
          <Route path="/engineering/*" element={<Engineering />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      <Dock />
    </div>
  );
}
