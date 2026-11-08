import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "忆谈", description: "给老人的回忆录访谈" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen bg-paper text-ink antialiased">{children}</body>
    </html>
  );
}
