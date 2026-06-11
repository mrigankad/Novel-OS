import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { AnimatePresence, motion, MotionConfig } from "motion/react";
import Sidebar from "./components/Sidebar";
import { ToastProvider } from "./components/Toaster";
import ProjectsList from "./routes/ProjectsList";
import ProjectDashboard from "./routes/ProjectDashboard";
import ChapterView from "./routes/ChapterView";

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
        <Routes location={location}>
          <Route path="/" element={<ProjectsList />} />
          <Route path="/projects/:id" element={<ProjectDashboard />} />
          <Route path="/projects/:id/chapters/:n" element={<ChapterView />} />
        </Routes>
      </motion.div>
    </AnimatePresence>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <MotionConfig reducedMotion="user">
        <ToastProvider>
          <a href="#main" className="skip-link">Skip to content</a>
          <div className="flex h-full">
            <Sidebar />
            <main id="main" className="h-full flex-1 overflow-y-auto">
              <AnimatedRoutes />
            </main>
          </div>
        </ToastProvider>
      </MotionConfig>
    </BrowserRouter>
  );
}
