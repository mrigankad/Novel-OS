import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import "@fontsource-variable/inter-tight/index.css";
import "@fontsource/urbanist/700.css";
import "@fontsource/newsreader/400.css";
import "@fontsource/newsreader/500.css";
import "@fontsource/newsreader/600.css";
import "@fontsource/newsreader/400-italic.css";
import "../src/index.css";
import ClientOnly from "../src/ClientOnly";

export const metadata: Metadata = {
  title: { default: "Novel OS", template: "%s · Novel OS" },
  description: "The writing studio that remembers chapter 3.",
  icons: { icon: "/favicon.svg" },
};

export const viewport: Viewport = { themeColor: "#ffffff" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <ClientOnly>{children}</ClientOnly>
      </body>
    </html>
  );
}
