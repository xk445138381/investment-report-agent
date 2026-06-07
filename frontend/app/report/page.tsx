"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Download, BookmarkPlus, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiUrl } from "@/lib/api";

type Section = { title: string; content: string };
type Prediction = { prediction: string; current: string; range: string };
type DataQuality = {
  status: "real" | "partial" | "empty" | "demo";
  prices_count?: number;
  financials_count?: number;
  missing?: string[];
  data_sources?: Record<string, string | null>;
  provider_trace?: { dataset: string; provider: string; status: string; records: number }[];
  as_of?: string;
};
type ReportData = {
  score: { total?: number; max?: number; rating?: string };
  val: { weighted_value?: number; weighted_upside_pct?: number; signal?: string };
  verdict: string;
  verdict_conf: number;
  current_price: number;
  isValueTemplate: boolean;
  sections: Record<string, Section>;
};

const MOCK: ReportData = {
  score: { total: 30.2, max: 32, rating: "EXCELLENT" },
  val: { weighted_value: 2440, weighted_upside_pct: 83.1, signal: "undervalued" },
  verdict: "STRONG_BUY", verdict_conf: 85, current_price: 1332.95, isValueTemplate: false,
  sections: {
    executive_summary: { title: "投资摘要", content: "Demo 演示 — 仅供界面参考，非真实分析结果。请输入真实任务查看实际报告。" },
    business_model: { title: "商业模式", content: "Demo 演示 — 此处展示商业模式分析框架（护城河、定价权、竞争格局）。实际报告由 AI 多 Agent 协同生成。" },
    financial_health: { title: "财务健康与现金流", content: "Demo 演示 — 此处展示 ROE、FCF/净利润、负债权益比等财务指标。实际数据从 TradingAgents/QVeris 实时获取。" },
    valuation: { title: "估值与安全边际", content: "Demo 演示 — 此处展示 DCF 三阶段模型 + Owner Earnings 估值结果及安全边际计算。" },
    inversion_checklist: { title: "逆向风险清单", content: "Demo 演示 — 此处展示多角度风控排查的结果。" },
    dual_verdict: { title: "双重视角裁决", content: "Demo 演示 — 此处展示段永平+芒格双视角交叉验证结果。" },
    final_judgment: { title: "综合判定", content: "Demo 演示 — 此处展示综合判定结论及置信度。注意：以上内容均为 Demo 示例，不代表任何真实投资建议。" },
  },
};

function ReportContent() {
  const params = useSearchParams();
  const ticker = params.get("ticker") || "Demo";
  const taskId = params.get("task");

  const [data, setData] = useState<ReportData | null>(taskId ? null : MOCK);
  const [dataQuality, setDataQuality] = useState<DataQuality | null>(taskId ? null : {
    status: "demo",
    prices_count: 0,
    financials_count: 0,
    missing: ["prices", "financials"],
    provider_trace: [],
  });
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(!!taskId);
  const [qnaQuestion, setQnaQuestion] = useState("");
  const [qnaAsking, setQnaAsking] = useState(false);
  const [qnaHistory, setQnaHistory] = useState<{ q: string; a: string }[]>([]);
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [archived, setArchived] = useState(false);
  const [expandedSection, setExpandedSection] = useState<string | null>(null);
  const [showPfModal, setShowPfModal] = useState(false);
  const [pfShares, setPfShares] = useState(100);
  const [pfAdded, setPfAdded] = useState(false);
  const [pfAdding, setPfAdding] = useState(false);

  const addToPortfolio = async () => {
    if (!taskId || pfAdding || pfAdded) return;
    setPfAdding(true);
    try {
      await fetch(apiUrl("/portfolio"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ticker, shares: pfShares, entry_price: data?.current_price || 0, name: ticker, task_id: taskId }) });
      setPfAdded(true); setShowPfModal(false);
    } catch {}
    setPfAdding(false);
  };

  const askQuestion = async () => {
    if (!qnaQuestion.trim() || !taskId || qnaAsking) return;
    setQnaAsking(true);
    try {
      const res = await fetch(apiUrl(`/report/${taskId}/ask`), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: qnaQuestion }) });
      const d = await res.json();
      setQnaHistory(prev => [...prev, { q: qnaQuestion, a: d.answer || "无法回答" }]);
      setQnaQuestion("");
    } catch { setQnaHistory(prev => [...prev, { q: qnaQuestion, a: "请求失败" }]); }
    setQnaAsking(false);
  };

  const doArchive = async () => {
    if (!taskId || archived) return;
    try { await fetch(apiUrl("/archive"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ task_id: taskId }) }); setArchived(true); } catch {}
  };

  useEffect(() => {
    if (!taskId) return;
    (async () => {
      try {
        const res = await fetch(apiUrl(`/report/${taskId}`));
        if (!res.ok) throw new Error(`报告读取失败（HTTP ${res.status}）`);
        const raw = await res.json();
        const sw = raw?.section_writer?.result;
        const fa = raw?.financial_analysis?.result;
        const val = raw?.valuation?.result;
        const price = raw?.price_data?.result?.price_summary || {};
        setDataQuality(raw?.data_quality?.result || null);
        setData({
          score: fa?.financial_health_score || {}, val: { weighted_value: val?.weighted_value, weighted_upside_pct: val?.weighted_upside_pct, signal: val?.signal },
          verdict: raw?.value_judge?.result?.verdict || raw?.risk_judge?.result?.verdict || "HOLD",
          verdict_conf: raw?.value_judge?.result?.verdict_confidence || 50,
          current_price: price?.latest_price || val?.current_price || 0, sections: sw?.sections || {}, isValueTemplate: !!raw?.value_judge,
        });
        if (raw?.predictions) setPredictions(raw.predictions);
      } catch (e) {
        const message = e instanceof Error ? e.message : "报告读取失败";
        setErrorMessage(message);
        setData(null);
      }
      setLoading(false);
    })();
  }, [taskId]);

  if (loading) return <div className="text-center py-12 text-[#94A3B8]">加载中…</div>;
  if (errorMessage) return (
    <div className="max-w-2xl mx-auto py-12">
      <Card className="border-[#FCA5A5] bg-[#FEF2F2]">
        <CardContent className="p-5">
          <div className="text-sm font-semibold text-[#991B1B]">真实报告读取失败</div>
          <div className="text-xs text-[#B91C1C] mt-1">{errorMessage}</div>
          <div className="text-xs text-[#7F1D1D] mt-3">系统已停止，不会用 Demo 报告替代真实结果。</div>
        </CardContent>
      </Card>
    </div>
  );
  if (!data) return <div className="text-center py-12 text-[#94A3B8]">暂无报告数据</div>;

  const { score, val, verdict, current_price, sections } = data;
  const verdictColor = verdict === "Yes" || verdict === "STRONG_BUY" ? "text-[#22C55E]" : verdict === "No" || verdict === "STRONG_SELL" ? "text-[#EF4444]" : "text-[#64748B]";
  const dataStatus = dataQuality?.status || "empty";
  const dataStatusLabel: Record<string, string> = {
    real: "真实数据",
    partial: "部分降级",
    empty: "数据缺失",
    demo: "Demo 数据",
  };
  const dataStatusClass: Record<string, string> = {
    real: "bg-[#F0FDF4] text-[#166534] border-[#BBF7D0]",
    partial: "bg-[#FFFBEB] text-[#92400E] border-[#FDE68A]",
    empty: "bg-[#FEF2F2] text-[#991B1B] border-[#FCA5A5]",
    demo: "bg-[#F8FAFC] text-[#475569] border-[#E2E8F0]",
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Back + Actions */}
      <div className="flex items-center justify-between">
        <Link href="/reports" className="flex items-center gap-1 text-sm text-[#64748B] hover:text-[#1C2434] no-underline"><ArrowLeft className="w-4 h-4" /> 返回列表</Link>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setShowPfModal(true)} disabled={pfAdded} className="text-xs h-8"><Plus className="w-3 h-3 mr-1" />{pfAdded ? "已加入组合" : "模拟组合"}</Button>
          <Button variant="outline" size="sm" onClick={doArchive} disabled={archived} className="text-xs h-8"><BookmarkPlus className="w-3 h-3 mr-1" />{archived ? "已归档" : "归档"}</Button>
          <Button variant="outline" size="sm" className="text-xs h-8"><Download className="w-3 h-3 mr-1" />导出</Button>
        </div>
      </div>

      {/* Cover */}
      <Card className="border-[#E2E8F0] shadow-sm">
        <CardContent className="p-6">
          <div className="flex items-start justify-between">
            <div>
              <div className="text-xs font-semibold text-[#3B82F6] tracking-wider mb-1">{data.isValueTemplate ? "VALUE INVESTING" : "DEEP DIVE"}</div>
              <h1 className="text-2xl font-bold text-[#1C2434]">{ticker}</h1>
              <div className="flex items-center gap-2 mt-2">
                <span className="text-sm text-[#64748B]">综合判定：</span>
                <span className={`text-lg font-bold ${verdictColor}`}>{verdict === "STRONG_BUY" ? "买入" : verdict === "Yes" ? "可买" : verdict === "HOLD" ? "持有" : verdict}</span>
                <Badge variant="outline" className="text-[11px] bg-[#F8FAFC]">{data.verdict_conf}% 置信度</Badge>
              </div>
            </div>
            <div className="text-right">
              <div className="text-sm text-[#64748B]">当前价格</div>
              <div className="text-3xl font-bold text-[#1C2434]">¥{current_price?.toLocaleString()}</div>
              {val?.weighted_upside_pct && <div className="text-sm font-medium text-[#22C55E]">+{val.weighted_upside_pct.toFixed(1)}%</div>}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Data Quality */}
      {dataQuality && (
        <Card className={`border ${dataStatusClass[dataStatus] || dataStatusClass.empty}`}>
          <CardContent className="p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-sm font-semibold">{dataStatusLabel[dataStatus] || "数据状态未知"}</div>
                <div className="text-xs mt-1 opacity-80">
                  行情 {dataQuality.prices_count ?? 0} 条 · 财报 {dataQuality.financials_count ?? 0} 条
                  {dataQuality.as_of ? ` · ${dataQuality.as_of.slice(0, 19).replace("T", " ")}` : ""}
                </div>
              </div>
              {dataQuality.missing && dataQuality.missing.length > 0 && (
                <div className="text-xs font-medium">
                  缺失：{dataQuality.missing.join(", ")}
                </div>
              )}
            </div>
            {dataQuality.provider_trace && dataQuality.provider_trace.length > 0 && (
              <div className="grid grid-cols-2 gap-2 mt-3">
                {dataQuality.provider_trace.map((p) => (
                  <div key={p.dataset} className="rounded-md border border-current/20 bg-white/45 p-2">
                    <div className="text-[11px] font-semibold">{p.dataset}</div>
                    <div className="text-[11px] opacity-80">{p.provider} · {p.status} · {p.records} 条</div>
                  </div>
                ))}
              </div>
            )}
            {dataStatus === "demo" && (
              <div className="text-xs mt-3 opacity-80">
                当前页面没有真实任务 id，展示的是显式 Demo 数据。
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Rating cards */}
      <div className="grid grid-cols-4 gap-3">
        {[{ l: "财务健康", v: score.rating || "N/A" }, { l: "估值水平", v: val?.signal === "undervalued" ? "低估" : "合理" }, { l: "目标价", v: val?.weighted_value ? `¥${val.weighted_value.toFixed(0)}` : "N/A" }, { l: "安全边际", v: val?.weighted_upside_pct ? `${val.weighted_upside_pct.toFixed(0)}%` : "N/A" }].map(s => (
          <Card key={s.l} className="border-[#E2E8F0]"><CardContent className="p-4 text-center"><div className="text-xs text-[#64748B] mb-1">{s.l}</div><div className="text-lg font-bold text-[#1C2434]">{s.v}</div></CardContent></Card>
        ))}
      </div>

      {/* Sections */}
      {sections && Object.keys(sections).length > 0 && (
        <div className="space-y-3">
          {Object.entries(sections as Record<string, Section>).map(([key, sec]) => {
            if (!sec?.content) return null;
            const isOpen = expandedSection === key;
            return (
              <Card key={key} className="border-[#E2E8F0] cursor-pointer" onClick={() => setExpandedSection(isOpen ? null : key)}>
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-[#1C2434]">{sec.title || key}</h3>
                    <span className="text-xs text-[#94A3B8]">{isOpen ? "▲" : "▼"}</span>
                  </div>
                  {isOpen && <div className="mt-3 text-sm text-[#64748B] leading-relaxed whitespace-pre-line">{sec.content}</div>}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Predictions */}
      {predictions.length > 0 && (
        <Card className="border-[#E2E8F0]">
          <CardContent className="p-4">
            <h3 className="text-sm font-semibold text-[#1C2434] mb-3">📊 可证伪预测（12个月后回测）</h3>
            {predictions.map((p, i) => (
              <div key={i} className="flex items-start gap-3 py-2 border-b border-[#E2E8F0] last:border-0">
                <span className="text-xs font-mono text-[#94A3B8]">#{i + 1}</span>
                <div><div className="text-sm text-[#1C2434]">{p.prediction}</div><div className="text-xs text-[#94A3B8] mt-0.5">当前: {p.current} · 预测: {p.range}</div></div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Q&A */}
      {taskId && (
        <Card className="border-[#E2E8F0]">
          <CardContent className="p-4">
            <h3 className="text-sm font-semibold text-[#1C2434] mb-3">💬 追问这份报告</h3>
            <div className="flex gap-2 mb-3">
              <Input value={qnaQuestion} onChange={e => setQnaQuestion(e.target.value)} onKeyDown={e => e.key === "Enter" && askQuestion()} placeholder="如：这个安全边际是怎么算的？" className="border-[#E2E8F0]" />
              <Button onClick={askQuestion} disabled={qnaAsking || !qnaQuestion.trim()} size="sm">{qnaAsking ? "…" : "追问"}</Button>
            </div>
            {qnaHistory.length > 0 && (
              <div className="max-h-48 overflow-y-auto space-y-2 border-t border-[#E2E8F0] pt-3">
                {qnaHistory.map((qa, i) => (
                  <div key={i}><div className="text-xs font-medium text-[#3B82F6]">Q: {qa.q}</div><div className="text-sm text-[#64748B] mt-0.5">{qa.a}</div></div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Portfolio Modal */}
      {showPfModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setShowPfModal(false)}>
          <div className="bg-white rounded-xl border border-[#E2E8F0] p-6 w-80 shadow-lg" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-[#1C2434] mb-4">加入模拟组合 — {ticker}</h3>
            <div className="space-y-3 mb-4">
              <div><label className="text-xs text-[#64748B] mb-1 block">持有股数</label><Input type="number" value={pfShares} onChange={e => setPfShares(parseInt(e.target.value) || 0)} className="border-[#E2E8F0]" min={1} /></div>
              <div className="text-xs text-[#94A3B8]">投入: ¥{(pfShares * (current_price || 0)).toLocaleString()}</div>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" className="flex-1" onClick={() => setShowPfModal(false)}>取消</Button>
              <Button className="flex-1 bg-[#3B82F6]" onClick={addToPortfolio} disabled={pfAdding || pfShares <= 0}>{pfAdding ? "添加中…" : "确认加入"}</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ReportPage() {
  return <Suspense fallback={<div className="text-center py-12 text-[#94A3B8]">加载报告…</div>}><ReportContent /></Suspense>;
}
