"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";

import { Noto_Sans_SC, Noto_Serif_SC, JetBrains_Mono, Playfair_Display } from "next/font/google";
import "./globals.css";

const notoSansSC = Noto_Sans_SC({ subsets: ["latin"], weight: ["400", "500", "700"], variable: "--font-sans" });
const notoSerifSC = Noto_Serif_SC({ subsets: ["latin"], weight: ["400", "600", "700"], variable: "--font-serif" });
const jetbrainsMono = JetBrains_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-mono" });
const playfair = Playfair_Display({ subsets: ["latin"], weight: ["600", "700"], variable: "--font-display" });

const NAV_ITEMS = [
  { section: "研究", items: [
    { id: "new", label: "新建分析", icon: "+", href: "/" },
    { id: "reports", label: "报告列表", icon: "☰", href: "/reports" },
  ]},
  { section: "工具", items: [
    { id: "templates", label: "模板管理", icon: "⚙", href: "/templates" },
  ]},
  { section: "系统", items: [
    { id: "settings", label: "模型与配置", icon: "⚡", href: "/settings" },
  ]},
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [hovered, setHovered] = useState<string | null>(null);

  const currentView = pathname === "/" ? "new"
    : pathname.startsWith("/reports") ? "reports"
    : pathname.startsWith("/templates") ? "templates"
    : pathname.startsWith("/settings") ? "settings"
    : "new";

  return (
    <html lang="zh-CN" className={`${notoSansSC.variable} ${notoSerifSC.variable} ${jetbrainsMono.variable} ${playfair.variable} h-full antialiased`}>
      <body className="min-h-full bg-bg-warm text-ink-primary font-sans">
        <div className="flex h-screen overflow-hidden">
          {/* Sidebar */}
          <aside className="w-[200px] min-w-[200px] bg-bg-surface border-r border-border-light flex flex-col py-6 h-screen overflow-y-auto">
            <div className="px-5 pb-5 border-b border-border-light mb-4">
              <Link href="/" className="no-underline">
                <div className="font-serif text-lg font-bold text-ink-primary tracking-wider">研报 Agent</div>
                <div className="font-mono text-[10px] text-ink-tertiary tracking-[0.1em] mt-0.5">RESEARCH</div>
              </Link>
            </div>

            <nav className="flex-1">
              {NAV_ITEMS.map((group) => (
                <div key={group.section}>
                  <div className="font-mono text-[9px] text-ink-tertiary tracking-[0.08em] px-5 pt-3 pb-1.5">
                    {group.section}
                  </div>
                  {group.items.map((item) => {
                    const isActive = currentView === item.id;
                    return (
                      <Link key={item.id} href={item.href} className="no-underline"
                        onMouseEnter={() => setHovered(item.id)}
                        onMouseLeave={() => setHovered(null)}
                      >
                        <div className={`flex items-center gap-2.5 px-5 py-2 text-[13px] transition-colors duration-150 border-l-2 ${
                          isActive
                            ? "text-accent border-accent bg-accent-soft font-medium"
                            : hovered === item.id
                            ? "text-ink-primary border-transparent bg-black/[0.03]"
                            : "text-ink-secondary border-transparent"
                        }`}>
                          <span className="w-4 text-center text-[13px]">{item.icon}</span>
                          {item.label}
                        </div>
                      </Link>
                    );
                  })}
                </div>
              ))}
            </nav>

            <div className="px-5 pt-4 border-t border-border-light text-[11px] text-ink-tertiary">
              本月用量
              <div className="h-[3px] bg-border-light mt-1.5">
                <div className="h-full bg-accent transition-all duration-500" style={{ width: "33%" }} />
              </div>
              <div className="font-mono text-[10px] mt-1">1 / 3 份报告</div>
            </div>
          </aside>

          {/* Main content */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* Top bar */}
            <header className="flex items-center justify-between px-8 py-3 bg-bg-warm border-b border-border-light shrink-0">
              <div className="text-[13px] text-ink-tertiary">
                研报 Agent <span className="mx-1.5">/</span> <span className="text-ink-secondary">
                  {{ new: "新建分析", reports: "报告列表", templates: "模板管理", settings: "模型与配置" }[currentView]}
                </span>
              </div>
            </header>

            {/* Page content with transition */}
            <main className="flex-1 overflow-y-auto">
              <AnimatePresence mode="wait">
                <motion.div
                  key={pathname}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -6 }}
                  transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
                  className="h-full"
                >
                  {children}
                </motion.div>
              </AnimatePresence>
            </main>
          </div>
        </div>
      </body>
    </html>
  );
}
