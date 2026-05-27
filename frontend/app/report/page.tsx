"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";

type Section = { title: string; content: string };
type NewsItem = { title: string; summary: string; date: string; source: string };

/* ── Mock data (fallback when no backend) ── */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Data = any;

const MOCK: Data = {
  score: { total: 30.2, max: 32, rating: "EXCELLENT" },
  val: { weighted_value: 2440, weighted_upside_pct: 83.1, signal: "undervalued" },
  verdict: "STRONG_BUY", verdict_conf: 85,
  current_price: 1332.95,
  isValueTemplate: false,
  sections: {
    executive_summary: { title: "投资摘要", content: "贵州茅台（600519.SH）当前 1332.95 元。判定：Yes（可买）。估计内在价值 2440 元，上行空间 83.1%。财务底子：EXCELLENT（30.2/32分）。商业模式清晰，看得懂。" },
    business_model: { title: "商业模式", content: "高 ROE（24.3%）表明公司具备可持续竞争优势。毛利率 68.4%，产品或服务有定价权——客户离不开你。几乎零负债（D/E 0.15），管理层不赌。段永平会说：这生意我看得懂，不需要复杂模型。" },
    corporate_character: { title: "企业文化与本分", content: "股权结构：中国贵州茅台酒厂集团 54.4%（国有）| 香港中央结算 4.7% | 贵州国有资本运营 4.6%。本分评分 85/100。财务保守（低杠杆），管理层不赌——好信号。" },
    financial_health: { title: "财务健康与现金流", content: "财务综合评分 30.2/32 — EXCELLENT\nROE 24.3% | FCF/净利 0.92 | 负债权益比 0.15 | 营收增长 +15.2%\n底线：这盘生意的财务底子好。" },
    valuation: { title: "估值与安全边际", content: "内在价值 2440 元/股（当前 1332.95，+83.1%）。DCF: 3248 | Owner Earnings: 1632。安全边际 45%（>30%，足够厚）。低于 1708 开始买入，低于 1220 可重仓。" },
    inversion_checklist: { title: "逆向风险清单", content: "初步排查未发现明显致命风险。但芒格会提醒：你的检查清单本身可能有盲点。系统性风险：竞争颠覆/监管突变/宏观黑天鹅。" },
    dual_verdict: { title: "双重视角裁决", content: "段永平：好生意+好价格。芒格：同意，但保持谦虚。共识：商业模式清晰+未发现致命风险。分歧：无实质分歧。Yes。" },
    final_judgment: { title: "综合判定", content: "贵州茅台 — Yes（置信度 85%）。买价参考：低于 1708 开始买入，低于 1220 重仓。仓位建议：最多 10%（单一标的上限）。" },
  },
};

const MOCK_NEWS: NewsItem[] = [
  { title: '国海证券：贵州茅台提价，维持买入评级', summary: '茅台提价传递市场化之声，Q2经营弹性可期。', date: '2026-05-18', source: '腾讯云' },
  { title: '多款茅台酒将首次上线i茅台', summary: '此前刚上调部分茅台酒产品价格，最高每瓶涨200元。', date: '2026-05-18', source: '新浪' },
  { title: '茅台调整i茅台和门店购酒时间', summary: '或瞄准即时零售机遇，推进直销渠道建设。', date: '2026-05-18', source: '腾讯云' },
];

function ReportContent() {
  const params = useSearchParams();
  const ticker = params.get("ticker") || "贵州茅台";
  const taskId = params.get("task");

  type ChartData = { chart_id: string; title: string; caption?: string; png_base64: string; position: string; width_px?: number };
const [data, setData] = useState(taskId ? null : MOCK);
const [newsItems, setNewsItems] = useState<NewsItem[]>(taskId ? [] : MOCK_NEWS);
const [charts, setCharts] = useState<ChartData[]>([]);
const [macroData, setMacroData] = useState<Record<string,unknown>|null>(null);
const [ownership, setOwnership] = useState("");
const [loading, setLoading] = useState(!!taskId);

  useEffect(() => {
    if (!taskId) return;
    (async () => {
      try {
        const res = await fetch(`http://localhost:8000/api/v1/report/${taskId}`);
        if (!res.ok) throw new Error("Failed");
        const raw = await res.json();

        const sw = raw?.section_writer?.result;
        const fa = raw?.financial_analysis?.result;
        const val = raw?.valuation?.result;
        const judge = raw?.value_judge?.result || raw?.risk_judge?.result;
        const price = raw?.price_data?.result?.price_summary || {};
        const newsRaw = raw?.news_data?.result?.recent_events || [];
        const sections = sw?.sections || {};
        const isValueTemplate = !!raw?.value_judge;

        setData({
          score: fa?.financial_health_score || {},
          val: { weighted_value: val?.weighted_value, weighted_upside_pct: val?.weighted_upside_pct, signal: val?.signal },
          verdict: judge?.verdict || "HOLD",
          verdict_conf: judge?.verdict_confidence || 50,
          current_price: price?.latest_price || val?.current_price || 0,
          sections,
          isValueTemplate,
        });
        setNewsItems(newsRaw.map((e: Record<string, unknown>) => ({
          title: String(e.title || ""),
          summary: String(e.summary || ""),
          date: String(e.date || ""),
          source: String(e.source || ""),
        })));
        // Chart data
        const chartsRaw = raw?.chart_generator?.result || [];
        setCharts(Array.isArray(chartsRaw) ? chartsRaw : []);
        // Macro data
        setMacroData(raw?.macro_data?.result?.macro || null);
        // Ownership
        const govResult = raw?.corporate_governance?.result;
        if (govResult?.ownership_structure && !govResult.ownership_structure.includes("待补充")) {
          setOwnership(String(govResult.ownership_structure));
        }
      } catch {
        setData(MOCK);
        setNewsItems(MOCK_NEWS);
      }
      setLoading(false);
    })();
  }, [taskId]);

  if (loading) return (
    <div className="max-w-[720px] mx-auto px-8 py-16 text-center">
      <div className="font-serif text-2xl font-bold text-ink-primary mb-4">{ticker}</div>
      <div className="text-ink-tertiary">加载分析报告…</div>
    </div>
  );

  if (!data) return null;

  const { score, val, verdict, current_price, sections, isValueTemplate } = data;
  const showNews = newsItems.length > 0;
  const verdictLabel: Record<string, string> = {
    STRONG_BUY: "买入", BUY: "买入", HOLD: "持有", SELL: "卖出", STRONG_SELL: "卖出",
    Yes: "可买", No: "不买", "Too Hard": "太难",
  };
  const verdictDisplay = verdictLabel[verdict] || verdict;
  const verdictClass = verdict === "Yes" || verdict === "STRONG_BUY" ? "text-accent" :
    verdict === "No" || verdict === "STRONG_SELL" ? "text-accent" : "text-ink-primary";

  return (
    <div className="max-w-[720px] mx-auto px-8 py-16">
      {/* Cover */}
      <div className="text-center py-12 border-b border-border-light mb-9">
        <div className="font-mono text-[10px] text-ink-tertiary tracking-[0.12em] mb-3.5">
          {isValueTemplate ? "VALUE INVESTING REPORT" : "DEEP DIVE REPORT"}
        </div>
        <h1 className="font-serif text-[28px] font-bold text-ink-primary tracking-[0.04em] leading-tight">{ticker}</h1>
        <p className="font-serif text-base text-ink-secondary mt-2">综合判定：<span className={verdictClass}>{verdictDisplay}</span></p>
        <p className="font-mono text-[11px] text-ink-tertiary mt-4">{new Date().toISOString().slice(0, 10)} · {isValueTemplate ? "段永平×芒格 双重视角" : "深度研究报告"}</p>
      </div>

      {/* Rating cards - value template shows different labels */}
      <div className="grid grid-cols-4 gap-2.5 mb-8">
        {(isValueTemplate ? [
          { l: "财务底子", v: score.rating || "N/A", c: score.rating === "EXCELLENT" ? "text-data-positive" : "text-ink-primary" },
          { l: "估值空间", v: val.signal === "undervalued" ? "安全边际" : val.signal === "overvalued" ? "偏贵" : "合理", c: val.signal === "undervalued" ? "text-accent" : "text-ink-secondary" },
          { l: "商业模式", v: (val as Data).weighted_upside_pct > 0 ? "清晰" : "需观察", c: "text-ink-primary" },
          { l: "风险水平", v: verdict === "Too Hard" ? "复杂" : "可控", c: verdict === "Too Hard" ? "text-ink-tertiary" : "text-ink-secondary" },
        ] : [
          { l: "财务健康", v: score.rating || "N/A", c: score.rating === "EXCELLENT" ? "text-data-positive" : "text-ink-primary" },
          { l: "估值水平", v: val.signal === "undervalued" ? "低估" : val.signal === "overvalued" ? "高估" : "合理", c: val.signal === "undervalued" ? "text-accent" : "text-ink-secondary" },
          { l: "成长前景", v: "稳健", c: "text-ink-primary" },
          { l: "风险等级", v: "中等", c: "text-ink-secondary" },
        ]).map((r) => (
          <div key={r.l} className="p-4 text-center bg-bg-surface border border-border-light">
            <div className="text-[10px] text-ink-tertiary font-mono tracking-[0.06em] mb-1">{r.l}</div>
            <div className={`font-serif text-[22px] font-semibold ${r.c}`}>{r.v}</div>
          </div>
        ))}
      </div>

      {/* Key data */}
      <div className="grid grid-cols-3 gap-2.5 mb-8">
        {[
          { l: "当前价格", v: current_price ? current_price.toLocaleString() : "N/A", s: "CNY" },
          { l: "加权目标价", v: val.weighted_value ? val.weighted_value.toFixed(2) : "N/A", s: `${val.weighted_upside_pct ? (val.weighted_upside_pct > 0 ? "+" : "") + val.weighted_upside_pct.toFixed(1) + "%" : ""}`, sc: (val.weighted_upside_pct || 0) > 0 ? "text-accent" : "" },
          { l: "综合评级", v: verdictLabel[verdict] || verdict, s: `置信度 ${data.verdict_conf || 50}%`, sc: verdict.includes("BUY") ? "text-accent" : verdict.includes("SELL") ? "text-accent" : "" },
        ].map((k) => (
          <div key={k.l} className="p-5 text-center bg-bg-surface border border-border-light">
            <div className="text-[10px] text-ink-tertiary font-mono tracking-[0.06em] mb-1">{k.l}</div>
            <div className={`font-display text-[34px] font-bold leading-tight ${k.sc || "text-ink-primary"}`}>{k.v}</div>
            <div className={`text-[11px] mt-0.5 ${k.sc || "text-ink-tertiary"}`}>{k.s}</div>
          </div>
        ))}
      </div>

      {/* Financial health score bar */}
      {score.total && (
        <div className="mb-8 p-5 bg-bg-surface border border-border-light">
          <div className="font-serif text-[15px] font-semibold text-ink-primary mb-3">财务健康评分</div>
          <div className="flex items-center gap-4">
            <div className="flex-1 h-2 bg-border-light">
              <div className="h-full bg-data-positive transition-all" style={{ width: `${(score.total / score.max) * 100}%` }} />
            </div>
            <span className="font-mono text-sm font-bold text-data-positive">{score.total}/{score.max}</span>
            <span className="text-[11px] font-mono text-ink-tertiary">{score.rating}</span>
          </div>
        </div>
      )}

      {/* Sections */}
      {sections && Object.keys(sections).length > 0 && (
        <div className="space-y-6">
          {Object.entries(sections as Record<string, { title: string; content: string }>).map(([key, sec]) => {
            if (!sec || !sec.content) return null;
            return (
              <div key={key} className="mb-6">
                <div className="font-serif text-[17px] font-semibold text-ink-primary mb-3">{sec.title || key}</div>
                <div className="text-[13px] text-ink-secondary leading-relaxed whitespace-pre-line">{sec.content}</div>
              </div>
            );
          })}
        </div>
      )}

      {/* Charts from pipeline */}
      {charts.length > 0 && (
        <div className="space-y-6 mb-8">
          {charts.map((c) => (
            <div key={c.chart_id} className="bg-bg-surface border border-border-light p-4">
              <img
                src={`data:image/png;base64,${c.png_base64}`}
                alt={c.title}
                className="w-full h-auto"
                style={{ maxWidth: c.width_px ? `${c.width_px}px` : '100%' }}
              />
              <div className="text-[11px] text-ink-tertiary text-center mt-2">{c.title}</div>
              {c.caption && <div className="text-[10px] text-ink-tertiary text-center mt-0.5">{c.caption}</div>}
            </div>
          ))}
        </div>
      )}

      {/* Chart placeholder fallback (when no charts from pipeline) */}
      {charts.length === 0 && current_price > 0 && (
        <div className="mb-8 p-8 bg-bg-surface border border-dashed border-border text-center">
          <div className="flex items-end justify-center gap-2 h-[100px]">
            {[40,55,45,70,55,82,62,75].map((h, i) => (
              <div key={i} className={`flex-1 max-w-[40px] ${h === 82 ? "bg-accent" : "bg-data-series-3"} opacity-70`} style={{ height: `${h}%` }} />
            ))}
          </div>
          <div className="text-[11px] text-ink-tertiary mt-3.5">股价走势（图表引擎就绪，生成深度研报以渲染）</div>
        </div>
      )}

      {/* Macro data */}
      {macroData && (macroData.gdp_growth_yoy || macroData.cpi_yoy || macroData.analysis) && (
        <div className="mb-8 p-4 bg-bg-surface border border-border-light">
          <div className="font-serif text-[15px] font-semibold text-ink-primary mb-3">宏观环境</div>
          <div className="grid grid-cols-4 gap-3 mb-3">
            {macroData.gdp_growth_yoy != null && (
              <div className="text-center p-2">
                <div className="text-[10px] text-ink-tertiary font-mono">GDP 增速</div>
                <div className="font-mono text-lg font-bold text-ink-primary">{String(macroData.gdp_growth_yoy)}%</div>
              </div>
            )}
            {macroData.cpi_yoy != null && (
              <div className="text-center p-2">
                <div className="text-[10px] text-ink-tertiary font-mono">CPI</div>
                <div className="font-mono text-lg font-bold text-ink-primary">{String(macroData.cpi_yoy)}%</div>
              </div>
            )}
            {macroData.m2_growth_yoy != null && (
              <div className="text-center p-2">
                <div className="text-[10px] text-ink-tertiary font-mono">M2 增速</div>
                <div className="font-mono text-lg font-bold text-ink-primary">{String(macroData.m2_growth_yoy)}%</div>
              </div>
            )}
            {macroData.pmi != null && (
              <div className="text-center p-2">
                <div className="text-[10px] text-ink-tertiary font-mono">PMI</div>
                <div className="font-mono text-lg font-bold text-ink-primary">{String(macroData.pmi)}</div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Ownership */}
      {ownership && (
        <div className="mb-8 p-4 bg-bg-surface border border-border-light">
          <div className="font-serif text-[15px] font-semibold text-ink-primary mb-2">股权结构</div>
          <div className="text-[13px] text-ink-secondary">{ownership}</div>
        </div>
      )}

      {/* News section */}
      {showNews && newsItems.length > 0 && (
        <div className="mb-8">
          <div className="font-serif text-[17px] font-semibold text-ink-primary mb-3">近期动态</div>
          <div className="space-y-2">
            {newsItems.slice(0, 5).map((n, i) => (
              <div key={i} className="p-3 bg-bg-surface border border-border-light">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="text-[13px] text-ink-primary font-medium leading-relaxed">{n.title}</div>
                    <div className="text-[12px] text-ink-secondary mt-1 leading-relaxed">{n.summary}</div>
                  </div>
                  <div className="text-[10px] text-ink-tertiary font-mono whitespace-nowrap">{n.date?.slice(0, 10)}</div>
                </div>
                <div className="text-[10px] text-ink-tertiary mt-1 font-mono">{n.source}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Export */}
      <div className="flex justify-center gap-4 mb-12 mt-8 print:hidden">
        <button onClick={() => window.print()} className="px-6 py-2.5 text-[13px] font-sans border border-border bg-bg-surface text-ink-primary cursor-pointer hover:bg-bg-warm transition-colors">导出 PDF</button>
        <button className="px-6 py-2.5 text-[13px] font-sans border border-border bg-bg-surface text-ink-primary cursor-pointer hover:bg-bg-warm transition-colors opacity-40" title="即将支持">导出 Word</button>
      </div>

      {/* Disclaimer */}
      <div className="text-center pt-12 border-t border-border-light text-[11px] text-ink-tertiary">
        AI 辅助生成 · 仅供参考 · 不构成投资建议<br />Generated by 研报 Agent · Research Platform
        {taskId && <div className="mt-1 font-mono text-[9px]">task: {taskId.slice(0, 8)}</div>}
      </div>
    </div>
  );
}

export default function ReportPage() {
  return (
    <Suspense fallback={<div className="max-w-[720px] mx-auto px-8 py-12 text-center text-ink-tertiary">加载报告…</div>}>
      <ReportContent />
    </Suspense>
  );
}
