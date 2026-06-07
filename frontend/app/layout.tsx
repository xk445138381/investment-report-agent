"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Bell, Settings, FileText, Briefcase, Archive, Plus } from "lucide-react";

import { apiUrl } from "@/lib/api";
import "./globals.css";

const NAV_ITEMS = [
  { id: "new", label: "新建分析", icon: Plus, href: "/" },
  { id: "reports", label: "报告列表", icon: FileText, href: "/reports" },
  { id: "portfolio", label: "模拟组合", icon: Briefcase, href: "/portfolio" },
  { id: "archive", label: "投研档案", icon: Archive, href: "/archive" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [alertCount, setAlertCount] = useState(0);
  const [alerts, setAlerts] = useState<{ ticker: string; company_name: string; message: string; current_price: number; triggered_at: string }[]>([]);
  const [showAlerts, setShowAlerts] = useState(false);

  useEffect(() => {
    const fetchAlerts = () => {
      fetch(apiUrl("/alerts/count"))
        .then((r) => r.json())
        .then((d) => setAlertCount(d.recent_triggered || 0))
        .catch(() => {});
    };
    fetchAlerts();
    const interval = setInterval(fetchAlerts, 60000);
    return () => clearInterval(interval);
  }, []);

  const openAlerts = async () => {
    setShowAlerts(!showAlerts);
    if (!showAlerts) {
      try {
        const res = await fetch(apiUrl("/alerts"));
        setAlerts((await res.json()).alerts || []);
      } catch {}
    }
  };

  const currentId = pathname === "/" ? "new"
    : pathname.startsWith("/reports") ? "reports"
    : pathname.startsWith("/portfolio") ? "portfolio"
    : pathname.startsWith("/archive") ? "archive"
    : pathname.startsWith("/settings") ? "settings"
    : "new";

  return (
    <html lang="zh-CN">
      <body className="bg-[#F1F5F9] text-[#1C2434] font-sans antialiased">
        <div className="flex h-screen overflow-hidden">
          {/* ── Sidebar ── */}
          <aside className="w-[280px] min-w-[280px] bg-white border-r border-[#E2E8F0] flex flex-col h-screen">
            {/* Logo */}
            <div className="px-6 py-5 border-b border-[#E2E8F0]">
              <Link href="/" className="flex items-center gap-3 no-underline">
                <div className="w-9 h-9 rounded-lg bg-[#3B82F6] flex items-center justify-center text-white font-bold text-sm">R</div>
                <div>
                  <div className="font-semibold text-[15px] text-[#1C2434]">研报 Agent</div>
                  <div className="text-[10px] text-[#64748B] font-mono tracking-wider">RESEARCH PLATFORM</div>
                </div>
              </Link>
            </div>

            {/* Navigation */}
            <nav className="flex-1 px-3 py-4 space-y-1">
              {NAV_ITEMS.map((item) => {
                const Icon = item.icon;
                const isActive = currentId === item.id;
                return (
                  <Link key={item.id} href={item.href} className="no-underline">
                    <div
                      className={`flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                        isActive
                          ? "bg-[#EFF6FF] text-[#3B82F6]"
                          : "text-[#637381] hover:bg-[#F8FAFC] hover:text-[#1C2434]"
                      }`}
                    >
                      <Icon className="w-5 h-5" />
                      {item.label}
                    </div>
                  </Link>
                );
              })}
            </nav>

            {/* Bottom section */}
            <div className="px-3 py-3 border-t border-[#E2E8F0]">
              <Link href="/settings" className="no-underline">
                <div
                  className={`flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    currentId === "settings"
                      ? "bg-[#EFF6FF] text-[#3B82F6]"
                      : "text-[#637381] hover:bg-[#F8FAFC] hover:text-[#1C2434]"
                  }`}
                >
                  <Settings className="w-5 h-5" />
                  模型与配置
                </div>
              </Link>
            </div>
          </aside>

          {/* ── Main content ── */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* Header */}
            <header className="flex items-center justify-between px-6 py-3 bg-white border-b border-[#E2E8F0] shrink-0">
              <div className="flex items-center gap-2">
                <span className="text-sm text-[#64748B]">
                  {currentId === "new" ? "新建分析" : ""}
                  {currentId === "reports" ? "报告列表" : ""}
                  {currentId === "portfolio" ? "模拟组合" : ""}
                  {currentId === "archive" ? "投研档案" : ""}
                  {currentId === "settings" ? "模型与配置" : ""}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <div className="relative">
                  <button
                    onClick={openAlerts}
                    className="relative w-9 h-9 flex items-center justify-center rounded-lg border border-[#E2E8F0] bg-white hover:bg-[#F8FAFC] transition-colors cursor-pointer"
                  >
                    <Bell className="w-4 h-4 text-[#637381]" />
                    {alertCount > 0 && (
                      <span className="absolute -top-1 -right-1 w-4 h-4 bg-[#DC2626] text-white text-[9px] font-mono flex items-center justify-center rounded-full">
                        {alertCount > 9 ? "9+" : alertCount}
                      </span>
                    )}
                  </button>
                  {showAlerts && alerts.length > 0 && (
                    <div className="absolute right-0 top-11 w-[360px] bg-white border border-[#E2E8F0] rounded-lg shadow-lg z-50 max-h-[320px] overflow-y-auto">
                      <div className="text-xs font-semibold text-[#64748B] px-4 py-3 border-b border-[#E2E8F0]">价格提醒</div>
                      {alerts.map((a, i) => (
                        <Link key={i} href={`/report?task=${a.ticker}`} className="block px-4 py-3 border-b border-[#E2E8F0] hover:bg-[#F8FAFC] no-underline">
                          <div className="text-sm font-medium text-[#1C2434]">{a.company_name || a.ticker}</div>
                          <div className="text-xs text-[#64748B] mt-0.5">{a.message}</div>
                          <div className="text-[10px] font-mono text-[#94A3B8] mt-0.5">
                            当前: ¥{a.current_price?.toLocaleString()} · {a.triggered_at ? new Date(a.triggered_at).toLocaleDateString("zh-CN") : ""}
                          </div>
                        </Link>
                      ))}
                    </div>
                  )}
                  {showAlerts && alerts.length === 0 && (
                    <div className="absolute right-0 top-11 w-[240px] bg-white border border-[#E2E8F0] rounded-lg shadow-lg z-50 text-center py-5 text-xs text-[#94A3B8]">
                      暂无触发提醒
                    </div>
                  )}
                </div>
              </div>
            </header>

            {/* Content */}
            <main className="flex-1 overflow-y-auto p-6">
              <AnimatePresence mode="wait">
                <motion.div
                  key={pathname}
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={{ duration: 0.2 }}
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
