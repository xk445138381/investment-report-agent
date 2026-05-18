"use client";

import { useState, useEffect, useRef, Suspense, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { generateReport, streamProgress, type TaskStatus } from "@/lib/api";

/* ------------------------------------------------------------------ */
/*  Mock animation (used when backend is unavailable)                 */
/* ------------------------------------------------------------------ */
const PHASE_AGENTS = [
  "行情数据、财报数据、公告新闻、宏观行业",
  "财务分析、估值建模、行业竞争、公司治理",
  "多头论点、空头论点、风险裁判",
  "章节撰写、图表生成、标题摘要",
];

const INITIAL_PHASES = [
  { id: "p1", num: "01", name: "数据聚合", agents: ["行情数据","财报数据","公告新闻","宏观行业"] },
  { id: "p2", num: "02", name: "深度分析", agents: ["财务分析","估值建模","行业竞争","公司治理"] },
  { id: "p3", num: "03", name: "多空辩论", agents: ["多头论点","空头论点","风险裁判"] },
  { id: "p4", num: "04", name: "统稿排版", agents: ["章节撰写","图表生成","标题摘要"] },
];

const DEBATE = {
  bull: ["超高 ROE (28.5%) 和宽阔护城河支撑估值溢价","直销占比提升将直接推升净利率 5.2%","消费升级趋势下高端白酒需求刚性"],
  bear: ["宏观经济放缓抑制商务消费场景","行业监管趋严，消费税改革风险上升","当前 PE 处于近 5 年 72% 分位"],
};

function useMockProgress(ticker: string, depth: string, onComplete: () => void) {
  const [phase, setPhase] = useState(0);
  const [logs, setLogs] = useState<string[]>([]);
  const [showDebate, setShowDebate] = useState(false);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    setLogs([`▶ 开始分析 ${ticker} (600519.SH) — ${depth === "deep" ? "深度研报" : "快速简报"}`]);

    const schedule = [{ p: 1, d: 600 }, { p: 2, d: 1300 }, { p: 3, d: 2100 }, { p: 4, d: 3000 }];
    const timers: ReturnType<typeof setTimeout>[] = [];
    schedule.forEach((s) => {
      timers.push(setTimeout(() => {
        setPhase(s.p);
        setLogs((prev) => [...prev, `✓ Phase ${s.p} 完成 — ${PHASE_AGENTS[s.p - 1]}`]);
        if (s.p === 3) setShowDebate(true);
        if (s.p === 4) setTimeout(onComplete, 500);
      }, s.d));
    });
    return () => timers.forEach(clearTimeout);
  }, []);

  return { phase, logs, showDebate };
}

/* ------------------------------------------------------------------ */
/*  Real backend progress hook (via SSE)                              */
/* ------------------------------------------------------------------ */
function useRealProgress(taskId: string, ticker: string, onComplete: () => void) {
  const [phase, setPhase] = useState(0);
  const [logs, setLogs] = useState<string[]>([`▶ 开始分析 ${ticker} — task: ${taskId.slice(0, 8)}…`]);
  const [showDebate, setShowDebate] = useState(false);

  useEffect(() => {
    const abort = streamProgress(taskId, (event, data) => {
      if (event === "progress") {
        setLogs((prev) => [...prev, `⏳ ${data}`]);
        // Parse phase from SSE message like "phase_2_analysis (50%)"
        const phaseMap: Record<string, number> = {
          phase_1: 1, phase_2: 2, phase_3: 3, phase_4: 4,
        };
        for (const [key, p] of Object.entries(phaseMap)) {
          if (data.includes(key)) { setPhase(p); break; }
        }
        if (data.includes("debate") || data.includes("phase_3")) setShowDebate(true);
      } else if (event === "complete") {
        setPhase(4);
        setLogs((prev) => [...prev, "✓ 报告生成完成"]);
        setTimeout(onComplete, 800);
      } else if (event === "error") {
        setLogs((prev) => [...prev, `✗ ${data}`]);
      }
    });
    return abort;
  }, [taskId]);

  return { phase, logs, showDebate };
}

/* ------------------------------------------------------------------ */
/*  Content (wrapped in Suspense for useSearchParams)                 */
/* ------------------------------------------------------------------ */
function ProgressContent() {
  const params = useSearchParams();
  const router = useRouter();
  const ticker = params.get("ticker") || "贵州茅台";
  const depth = params.get("depth") || "deep";

  const [mode, setMode] = useState<"connecting" | "real" | "mock">("connecting");
  const [taskId, setTaskId] = useState<string | null>(null);
  const started = useRef(false);

  const handleComplete = useCallback(() => {
    router.push(`/report?ticker=${encodeURIComponent(ticker)}`);
  }, [ticker, router]);

  // Try to connect to real backend first
  useEffect(() => {
    if (started.current) return;
    started.current = true;

    (async () => {
      try {
        const res = await generateReport({ ticker, report_type: depth as "deep_dive" | "brief" });
        setTaskId(res.task_id);
        setMode("real");
      } catch {
        setMode("mock");
      }
    })();
  }, []);

  const mockProgress = useMockProgress(ticker, depth, handleComplete);
  const realProgress = useRealProgress(taskId || "", ticker, handleComplete);

  const { phase, logs, showDebate } = mode === "real" ? realProgress : mockProgress;

  return (
    <div className="max-w-[780px] mx-auto px-8 py-12">
      <div className="text-center mb-8">
        <div className="font-display text-[36px] font-bold text-ink-primary leading-tight">{ticker}</div>
        <div className="font-mono text-xs text-ink-tertiary mt-1">
          600519.SH · {depth === "deep" ? "深度研报" : "快速简报"}
          {mode === "connecting" && <span className="ml-2 text-accent">连接后端…</span>}
          {mode === "real" && <span className="ml-2 text-data-positive">实时生成</span>}
          {mode === "mock" && <span className="ml-2 text-ink-tertiary">Demo</span>}
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
      <div className="grid grid-cols-4 gap-2.5 mb-7">
        {INITIAL_PHASES.map((p, i) => (
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

      {/* Debate preview */}
      {showDebate && (
        <div className="grid grid-cols-2 gap-2.5 mb-7 animate-[slideIn_0.3s_ease]">
          <div className="p-3.5 bg-bg-surface border border-border-light">
            <div className="text-[10px] font-mono text-data-positive tracking-[0.06em] mb-2">BULL CASE</div>
            {DEBATE.bull.map((t, i) => <div key={i} className="text-xs text-ink-secondary mb-1.5 leading-relaxed">· {t}</div>)}
          </div>
          <div className="p-3.5 bg-bg-surface border border-border-light">
            <div className="text-[10px] font-mono text-accent tracking-[0.06em] mb-2">BEAR CASE</div>
            {DEBATE.bear.map((t, i) => <div key={i} className="text-xs text-ink-secondary mb-1.5 leading-relaxed">· {t}</div>)}
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
