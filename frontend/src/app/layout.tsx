import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Tender Project Manager",
  description: "AI-powered German tender document management",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-background min-h-screen`}
      >
        <nav className="border-b border-border px-6 py-3">
          <div className="max-w-7xl mx-auto flex items-center justify-between">
            <a href="/" className="text-base font-semibold text-foreground">
              Tender Manager
            </a>
            <div className="flex gap-1 text-sm">
              <a href="/projects" className="text-text-secondary hover:bg-surface-hover rounded-md px-3 py-1.5 transition-colors">
                Projects
              </a>
              <a href="/knowledge" className="text-text-secondary hover:bg-surface-hover rounded-md px-3 py-1.5 transition-colors">
                Knowledge Base
              </a>
            </div>
          </div>
        </nav>
        <main className="max-w-7xl mx-auto px-6 py-8">
          {children}
        </main>
      </body>
    </html>
  );
}
