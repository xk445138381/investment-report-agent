import type { Metadata } from "next";
import { Noto_Sans_SC, Noto_Serif_SC, JetBrains_Mono, Inter, Playfair_Display } from "next/font/google";
import "./globals.css";

const notoSansSC = Noto_Sans_SC({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  variable: "--font-sans",
});
const notoSerifSC = Noto_Serif_SC({
  subsets: ["latin"],
  weight: ["400", "600", "700"],
  variable: "--font-serif",
});
const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
});
const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-inter",
});
const playfair = Playfair_Display({
  subsets: ["latin"],
  weight: ["600", "700"],
  variable: "--font-display",
});

export const metadata: Metadata = {
  title: "投资报告 Agent — AI 研报生成",
  description: "基于多 Agent 协作的专业投资研究报告生成系统",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="zh-CN"
      className={`${notoSansSC.variable} ${notoSerifSC.variable} ${jetbrainsMono.variable} ${inter.variable} ${playfair.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-bg-warm text-ink-primary">
        <header className="flex items-center justify-between px-8 py-4 border-b border-border-light">
          <div className="flex items-center gap-3">
            <span className="font-serif text-xl font-semibold tracking-wide text-ink-primary">
              研报 Agent
            </span>
            <span className="text-xs text-ink-tertiary tracking-widest uppercase font-mono">
              Research
            </span>
          </div>
          <nav className="flex items-center gap-6 text-sm text-ink-secondary">
            <a href="/" className="hover:text-ink-primary transition-colors">对话</a>
            <a href="/templates" className="hover:text-ink-primary transition-colors">模板</a>
            <span className="text-ink-tertiary text-xs font-mono">0/3</span>
          </nav>
        </header>
        <main className="flex-1">{children}</main>
      </body>
    </html>
  );
}
