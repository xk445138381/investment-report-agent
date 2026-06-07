"use client";

import { useState, useEffect } from "react";
import { TrendingUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { apiUrl } from "@/lib/api";

type Position = { ticker: string; name: string; shares: number; entry_price: number; current_price: number; cost_basis: number; market_value: number; pnl: number; pnl_pct: number; task_id: string | null };
type PortfolioSummary = { positions_count?: number; total_cost?: number; total_market_value?: number; total_pnl?: number; total_pnl_pct?: number };

export default function PortfolioPage() {
  const [positions, setPositions] = useState<Position[]>([]);
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchPortfolio = () => {
    fetch(apiUrl("/portfolio")).then(r => r.json()).then(d => { setPositions(d.positions || []); setSummary(d.summary || null); }).catch(() => {}).finally(() => setLoading(false));
  };
  useEffect(fetchPortfolio, []);

  const closePosition = async (ticker: string) => { try { await fetch(apiUrl(`/portfolio/${ticker}`), { method: "DELETE" }); fetchPortfolio(); } catch {} };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-[#1C2434]">模拟组合</h1>

      {loading && <div className="text-center py-10 text-sm text-[#94A3B8]">加载中…</div>}

      {!loading && positions.length === 0 && (
        <Card className="border-[#E2E8F0]"><CardContent className="p-10 text-center"><TrendingUp className="w-10 h-10 text-[#94A3B8] mx-auto mb-3" /><p className="text-sm text-[#64748B]">组合为空，在报告中点击「模拟组合」加入持仓</p></CardContent></Card>
      )}

      {!loading && positions.length > 0 && (
        <>
          {/* Summary */}
          <div className="grid grid-cols-4 gap-4">
            {[{ l: "持有标的", v: `${summary?.positions_count || 0} 只` }, { l: "总投入", v: `¥${(summary?.total_cost || 0).toLocaleString()}` }, { l: "总市值", v: `¥${(summary?.total_market_value || 0).toLocaleString()}` }, { l: "总盈亏", v: `${(summary?.total_pnl || 0) >= 0 ? "+" : ""}${(summary?.total_pnl_pct || 0).toFixed(1)}%`, c: (summary?.total_pnl || 0) >= 0 ? "text-[#22C55E]" : "text-[#EF4444]" }].map(s => (
              <Card key={s.l} className="border-[#E2E8F0]"><CardContent className="p-4 text-center"><div className="text-xs text-[#64748B] mb-1">{s.l}</div><div className={`text-xl font-bold ${s.c || "text-[#1C2434]"}`}>{s.v}</div></CardContent></Card>
            ))}
          </div>

          {/* Table */}
          <Card className="border-[#E2E8F0] shadow-sm overflow-hidden">
            <table className="w-full">
              <thead><tr className="border-b border-[#E2E8F0] bg-[#F8FAFC]">
                <th className="text-left text-xs font-semibold text-[#64748B] px-5 py-3">标的</th>
                <th className="text-right text-xs font-semibold text-[#64748B] px-5 py-3">持仓</th>
                <th className="text-right text-xs font-semibold text-[#64748B] px-5 py-3">成本</th>
                <th className="text-right text-xs font-semibold text-[#64748B] px-5 py-3">现价</th>
                <th className="text-right text-xs font-semibold text-[#64748B] px-5 py-3">市值</th>
                <th className="text-right text-xs font-semibold text-[#64748B] px-5 py-3">盈亏</th>
                <th className="text-right text-xs font-semibold text-[#64748B] px-5 py-3"></th>
              </tr></thead>
              <tbody>
                {positions.map(pos => (
                  <tr key={pos.ticker} className="border-b border-[#E2E8F0] hover:bg-[#F8FAFC]">
                    <td className="px-5 py-3.5"><div className="text-sm font-medium text-[#1C2434]">{pos.name}</div><div className="text-xs text-[#94A3B8] font-mono">{pos.ticker}</div></td>
                    <td className="px-5 py-3.5 text-right text-sm text-[#64748B]">{pos.shares}</td>
                    <td className="px-5 py-3.5 text-right text-sm font-mono text-[#64748B]">¥{pos.entry_price.toFixed(2)}</td>
                    <td className="px-5 py-3.5 text-right text-sm font-mono text-[#64748B]">¥{pos.current_price.toFixed(2)}</td>
                    <td className="px-5 py-3.5 text-right text-sm font-mono text-[#64748B]">¥{pos.market_value.toLocaleString()}</td>
                    <td className="px-5 py-3.5 text-right">
                      <div className={`text-sm font-mono font-medium ${pos.pnl >= 0 ? "text-[#22C55E]" : "text-[#EF4444]"}`}>
                        {pos.pnl >= 0 ? "+" : ""}{pos.pnl_pct.toFixed(1)}%
                      </div>
                    </td>
                    <td className="px-5 py-3.5 text-right"><Button variant="ghost" size="sm" className="text-xs text-[#94A3B8] hover:text-[#EF4444]" onClick={() => closePosition(pos.ticker)}>卖出</Button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </>
      )}
    </div>
  );
}
