import type { Metadata, Viewport } from "next";
import { Inter_Tight, Newsreader, Urbanist } from "next/font/google";
import type { ReactNode } from "react";
import Providers from "@/lib/providers";
import Sidebar from "@/components/sidebar";
import MobileNav from "@/components/mobile-nav";
import { THEME_BOOT_SCRIPT } from "@/lib/theme";
import CommandPalette from "@/components/command-palette";
import "./globals.css";

const inter = Inter_Tight({ subsets: ["latin"], variable: "--font-inter-tight", display: "swap" });
const urbanist = Urbanist({ subsets: ["latin"], weight: ["700"], variable: "--font-urbanist", display: "swap" });
const newsreader = Newsreader({
  subsets: ["latin"], style: ["normal", "italic"], variable: "--font-newsreader", display: "swap",
});

export const metadata: Metadata = {
  title: { default: "Novel OS", template: "%s · Novel OS" },
  description: "The writing studio that remembers chapter 3.",
  icons: { icon: "/favicon.svg" },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#121117" },
  ],
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${urbanist.variable} ${newsreader.variable}`} suppressHydrationWarning>
      <head>
        {/* Apply a stored theme before first paint, so there is no flash. */}
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT_SCRIPT }} />
      </head>
      <body>
        <Providers>
          <CommandPalette />
          <div className="flex h-full flex-col md:flex-row">
            <MobileNav />
            <Sidebar />
            <main id="main" className="min-h-0 min-w-0 flex-1 overflow-y-auto">{children}</main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
