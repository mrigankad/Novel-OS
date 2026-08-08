import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { AnimatePresence, motion, MotionConfig } from "motion/react";
import Sidebar from "./components/Sidebar";
import CommandPalette from "./components/CommandPalette";
import ShortcutsHelp from "./components/ShortcutsHelp";
import ErrorBoundary from "./components/ErrorBoundary";
import { ToastProvider } from "./components/Toaster";
import { ConfirmProvider } from "./components/Confirm";

// Code-split routes so the CodeMirror editor only loads on the chapter view.
const ProjectsList = lazy(() => import("./routes/ProjectsList"));
const ProjectDashboard = lazy(() => import("./routes/ProjectDashboard"));
const ChapterView = lazy(() => import("./routes/ChapterView"));
const Settings = lazy(() => import("./routes/Settings"));
const RelationshipChart = lazy(() => import("./routes/RelationshipChart"));
const ResearchMoodboard = lazy(() => import("./routes/ResearchMoodboard"));

function AnimatedRoutes() {
  const location = useLocation();
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={location.pathname}
        transition={{ duration: 0.35, ease: [0.2, 0.8, 0.2, 1] }}
        initial={{ opacity: 0, y: 10, scale: 0.985 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: -8, scale: 0.99 }}
        className="h-full"
      >
        <Suspense fallback={<div className="px-10 py-12 text-ink-muted">Loading…</div>}>
          <Routes location={location}>
            <Route path="/" element={<ProjectsList />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/projects/:id" element={<ProjectDashboard />} />
            <Route path="/projects/:id/chart" element={<RelationshipChart />} />
            <Route path="/projects/:id/research" element={<ResearchMoodboard />} />
            <Route path="/projects/:id/chapters/:n" element={<ChapterView />} />
          </Routes>
        </Suspense>
      </motion.div>
    </AnimatePresence>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <MotionConfig reducedMotion="user">
        <ToastProvider>
          <ConfirmProvider>
            <a href="#main" className="skip-link">Skip to content</a>
            <CommandPalette />
            <ShortcutsHelp />
            <div className="flex h-full">
              <Sidebar />
              <main id="main" className="h-full flex-1 overflow-y-auto">
                <ErrorBoundary>
                  <AnimatedRoutes />
                </ErrorBoundary>
              </main>
            </div>
          </ConfirmProvider>
        </ToastProvider>
      </MotionConfig>
    </BrowserRouter>
  );
}
