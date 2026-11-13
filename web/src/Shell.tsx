"use client";
import "./theme";
import type { ReactNode } from "react";
import { MotionConfig } from "motion/react";
import Sidebar from "./components/Sidebar";
import CommandPalette from "./components/CommandPalette";
import ShortcutsHelp from "./components/ShortcutsHelp";
import ErrorBoundary from "./components/ErrorBoundary";
import { ToastProvider } from "./components/Toaster";
import { ConfirmProvider } from "./components/Confirm";

/** Studio chrome shared by every page: sidebar, command palette, toasts, confirms. */
export default function Shell({ children }: { children: ReactNode }) {
  return (
    <MotionConfig reducedMotion="user">
      <ToastProvider>
        <ConfirmProvider>
          <a href="#main" className="skip-link">Skip to content</a>
          <CommandPalette />
          <ShortcutsHelp />
          <div className="flex h-full">
            <Sidebar />
            <main id="main" className="h-full flex-1 overflow-y-auto">
              <ErrorBoundary>{children}</ErrorBoundary>
            </main>
          </div>
        </ConfirmProvider>
      </ToastProvider>
    </MotionConfig>
  );
}
