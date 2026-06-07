"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Search, FileText } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { apiUrl } from "@/lib/api";

type ReportItem = {
  task_id: string;
  ticker: string;
  company_name: string;
  report_type: string;
  verdict: string;
  upside_pct: number;
  created_at: string | null;
};

const reportTypeLabel = (t: string) => {
  const map: Record<string, string> = { value_deep_dive: "价值投资", quick_scan: "快速扫描", deep_dive: "深度研报" };
  return map[t] || t;
};

export default function ReportsPage() {
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    fetch(apiUrl("/reports"))
      .then(r => r.json())
      .then(d => { setReports(d.reports || []); setTotal(d.total || 0); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const filtered = search
    ? reports.filter(r => r.company_name?.includes(search) || r.ticker?.includes(search))
    : reports;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[#1C2434]">报告列表</h1>
          <p className="text-sm text-[#64748B] mt-1">共 {total} 份研究报告</p>
        </div>
        <Link href="/" className="text-sm text-[#3B82F6] hover:underline">新建分析 →</Link>
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#94A3B8]" />
        <Input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="搜索股票或代码…"
          className="pl-10 border-[#E2E8F0]"
        />
      </div>

      {loading && <div className="text-center py-10 text-sm text-[#94A3B8]">加载中…</div>}

      {!loading && filtered.length === 0 && (
        <Card className="border-[#E2E8F0]">
          <CardContent className="p-10 text-center">
            <FileText className="w-10 h-10 text-[#94A3B8] mx-auto mb-3" />
            <p className="text-sm text-[#64748B]">{search ? "未找到匹配报告" : "暂无报告，去首页开始分析吧"}</p>
          </CardContent>
        </Card>
      )}

      {!loading && filtered.length > 0 && (
        <Card className="border-[#E2E8F0] shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-[#E2E8F0] bg-[#F8FAFC]">
                  <th className="text-left text-xs font-semibold text-[#64748B] px-5 py-3">标的</th>
                  <th className="text-left text-xs font-semibold text-[#64748B] px-5 py-3">类型</th>
                  <th className="text-left text-xs font-semibold text-[#64748B] px-5 py-3">评级</th>
                  <th className="text-right text-xs font-semibold text-[#64748B] px-5 py-3">上行空间</th>
                  <th className="text-right text-xs font-semibold text-[#64748B] px-5 py-3">日期</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(r => (
                  <tr key={r.task_id} className="border-b border-[#E2E8F0] hover:bg-[#F8FAFC] transition-colors cursor-pointer" onClick={() => window.location.href = `/report?task=${r.task_id}`}>
                    <td className="px-5 py-3.5">
                      <div className="text-sm font-medium text-[#1C2434]">{r.company_name}</div>
                      <div className="text-xs text-[#94A3B8] font-mono">{r.ticker}</div>
                    </td>
                    <td className="px-5 py-3.5 text-sm text-[#64748B]">{reportTypeLabel(r.report_type)}</td>
                    <td className="px-5 py-3.5">
                      <Badge variant={r.verdict === "Yes" ? "positive" : "secondary"} className={`text-[11px] ${r.verdict === "Yes" ? "bg-[#F0FDF4] text-[#22C55E]" : r.verdict === "No" ? "bg-[#FEF2F2] text-[#EF4444]" : "bg-[#F8FAFC] text-[#64748B]"}`}>{r.verdict}</Badge>
                    </td>
                    <td className="px-5 py-3.5 text-right text-sm font-mono text-[#22C55E]">{r.upside_pct ? `+${Number(r.upside_pct).toFixed(1)}%` : "—"}</td>
                    <td className="px-5 py-3.5 text-right text-xs text-[#94A3B8]">{r.created_at ? new Date(r.created_at).toLocaleDateString("zh-CN") : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
