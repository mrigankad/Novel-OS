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

function AnimatedRoutes() {
  const location = useLocation();
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={location.pathname}
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -6 }}
        transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
        className="h-full"
      >
        <Suspense fallback={<div className="px-10 py-12 text-ink-muted">Loading…</div>}>
          <Routes location={location}>
            <Route path="/" element={<ProjectsList />} />
            <Route path="/projects/:id" element={<ProjectDashboard />} />
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
