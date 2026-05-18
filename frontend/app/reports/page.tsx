"use client";

const MOCK_REPORTS = [
  { id: "1", ticker: "600519.SH", name: "贵州茅台", type: "深度研报", date: "2026-05-17", verdict: "买入", upside: "+17.3%" },
  { id: "2", ticker: "300750.SZ", name: "宁德时代", type: "深度研报", date: "2026-05-16", verdict: "买入", upside: "+22.1%" },
  { id: "3", ticker: "000858.SZ", name: "五粮液", type: "快速简报", date: "2026-05-15", verdict: "持有", upside: "+4.5%" },
];

export default function ReportsPage() {
  return (
    <div className="max-w-[860px] mx-auto px-8 py-12">
      <div className="font-serif text-[22px] font-bold text-ink-primary mb-1.5">报告列表</div>
      <div className="text-[13px] text-ink-secondary mb-7">管理已生成的研究报告。数据仅保存在当前会话中。</div>

      <div className="border border-border-light">
        {/* Header */}
        <div className="grid grid-cols-[2fr_1fr_1fr_1fr] px-4 py-2.5 bg-bg-surface text-[10px] font-mono text-ink-tertiary tracking-[0.06em] border-b border-border-light">
          <div>标的</div><div>类型</div><div>日期</div><div>评级</div>
        </div>
        {MOCK_REPORTS.map((r) => (
          <div key={r.id} className="grid grid-cols-[2fr_1fr_1fr_1fr] px-4 py-3 text-[13px] border-b border-border-light cursor-pointer hover:bg-bg-surface transition-colors items-center">
            <div>
              <div className="font-medium text-ink-primary">{r.name}</div>
              <div className="font-mono text-[11px] text-ink-tertiary">{r.ticker}</div>
            </div>
            <div className="text-ink-secondary">{r.type}</div>
            <div className="font-mono text-[11px] text-ink-tertiary">{r.date}</div>
            <div className="flex items-center gap-2">
              <span className={r.verdict === "买入" ? "text-accent font-medium" : "text-ink-secondary"}>{r.verdict}</span>
              <span className={`font-mono text-[10px] ${r.upside.startsWith("+") ? "text-data-positive" : "text-ink-tertiary"}`}>{r.upside}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="text-center py-10 text-xs text-ink-tertiary">
        数据仅保存在当前会话 · 刷新后清空 · <code className="font-mono text-[11px]">GET /reports</code> 端点待后端实现
      </div>
    </div>
  );
}
