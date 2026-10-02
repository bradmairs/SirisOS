import { useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { onUnauthorised, session } from "./api/client";
import { Dock } from "./components/Dock";
import { Wallpaper } from "./components/Wallpaper";
import { Assistant } from "./screens/Assistant";
import { Brain } from "./screens/Brain";
import { Engineering } from "./screens/Engineering";
import { Home } from "./screens/Home";
import { Login } from "./screens/Login";

export function App() {
  const [user, setUser] = useState<string | null>(session.token() ? session.user() : null);
  useEffect(() => onUnauthorised(() => setUser(null)), []);

  return (
    <BrowserRouter>
      <Wallpaper />
      {user === null ? (
        <Login onLogin={setUser} />
      ) : (
        <>
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
        </>
      )}
    </BrowserRouter>
  );
}
