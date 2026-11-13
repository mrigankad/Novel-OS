import type { Metadata, Viewport } from "next";
import { Inter_Tight, Newsreader, Urbanist } from "next/font/google";
import type { ReactNode } from "react";
import Providers from "@/lib/providers";
import Sidebar from "@/components/sidebar";
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

export const viewport: Viewport = { themeColor: "#ffffff" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${urbanist.variable} ${newsreader.variable}`}>
      <body>
        <Providers>
          <div className="flex h-full">
            <Sidebar />
            <main id="main" className="h-full min-w-0 flex-1 overflow-y-auto">{children}</main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
