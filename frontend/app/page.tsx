"use client";

import { useState, useRef, useEffect } from "react";

/* ── Placeholder SVG for report preview screen ── */
function ReportPlaceholder() {
  return (
    <div className="max-w-3xl mx-auto space-y-8 py-12">
      <div className="text-center space-y-3 mb-12">
        <p className="text-ink-tertiary text-sm tracking-widest uppercase font-mono">DEEP DIVE REPORT</p>
        <h1 className="font-serif text-3xl font-bold text-ink-primary">
          贵州茅台 (600519.SH)
        </h1>
        <p className="text-lg text-ink-secondary font-serif">护城河坚固，估值具备吸引力</p>
      </div>

      {/* Rating Cards */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "财务健康", score: "优秀", color: "text-data-positive" },
          { label: "估值水平", score: "低估", color: "text-accent" },
          { label: "成长前景", score: "稳健", color: "text-ink-secondary" },
          { label: "风险等级", score: "中等", color: "text-ink-secondary" },
        ].map((c) => (
          <div key={c.label} className="bg-bg-surface border border-border-light p-4 text-center">
            <p className="text-xs text-ink-tertiary mb-1">{c.label}</p>
            <p className={`text-lg font-serif font-semibold ${c.color}`}>{c.score}</p>
          </div>
        ))}
      </div>

      {/* Key Data */}
      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-1 bg-bg-surface border border-border-light p-6 text-center space-y-2">
          <p className="text-xs text-ink-tertiary tracking-widest uppercase">当前价格</p>
          <p className="data-headline">1,680</p>
          <p className="text-xs text-ink-tertiary">CNY</p>
        </div>
        <div className="col-span-1 bg-bg-surface border border-border-light p-6 text-center space-y-2">
          <p className="text-xs text-ink-tertiary tracking-widest uppercase">目标价格</p>
          <p className="data-headline">1,970</p>
          <p className="text-xs text-accent">+17.3% 上行空间</p>
        </div>
        <div className="col-span-1 bg-bg-surface border border-border-light p-6 text-center space-y-2">
          <p className="text-xs text-ink-tertiary tracking-widest uppercase">综合评级</p>
          <p className="data-headline text-accent">买入</p>
          <p className="text-xs text-ink-tertiary">置信度 72%</p>
        </div>
      </div>

      {/* TOC */}
      <div className="border-t border-b border-border-light py-6">
        <h2 className="font-serif text-lg font-semibold mb-4 text-ink-primary">目录</h2>
        <div className="grid grid-cols-2 gap-2 text-sm">
          {[
            "1. 投资摘要",
            "2. 公司概况",
            "3. 行业分析",
            "4. 财务分析",
            "5. 估值分析",
            "6. 风险提示",
            "7. 投资建议",
          ].map((s) => (
            <p key={s} className="text-ink-secondary hover:text-ink-primary cursor-pointer transition-colors">
              {s}
            </p>
          ))}
        </div>
      </div>

      {/* Chart placeholder */}
      <div className="bg-bg-surface border border-border-light p-8 flex items-center justify-center">
        <div className="text-center space-y-3">
          <div className="w-64 h-32 mx-auto flex items-end justify-between gap-2 px-4">
            {[40, 65, 45, 75, 50, 85, 60, 70].map((h, i) => (
              <div key={i} className="flex-1 bg-data-series-3" style={{ height: `${h}%` }} />
            ))}
          </div>
          <p className="text-xs text-ink-tertiary">营收/净利润趋势图</p>
        </div>
      </div>

      <p className="text-xs text-ink-tertiary text-center pt-8">
        AI 辅助生成 · 仅供参考 · 不构成投资建议
      </p>
    </div>
  );
}

/* ── Main Page Component ── */
export default function Home() {
  const [input, setInput] = useState("");
  const [view, setView] = useState<"chat" | "report">("chat");
  const [messages, setMessages] = useState<{ role: string; text: string }[]>([]);
  const [status, setStatus] = useState<"idle" | "running" | "done">("idle");
  const [progress, setProgress] = useState({ phase: "", pct: 0 });
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSubmit = async () => {
    if (!input.trim() || status === "running") return;
    const userMsg = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text: userMsg }]);
    setStatus("running");

    // Simulate progress for demo (no backend connected)
    const phases = [
      { phase: "数据采集", pct: 20 },
      { phase: "财务分析", pct: 45 },
      { phase: "多空辩论", pct: 70 },
      { phase: "统稿排版", pct: 90 },
    ];
    for (const p of phases) {
      await new Promise((r) => setTimeout(r, 200));
      setProgress(p);
    }
    setStatus("done");
    setProgress({ phase: "完成", pct: 100 });
    setMessages((prev) => [
      ...prev,
      { role: "assistant", text: "报告已生成。" },
    ]);
    // Don't auto-switch — let user click "查看完整报告"
  };

  const suggestions = [
    "分析贵州茅台",
    "快速看下宁德时代",
    "深度研报 腾讯控股",
  ];

  if (view === "report") {
    return (
      <div className="min-h-[calc(100vh-73px)] px-8 pb-16">
        {/* Top bar */}
        <div className="sticky top-0 bg-bg-warm/95 backdrop-blur-sm border-b border-border-light py-3 flex items-center justify-between mb-8">
          <button
            onClick={() => { setView("chat"); setMessages([]); setStatus("idle"); }}
            className="text-sm text-ink-secondary hover:text-ink-primary transition-colors"
          >
            ← 返回对话
          </button>
          <div className="flex gap-4">
            <button className="px-5 py-2 text-sm border border-border bg-bg-surface text-ink-primary hover:bg-bg-warm transition-colors">
              导出 PDF
            </button>
            <button className="px-5 py-2 text-sm border border-border bg-bg-surface text-ink-primary hover:bg-bg-warm transition-colors">
              导出 Word
            </button>
          </div>
        </div>
        <ReportPlaceholder />
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-73px)] px-8 pb-16">
      {messages.length === 0 ? (
        /* ── Blank state: command entry ── */
        <div className="flex flex-col items-center gap-12 max-w-2xl w-full">
          <div className="text-center space-y-6">
            <div className="flex items-center justify-center gap-4">
              <div className="w-12 h-px bg-border" />
              <h1 className="font-serif text-4xl font-bold text-ink-primary tracking-wide">
                研报 Agent
              </h1>
              <div className="w-12 h-px bg-border" />
            </div>
            <p className="text-lg text-ink-secondary leading-relaxed max-w-md mx-auto">
              基于多 Agent 协作的专业投资研究报告生成
            </p>
          </div>

          {/* Suggestions */}
          <div className="flex flex-wrap justify-center gap-3">
            {suggestions.map((s) => (
              <button
                key={s}
                onClick={() => { setInput(s); inputRef.current?.focus(); }}
                className="px-5 py-2.5 text-sm text-ink-secondary bg-bg-surface
                           border border-border-light hover:border-border
                           hover:text-ink-primary transition-all duration-200"
              >
                {s}
              </button>
            ))}
          </div>

          {/* Command bar */}
          <div className="w-full">
            <div
              className="flex items-center gap-4 px-6 py-4 bg-bg-elevated
                          border border-border-light
                          focus-within:border-accent transition-colors duration-300"
            >
              <span className="text-ink-tertiary text-lg">$</span>
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
                placeholder="输入公司名称或股票代码…"
                className="flex-1 bg-transparent text-lg text-ink-primary
                           placeholder:text-ink-tertiary outline-none font-sans"
              />
              <button
                onClick={handleSubmit}
                disabled={status === "running"}
                className="px-6 py-2 bg-accent text-white text-sm font-medium
                           hover:bg-accent-hover disabled:opacity-40
                           transition-colors duration-200"
              >
                {status === "running" ? "生成中…" : "生成报告 →"}
              </button>
            </div>
          </div>
        </div>
      ) : (
        /* ── Chat flow ── */
        <div className="w-full max-w-3xl space-y-8">
          {messages.map((m, i) => (
            <div
              key={i}
              className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[75%] px-6 py-4 ${
                  m.role === "user"
                    ? "bg-accent-soft text-ink-primary border border-accent-soft"
                    : "bg-bg-surface text-ink-primary border border-border-light"
                }`}
              >
                <p className="text-sm leading-relaxed whitespace-pre-wrap">{m.text}</p>
              </div>
            </div>
          ))}

          {/* Progress indicator */}
          {status === "running" && (
            <div className="flex justify-start">
              <div className="max-w-[75%] w-full px-6 py-5 bg-bg-surface border border-border-light space-y-4">
                <div className="flex items-center gap-3">
                  <div className="w-2.5 h-2.5 bg-accent" />
                  <span className="text-sm text-ink-secondary">
                    {progress.phase || "准备中…"}
                  </span>
                  <span className="text-xs text-ink-tertiary font-mono ml-auto">
                    {progress.pct}%
                  </span>
                </div>
                <div className="w-full h-1 bg-border-light">
                  <div
                    className="h-full bg-accent transition-all duration-500 ease-out"
                    style={{ width: `${progress.pct}%` }}
                  />
                </div>
              </div>
            </div>
          )}

          {/* View report button after completion */}
          {status === "done" && (
            <div className="flex justify-center pt-4">
              <button
                onClick={() => setView("report")}
                className="px-8 py-3 bg-accent text-white text-sm font-medium
                           hover:bg-accent-hover transition-colors duration-200"
              >
                查看完整报告
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
