import { Suspense, lazy, useCallback, useEffect, useState } from "react";
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { Menu, Mic, PenLine, Search } from "lucide-react";
import { onUnauthorised, session } from "./api/client";
import { Dock } from "./components/Dock";
import { LogoMark } from "./components/Logo";
import { useMorningBrief } from "./components/MorningBrief";
import { useEdgeSwipe } from "./components/EdgeSwipe";
import { useSearchShortcut } from "./components/searchShortcut";
import { AppSheet } from "./screens/AppSheet";
import { Sidebar } from "./components/Sidebar";
import { Wallpaper } from "./components/Wallpaper";
import { Home, useApps } from "./screens/Home";
import { Login } from "./screens/Login";
import { ActScreen } from "./screens/Act";

// Home ships in the main bundle; every other screen is its own chunk,
// fetched in the background once the shell is idle (see warmScreens).
const loadAssistant = () => import("./screens/Assistant");
const loadBrain = () => import("./screens/Brain");
const loadLinks = () => import("./screens/Links");
const loadEngineering = () => import("./screens/Engineering");
const loadBrief = () => import("./screens/Brief");
const loadSearch = () => import("./components/SearchPalette");
const loadCareer = () => import("./screens/Career");
const loadInbox = () => import("./components/Inbox");
const loadStatus = () => import("./screens/Status");
const loadSecurity = () => import("./screens/Security");
const loadTerminal = () => import("./screens/Terminal");
const loadTasks = () => import("./screens/Tasks");
const loadWrapUp = () => import("./screens/WrapUp");
const loadReview = () => import("./screens/Review");
const loadCapture = () => import("./components/QuickCapture");
const loadTalk = () => import("./components/Talk");
const loadProjects = () => import("./screens/Projects");
const loadTrends = () => import("./screens/Trends");
const loadHouse = () => import("./screens/House");
const loadTraining = () => import("./screens/Training");
const Assistant = lazy(() => loadAssistant().then((m) => ({ default: m.Assistant })));
const Brain = lazy(() => loadBrain().then((m) => ({ default: m.Brain })));
const Links = lazy(() => loadLinks().then((m) => ({ default: m.Links })));
const Engineering = lazy(() => loadEngineering().then((m) => ({ default: m.Engineering })));
const BriefScreen = lazy(() => loadBrief().then((m) => ({ default: m.BriefScreen })));
const BriefOverlay = lazy(() => loadBrief().then((m) => ({ default: m.BriefOverlay })));
const Career = lazy(() => loadCareer().then((m) => ({ default: m.Career })));
const ProjectsScreen = lazy(() => loadProjects().then((m) => ({ default: m.ProjectsScreen })));
const ProjectScreen = lazy(() => loadProjects().then((m) => ({ default: m.ProjectScreen })));
const HouseScreen = lazy(() => loadHouse().then((m) => ({ default: m.HouseScreen })));
const TrainingScreen = lazy(() => loadTraining().then((m) => ({ default: m.TrainingScreen })));
const TrendsScreen = lazy(() => loadTrends().then((m) => ({ default: m.TrendsScreen })));
const Talk = lazy(() => loadTalk().then((m) => ({ default: m.Talk })));
const QuickCapture = lazy(() => loadCapture().then((m) => ({ default: m.QuickCapture })));
const SecurityScreen = lazy(() => loadSecurity().then((m) => ({ default: m.SecurityScreen })));
const TerminalScreen = lazy(() => loadTerminal().then((m) => ({ default: m.TerminalScreen })));
const TasksScreen = lazy(() => loadTasks().then((m) => ({ default: m.TasksScreen })));
const WrapUpScreen = lazy(() => loadWrapUp().then((m) => ({ default: m.WrapUpScreen })));
const ReviewScreen = lazy(() => loadReview().then((m) => ({ default: m.ReviewScreen })));
const StatusScreen = lazy(() => loadStatus().then((m) => ({ default: m.StatusScreen })));
const InboxScreen = lazy(() => loadInbox().then((m) => ({ default: m.InboxScreen })));
const SearchPalette = lazy(() => loadSearch().then((m) => ({ default: m.SearchPalette })));

function warmScreens() {
  const warm = () => [loadAssistant, loadBrain, loadLinks, loadEngineering, loadBrief, loadSearch, loadCareer, loadInbox, loadCapture].forEach((load) => load().catch(() => undefined));
  const idle = (window as Window & { requestIdleCallback?: (cb: () => void, opts?: { timeout: number }) => number }).requestIdleCallback;
  if (idle) idle(warm, { timeout: 3000 });
  else window.setTimeout(warm, 1500);
}

/** /capture (a Home Screen link): open quick capture over Home. */
function OpenCapture({ onOpen }: { onOpen: () => void }) {
  const navigate = useNavigate();
  useEffect(() => {
    onOpen();
    navigate("/", { replace: true });
  }, [onOpen, navigate]);
  return null;
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
      <Routes>
        <Route path="/act" element={<ActScreen signedIn={user !== null} />} />
        <Route path="*" element={user === null ? <Login onLogin={setUser} /> : <Shell user={user} onSignOut={() => { session.clear(); setUser(null); }} />} />
      </Routes>
    </BrowserRouter>
  );
}

function Shell({ user, onSignOut }: { user: string; onSignOut: () => void }) {
  const { apps } = useApps(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const closeMenu = useCallback(() => setMenuOpen(false), []);
  // Swipe in from the left edge to open the menu, and back to close it (phones and tablets).
  useEdgeSwipe({ open: menuOpen, onOpen: () => setMenuOpen(true), onClose: closeMenu });
  const morning = useMorningBrief();
  const onBriefScreen = useLocation().pathname === "/brief";
  const [searching, setSearching] = useState(false);
  const openSearch = useCallback(() => {
    setMenuOpen(false);
    setSearching(true);
  }, []);
  const closeSearch = useCallback(() => setSearching(false), []);
  const [capturing, setCapturing] = useState(false);
  const openCapture = useCallback(() => {
    setMenuOpen(false);
    setCapturing(true);
  }, []);
  const closeCapture = useCallback(() => setCapturing(false), []);
  const [talking, setTalking] = useState(false);
  const openTalk = useCallback(() => {
    setMenuOpen(false);
    setTalking(true);
  }, []);
  const closeTalk = useCallback(() => setTalking(false), []);
  useSearchShortcut(openSearch);
  const [sheetFor, setSheetFor] = useState<string | null>(null);
  const sheetApp = sheetFor ? apps?.find((a) => a.id === sheetFor) : undefined;
  useEffect(warmScreens, []);

  return (
    <div className="frame">
      <Sidebar apps={apps} user={user} open={menuOpen} onClose={closeMenu} onSignOut={onSignOut} onSearch={openSearch} onCapture={openCapture} />
      <header className="topbar">
        <button type="button" className="icon-link topbar__menu" onClick={() => setMenuOpen(true)} aria-label="Open menu">
          <Menu size={20} aria-hidden="true" />
        </button>
        <Link to="/" className="topbar__home" aria-label="SirisOS home">
          <LogoMark size={30} />
          <span className="topbar__word">SIRIS<b>OS</b></span>
        </Link>
        <button type="button" className="icon-link topbar__talk" onClick={openTalk} aria-label="Talk to SirisOS">
          <Mic size={19} aria-hidden="true" />
        </button>
        <button type="button" className="icon-link topbar__capture" onClick={openCapture} aria-label="Quick capture">
          <PenLine size={19} aria-hidden="true" />
        </button>
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
          <Route path="/career" element={<Career />} />
          <Route path="/inbox" element={<InboxScreen />} />
          <Route path="/status" element={<StatusScreen />} />
          <Route path="/security" element={<SecurityScreen />} />
          <Route path="/terminal" element={<TerminalScreen />} />
          <Route path="/tasks" element={<TasksScreen />} />
          <Route path="/projects" element={<ProjectsScreen />} />
          <Route path="/year" element={<TrendsScreen />} />
          <Route path="/house" element={<HouseScreen />} />
          <Route path="/training" element={<TrainingScreen />} />
          <Route path="/projects/:title" element={<ProjectScreen />} />
          <Route path="/wrapup" element={<WrapUpScreen />} />
          <Route path="/review" element={<ReviewScreen />} />
          <Route path="/capture" element={<OpenCapture onOpen={openCapture} />} />
          <Route path="/talk" element={<OpenCapture onOpen={openTalk} />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </Suspense>
      </main>
      <Dock />
      {talking && (
        <Suspense fallback={null}>
          <Talk onClose={closeTalk} />
        </Suspense>
      )}
      {capturing && (
        <Suspense fallback={null}>
          <QuickCapture onClose={closeCapture} />
        </Suspense>
      )}
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
