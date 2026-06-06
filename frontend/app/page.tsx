"use client";

import { useState, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Search, TrendingUp, BarChart3 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { apiUrl } from "@/lib/api";

const SUGGESTIONS = ["贵州茅台", "宁德时代", "AAPL", "五粮液", "MSFT", "恒瑞医药"];

export default function HomePage() {
  const router = useRouter();
  const [ticker, setTicker] = useState("");
  const [watchlist, setWatchlist] = useState<{ ticker: string; name: string }[]>([]);
  const [recentReports, setRecentReports] = useState<{ task_id: string; ticker: string; company_name: string; verdict: string; report_type: string; created_at: string }[]>([]);

  useEffect(() => {
    fetch(apiUrl("/watchlist")).then(r => r.json()).then(d => setWatchlist(d.watchlist || [])).catch(() => {});
    fetch(apiUrl("/reports?limit=5")).then(r => r.json()).then(d => setRecentReports(d.reports || [])).catch(() => {});
  }, []);

  const handleStart = useCallback(() => {
    if (!ticker.trim()) return;
    router.push(`/progress?ticker=${encodeURIComponent(ticker)}&depth=value&template=value_investor`);
  }, [ticker, router]);

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Page Title */}
      <div>
        <h1 className="text-2xl font-bold text-[#1C2434]">新建分析</h1>
        <p className="text-sm text-[#64748B] mt-1">输入股票代码，AI 多 Agent 协作生成专业投研报告</p>
      </div>

      {/* Search Card */}
      <Card className="border-[#E2E8F0] shadow-sm">
        <CardContent className="p-5">
          <div className="flex gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#94A3B8]" />
              <Input
                value={ticker}
                onChange={e => setTicker(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handleStart()}
                placeholder="输入公司名称或股票代码…"
                className="pl-10 h-11 border-[#E2E8F0]"
              />
            </div>
            <Button onClick={handleStart} disabled={!ticker.trim()} className="h-11 px-6 bg-[#3B82F6] hover:bg-[#2563EB]">
              开始分析
            </Button>
          </div>
          <div className="flex items-center gap-2 mt-4 flex-wrap">
            <span className="text-xs text-[#94A3B8]">热门:</span>
            {SUGGESTIONS.map(s => (
              <Badge key={s} variant="secondary" className="cursor-pointer bg-[#F8FAFC] text-[#64748B] hover:bg-[#EFF6FF] hover:text-[#3B82F6] border-0" onClick={() => setTicker(s)}>
                {s}
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Quick Stats */}
      <div className="grid grid-cols-3 gap-4">
        <Card className="border-[#E2E8F0] shadow-sm">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-[#EFF6FF] flex items-center justify-center"><BarChart3 className="w-5 h-5 text-[#3B82F6]" /></div>
            <div><div className="text-2xl font-bold text-[#1C2434]">{recentReports.length}</div><div className="text-xs text-[#64748B]">已生成报告</div></div>
          </CardContent>
        </Card>
        <Card className="border-[#E2E8F0] shadow-sm">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-[#F0FDF4] flex items-center justify-center"><TrendingUp className="w-5 h-5 text-[#22C55E]" /></div>
            <div><div className="text-2xl font-bold text-[#1C2434]">{watchlist.length}</div><div className="text-xs text-[#64748B]">自选股票</div></div>
          </CardContent>
        </Card>
        <Card className="border-[#E2E8F0] shadow-sm">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-[#FFF7ED] flex items-center justify-center"><TrendingUp className="w-5 h-5 text-[#F97316]" /></div>
            <div><div className="text-2xl font-bold text-[#1C2434]">{recentReports.filter(r => r.verdict === "Yes").length}</div><div className="text-xs text-[#64748B]">Yes 判定</div></div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Reports */}
      {recentReports.length > 0 && (
        <Card className="border-[#E2E8F0] shadow-sm">
          <CardContent className="p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-[#1C2434]">最近分析</h3>
              <Link href="/reports" className="text-xs text-[#3B82F6] hover:underline">查看全部 →</Link>
            </div>
            <div className="space-y-1">
              {recentReports.map(r => (
                <Link key={r.task_id} href={`/report?task=${r.task_id}`} className="flex items-center justify-between py-2.5 px-3 rounded-lg hover:bg-[#F8FAFC] transition-colors no-underline group">
                  <div className="flex items-center gap-3">
                    <span className="font-medium text-sm text-[#1C2434]">{r.company_name}</span>
                    <span className="text-xs text-[#94A3B8]">{r.ticker}</span>
                    <Badge variant="secondary" className="text-[10px] bg-[#F8FAFC] text-[#64748B] border-0">{r.report_type}</Badge>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge variant={r.verdict === "Yes" ? "positive" : "secondary"} className={`text-[11px] ${r.verdict === "Yes" ? "bg-[#F0FDF4] text-[#22C55E]" : "bg-[#F8FAFC] text-[#64748B]"}`}>{r.verdict}</Badge>
                    <span className="text-xs text-[#94A3B8] opacity-0 group-hover:opacity-100 transition-opacity">{r.created_at ? new Date(r.created_at).toLocaleDateString("zh-CN") : ""}</span>
                  </div>
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Watchlist */}
      {watchlist.length > 0 && (
        <Card className="border-[#E2E8F0] shadow-sm">
          <CardContent className="p-5">
            <h3 className="text-sm font-semibold text-[#1C2434] mb-3">自选股</h3>
            <div className="flex flex-wrap gap-2">
              {watchlist.map(w => (
                <Badge key={w.ticker} variant="outline" className="cursor-pointer text-sm py-1.5 px-3 border-[#E2E8F0] hover:border-[#3B82F6] hover:text-[#3B82F6]" onClick={() => setTicker(w.ticker)}>
                  {w.name || w.ticker}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
