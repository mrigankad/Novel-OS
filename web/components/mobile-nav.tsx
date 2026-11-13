"use client";

import { Menu, Search } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { BrandLogo, BrandMark } from "./brand";
import { NavList, openCommandPalette, useNav } from "./sidebar";
import { ThemeToggle } from "./theme-toggle";
import { Drawer } from "./ui/drawer";

/** Below md: a top bar (mark, current book, search, menu) and a slide-over drawer with the same nav. */
export default function MobileNav() {
  const { pathname, projectTitle } = useNav();
  // The drawer is open only for the path it was opened on, so any navigation closes it.
  const [openAt, setOpenAt] = useState<string | null>(null);
  const open = openAt === pathname;
  const close = () => setOpenAt(null);

  return (
    <>
      <header className="flex h-14 shrink-0 items-center gap-2 border-b border-rule bg-sheet px-4 md:hidden">
        <Link href="/" aria-label="Novel OS, Library" className="mr-1"><BrandMark /></Link>
        <span className="min-w-0 flex-1 truncate text-[14px] font-semibold text-ink">{projectTitle ?? "Novel OS"}</span>
        <button type="button" onClick={openCommandPalette} aria-label="Search or command"
          className="rounded-[8px] p-2 text-body hover:bg-paper hover:text-ink">
          <Search className="h-5 w-5" strokeWidth={1.75} />
        </button>
        <button type="button" onClick={() => setOpenAt(pathname)} aria-label="Open menu"
          aria-expanded={open} aria-controls="mobile-nav" aria-haspopup="dialog"
          className="rounded-[8px] p-2 text-body hover:bg-paper hover:text-ink">
          <Menu className="h-5 w-5" strokeWidth={1.75} />
        </button>
      </header>
      <Drawer open={open} onClose={close} side="left" label="Navigation">
        <div id="mobile-nav" className="flex min-h-full flex-col bg-sheet gap-5 px-3 py-5">
          <Link href="/" onClick={close} className="self-start px-2"><BrandLogo /></Link>
          <NavList onNavigate={close} />
          <div className="mt-auto pt-2"><ThemeToggle /></div>
        </div>
      </Drawer>
    </>
  );
}
