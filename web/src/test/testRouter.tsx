/**
 * In-memory router for tests: drives the app's nav layer (src/lib/nav.tsx)
 * with react-router's MemoryRouter, so component tests don't need Next.js.
 */
import type { ReactNode } from "react";
import {
  MemoryRouter as RRMemoryRouter,
  Route,
  Routes,
  useLocation as useRRLocation,
  useNavigate as useRRNavigate,
  useParams as useRRParams,
} from "react-router-dom";
import { NavImplContext, type NavImpl, type NavigateFn } from "../lib/nav";

const memoryImpl: NavImpl = {
  usePathname: () => useRRLocation().pathname,
  useSearch: () => useRRLocation().search.replace(/^\?/, ""),
  useParams: () => useRRParams() as Record<string, string>,
  useNavigate: () => {
    const nav = useRRNavigate();
    return ((to, opts) => (typeof to === "number" ? nav(to) : nav(to, opts))) as NavigateFn;
  },
};

export function MemoryRouter({ children, initialEntries }: { children: ReactNode; initialEntries?: string[] }) {
  return (
    <RRMemoryRouter initialEntries={initialEntries}>
      <NavImplContext.Provider value={memoryImpl}>{children}</NavImplContext.Provider>
    </RRMemoryRouter>
  );
}

export { Routes, Route };
