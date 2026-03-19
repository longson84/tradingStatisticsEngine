import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";
import { Providers } from "./providers";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Trading Statistics Engine",
  description: "Backtesting and factor analysis dashboard",
};

const NAV_LINKS = [
  { href: "/backtest", label: "Backtest" },
  { href: "/sweep", label: "Strategy Sweep" },
  { href: "/factors", label: "Factors" },
];

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased dark`}
    >
      <body className="min-h-full flex bg-background text-foreground">
        <Providers>
          {/* Sidebar */}
          <aside className="w-52 shrink-0 border-r border-border flex flex-col gap-1 p-4">
            <div className="mb-6">
              <span className="font-semibold text-sm text-muted-foreground uppercase tracking-wider">
                TSE
              </span>
            </div>
            {NAV_LINKS.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                className="px-3 py-2 rounded-md text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
              >
                {label}
              </Link>
            ))}
          </aside>

          {/* Main content */}
          <main className="flex-1 overflow-y-auto p-8">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
