"use client";

import { useState, useEffect, useRef, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { generateReport, streamProgress } from "@/lib/api";

const INITIAL_PHASES = [
  { id: "p1", num: "01", name: "数据聚合", agents: ["行情数据","财报数据","公告新闻","宏观行业"] },
  { id: "p2", num: "02", name: "深度分析", agents: ["财务分析","估值建模","行业竞争","公司治理"] },
  { id: "p3", num: "03", name: "多空辩论", agents: ["多头论点","空头论点","风险裁判"] },
  { id: "p4", num: "04", name: "统稿排版", agents: ["章节撰写","图表生成","标题摘要"] },
];

const SCAN_PHASES = [
  { id: "s1", num: "01", name: "数据聚合", agents: ["行情","财报","技术指标","资金流向","新闻"] },
  { id: "s2", num: "02", name: "LLM 总结", agents: ["一句话买卖建议"] },
];

const VALUE_PHASES = [
  { id: "v1", num: "01", name: "数据聚合", agents: ["行情数据","财报数据","公告新闻","宏观行业"] },
  { id: "v2", num: "02", name: "财务分析", agents: ["财务分析","估值建模","行业竞争","公司治理"] },
  { id: "v3", num: "03", name: "价值评估", agents: ["段永平视角","芒格视角"] },
  { id: "v3b", num: "03b", name: "综合裁决", agents: ["双视角裁决官"] },
  { id: "v4", num: "04", name: "统稿排版", agents: ["章节撰写","图表生成","标题摘要"] },
];

const DEBATE = {
  bull: ["超高 ROE (28.5%) 和宽阔护城河支撑估值溢价","直销占比提升将直接推升净利率 5.2%","消费升级趋势下高端白酒需求刚性"],
  bear: ["宏观经济放缓抑制商务消费场景","行业监管趋严，消费税改革风险上升","当前 PE 处于近 5 年 72% 分位"],
};

const VALUE_DEBATE = {
  duan: ["商业模式清晰度：这个生意怎么赚钱？十年后还能赚钱吗？","企业文化与本分：管理层在做对的事吗？","现金流确定性：利润里有几分真金白银？"],
  munger: ["反过来想：这笔投资最可能怎么死？","Lollapalooza 检测：多种风险因子同时发力的场景","激励机制诊断：管理层与股东利益对齐吗？"],
};

function ProgressContent() {
  const params = useSearchParams();
  const router = useRouter();
  const ticker = params.get("ticker") || "贵州茅台";
  const depth = params.get("depth") || "deep";
  const template = params.get("template") || "deep_dive_default";
  const isValue = template === "value_investor";
  const isScan = template === "quick_scan";
  const phases = isScan ? SCAN_PHASES : isValue ? VALUE_PHASES : INITIAL_PHASES;

  const [phase, setPhase] = useState(0);
  const [logs, setLogs] = useState<string[]>([`▶ 开始分析 ${ticker}…`]);
  const [showDebate, setShowDebate] = useState(false);
  const [mode, setMode] = useState<"connecting" | "real" | "mock">("connecting");
  const started = useRef(false);

  const goReport = (tid?: string) => {
    const params = new URLSearchParams({ ticker });
    if (tid) params.set("task", tid);
    router.push(`/report?${params.toString()}`);
  };

  useEffect(() => {
    if (started.current) return;
    started.current = true;

    (async () => {
      // Try real backend first
      try {
        const res = await generateReport({ ticker, report_type: depth as "deep_dive" | "brief", template_id: template });
        setLogs((prev) => [...prev, `✓ 分析任务启动: ${res.task_id.slice(0, 8)}…`]);
        setMode("real");

        const abort = streamProgress(res.task_id, (event, data) => {
          if (event === "progress") {
            setLogs((prev) => [...prev, `⏳ ${data}`]);
            if (data.includes("phase_2")) setPhase(2);
            else if (data.includes("phase_3")) { setPhase(3); setShowDebate(true); }
            else if (data.includes("phase_4")) setPhase(4);
            else if (data.includes("phase_1")) setPhase(1);
          } else if (event === "complete") {
            setPhase(4);
            setLogs((prev) => [...prev, "✓ 报告生成完成"]);
            setTimeout(() => goReport(res.task_id), 800);
          } else if (event === "error") {
            setLogs((prev) => [...prev, `✗ ${data}`]);
          }
        });
        return () => abort();
      } catch {
        // Fall back to mock
        setLogs((prev) => [...prev, "后端未连接，使用 Demo 模式"]);
        setMode("mock");
      }
    })();
  }, []);

  // Mock progress (only when API fails)
  useEffect(() => {
    if (mode !== "mock") return;
    setLogs((prev) => [...prev, `▶ Demo: ${ticker} (600519.SH) — ${depth === "deep" ? "深度研报" : "快速简报"}`]);
    const schedule = [{ p: 1, d: 600 }, { p: 2, d: 1300 }, { p: 3, d: 2100 }, { p: 4, d: 3000 }];
    const timers: ReturnType<typeof setTimeout>[] = [];
    schedule.forEach((s) => {
      timers.push(setTimeout(() => {
        setPhase(s.p);
        if (s.p === 3) setShowDebate(true);
        if (s.p === 4) setTimeout(() => goReport(), 500);
      }, s.d));
    });
    return () => timers.forEach(clearTimeout);
  }, [mode]);

  return (
    <div className="max-w-[780px] mx-auto px-8 py-12">
      <div className="text-center mb-8">
        <div className="font-display text-[36px] font-bold text-ink-primary leading-tight">{ticker}</div>
        <div className="font-mono text-xs text-ink-tertiary mt-1">
          600519.SH · {depth === "deep" ? "深度研报" : "快速简报"}
          <span className={`ml-2 ${mode === "real" ? "text-data-positive" : mode === "mock" ? "text-ink-tertiary" : "text-accent"}`}>
            {mode === "connecting" ? "连接中…" : mode === "real" ? "实时" : "Demo"}
          </span>
        </div>
      </div>

      {/* Progress bar */}
      <div className="mb-7">
        <div className="h-0.5 bg-border-light">
          <div className="h-full bg-accent transition-[width] duration-[0.6s]" style={{ width: `${phase * 25}%` }} />
        </div>
        <div className="flex justify-between text-[11px] text-ink-tertiary font-mono mt-1.5">
          <span>Phase {phase} / 4</span><span>{phase * 25}%</span>
        </div>
      </div>

      {/* Phase cards */}
      <div className={`grid gap-2.5 mb-7 ${isScan ? 'grid-cols-2' : isValue ? 'grid-cols-5' : 'grid-cols-4'}`}>
        {phases.map((p, i) => (
          <div key={p.id} className={`p-3.5 relative ${
            i < phase ? "bg-bg-surface border border-data-positive" :
            i === phase ? "bg-accent-soft border border-accent" :
            "bg-bg-surface border border-border-light opacity-40"
          }`}>
            <div className="font-display text-2xl font-bold text-ink-primary opacity-10 absolute top-1 right-2">{p.num}</div>
            <div className="font-serif text-[13px] font-semibold text-ink-primary mb-1.5">{p.name}</div>
            {p.agents.map((a, j) => {
              const state = i < phase ? "done" : i === phase && j === 0 ? "running" : "pending";
              return (
                <div key={a} className="text-[10px] text-ink-secondary mb-0.5 flex items-center gap-1.5">
                  <span className={`inline-block w-[5px] h-[5px] ${
                    state === "running" ? "bg-accent animate-[pulse_1.2s_infinite]" :
                    state === "done" ? "bg-data-positive" : "bg-border"
                  }`} />{a}
                </div>
              );
            })}
          </div>
        ))}
      </div>

      {/* Debate / Value Perspectives */}
      {showDebate && (
        <div className="grid grid-cols-2 gap-2.5 mb-7 animate-[slideIn_0.3s_ease]">
          <div className="p-3.5 bg-bg-surface border border-border-light">
            <div className="text-[10px] font-mono text-data-positive tracking-[0.06em] mb-2">
              {isValue ? "段永平视角" : "BULL CASE"}
            </div>
            {(isValue ? VALUE_DEBATE.duan : DEBATE.bull).map((t, i) => (
              <div key={i} className="text-xs text-ink-secondary mb-1.5 leading-relaxed">· {t}</div>
            ))}
          </div>
          <div className="p-3.5 bg-bg-surface border border-border-light">
            <div className="text-[10px] font-mono text-accent tracking-[0.06em] mb-2">
              {isValue ? "芒格视角" : "BEAR CASE"}
            </div>
            {(isValue ? VALUE_DEBATE.munger : DEBATE.bear).map((t, i) => (
              <div key={i} className="text-xs text-ink-secondary mb-1.5 leading-relaxed">· {t}</div>
            ))}
          </div>
        </div>
      )}

      {/* Logs */}
      <div className="p-3.5 bg-bg-surface border border-border-light max-h-[180px] overflow-y-auto font-mono text-[11px] leading-[2]">
        {logs.map((l, i) => (
          <div key={i} className={l.startsWith("✓") ? "text-ink-secondary" : l.startsWith("✗") ? "text-accent" : l.startsWith("⏳") ? "text-ink-tertiary" : "text-accent"}>
            <span className="text-ink-tertiary mr-2.5">{new Date().toLocaleTimeString("zh-CN", { hour12: false })}</span>
            {l}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function ProgressPage() {
  return (
    <Suspense fallback={<div className="max-w-[780px] mx-auto px-8 py-12 text-center text-ink-tertiary">加载分析管线…</div>}>
      <ProgressContent />
    </Suspense>
  );
}
