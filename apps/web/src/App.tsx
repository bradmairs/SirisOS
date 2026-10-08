import { Suspense, lazy, useCallback, useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Menu, Search } from "lucide-react";
import { onUnauthorised, session } from "./api/client";
import { Dock } from "./components/Dock";
import { LogoMark } from "./components/Logo";
import { useMorningBrief } from "./components/MorningBrief";
import { useSearchShortcut } from "./components/searchShortcut";
import { AppSheet } from "./screens/AppSheet";
import { Sidebar } from "./components/Sidebar";
import { Wallpaper } from "./components/Wallpaper";
import { Home, useApps } from "./screens/Home";
import { Login } from "./screens/Login";

// Home ships in the main bundle; every other screen is its own chunk,
// fetched in the background once the shell is idle (see warmScreens).
const loadAssistant = () => import("./screens/Assistant");
const loadBrain = () => import("./screens/Brain");
const loadLinks = () => import("./screens/Links");
const loadEngineering = () => import("./screens/Engineering");
const loadBrief = () => import("./screens/Brief");
const loadSearch = () => import("./components/SearchPalette");
const Assistant = lazy(() => loadAssistant().then((m) => ({ default: m.Assistant })));
const Brain = lazy(() => loadBrain().then((m) => ({ default: m.Brain })));
const Links = lazy(() => loadLinks().then((m) => ({ default: m.Links })));
const Engineering = lazy(() => loadEngineering().then((m) => ({ default: m.Engineering })));
const BriefScreen = lazy(() => loadBrief().then((m) => ({ default: m.BriefScreen })));
const BriefOverlay = lazy(() => loadBrief().then((m) => ({ default: m.BriefOverlay })));
const SearchPalette = lazy(() => loadSearch().then((m) => ({ default: m.SearchPalette })));

function warmScreens() {
  const warm = () => [loadAssistant, loadBrain, loadLinks, loadEngineering, loadBrief, loadSearch].forEach((load) => load().catch(() => undefined));
  const idle = (window as Window & { requestIdleCallback?: (cb: () => void, opts?: { timeout: number }) => number }).requestIdleCallback;
  if (idle) idle(warm, { timeout: 3000 });
  else window.setTimeout(warm, 1500);
}

function ScreenFallback() {
  return (
    <div className="screen-fallback" aria-busy="true" aria-label="Loading">
      <div className="skeleton" style={{ height: 34, width: "45%" }} />
      <div className="skeleton" style={{ height: 120 }} />
    </div>
  );
}

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
  const morning = useMorningBrief();
  const onBriefScreen = useLocation().pathname === "/brief";
  const [searching, setSearching] = useState(false);
  const openSearch = useCallback(() => {
    setMenuOpen(false);
    setSearching(true);
  }, []);
  const closeSearch = useCallback(() => setSearching(false), []);
  useSearchShortcut(openSearch);
  const [sheetFor, setSheetFor] = useState<string | null>(null);
  const sheetApp = sheetFor ? apps?.find((a) => a.id === sheetFor) : undefined;
  useEffect(warmScreens, []);

  return (
    <div className="frame">
      <Sidebar apps={apps} user={user} open={menuOpen} onClose={closeMenu} onSignOut={onSignOut} onSearch={openSearch} />
      <header className="topbar">
        <button type="button" className="icon-link topbar__menu" onClick={() => setMenuOpen(true)} aria-label="Open menu">
          <Menu size={20} aria-hidden="true" />
        </button>
        <LogoMark size={30} />
        <span className="topbar__word">SIRIS<b>OS</b></span>
        <button type="button" className="icon-link topbar__search" onClick={openSearch} aria-label="Search everything">
          <Search size={20} aria-hidden="true" />
        </button>
      </header>
      <main className="shell">
        <Suspense fallback={<ScreenFallback />}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/assistant" element={<Assistant />} />
          <Route path="/brain" element={<Brain />} />
          <Route path="/links" element={<Links />} />
          <Route path="/engineering/*" element={<Engineering />} />
          <Route path="/brief" element={<BriefScreen />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </Suspense>
      </main>
      <Dock />
      {searching && (
        <Suspense fallback={null}>
          <SearchPalette onClose={closeSearch} onOpenApp={setSheetFor} />
        </Suspense>
      )}
      {sheetApp && <AppSheet appId={sheetApp.id} initial={sheetApp} onClose={() => setSheetFor(null)} />}
      {morning.open && !onBriefScreen && (
        <Suspense fallback={null}>
          <BriefOverlay onClose={morning.close} />
        </Suspense>
      )}
    </div>
  );
}
