"use client";

import { useState, useEffect, useRef, Suspense, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { generateReport, streamProgress } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const PHASES: Record<string, { num: string; name: string; agents: string[] }[]> = {
  scan: [
    { num: "01", name: "数据聚合", agents: ["行情", "财报", "技术指标", "资金流向", "新闻"] },
    { num: "02", name: "LLM 总结", agents: ["一句话买卖建议"] },
  ],
  value: [
    { num: "01", name: "数据聚合", agents: ["行情数据", "财报数据", "公告新闻", "宏观行业"] },
    { num: "02", name: "财务分析", agents: ["财务分析", "估值建模", "行业竞争", "公司治理"] },
    { num: "03", name: "价值评估", agents: ["段永平视角", "芒格视角"] },
    { num: "03b", name: "综合裁决", agents: ["双视角裁决官"] },
    { num: "04", name: "统稿排版", agents: ["章节撰写", "图表生成", "标题摘要"] },
  ],
  deep: [
    { num: "01", name: "数据聚合", agents: ["行情数据", "财报数据", "公告新闻", "宏观行业"] },
    { num: "02", name: "深度分析", agents: ["财务分析", "估值建模", "行业竞争", "公司治理"] },
    { num: "03", name: "多空辩论", agents: ["多头论点", "空头论点", "风险裁判"] },
    { num: "04", name: "统稿排版", agents: ["章节撰写", "图表生成", "标题摘要"] },
  ],
};

const REPORT_TYPE_BY_DEPTH: Record<string, string> = {
  scan: "quick_scan",
  value: "value_deep_dive",
  deep: "deep_dive",
  brief: "brief",
};

function ProgressContent() {
  const params = useSearchParams();
  const router = useRouter();
  const ticker = params.get("ticker") || "贵州茅台";
  const depth = params.get("depth") || "deep";
  const template = params.get("template") || "deep_dive_default";
  const phases = PHASES[depth] || PHASES.deep;

  const [phase, setPhase] = useState(0);
  const [logs, setLogs] = useState<string[]>([`▶ 开始分析 ${ticker}…`]);
  const [agentStatus, setAgentStatus] = useState<Record<string, string>>({});
  const [mode, setMode] = useState<"connecting" | "real" | "error">("connecting");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const started = useRef(false);

  const goReport = useCallback((tid?: string) => {
    const p = new URLSearchParams({ ticker });
    if (tid) p.set("task", tid);
    router.push(`/report?${p.toString()}`);
  }, [router, ticker]);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    (async () => {
      try {
        const reportType = REPORT_TYPE_BY_DEPTH[depth] || "deep_dive";
        const res = await generateReport({ ticker, report_type: reportType, template_id: template });
        setLogs(prev => [...prev, `✓ 任务启动: ${res.task_id.slice(0, 8)}…`]);
        setMode("real");
        streamProgress(res.task_id, (event, data) => {
          if (event === "progress") {
            setLogs(prev => [...prev, `⏳ ${data}`]);
            if (data.includes("phase_2")) setPhase(2); else if (data.includes("phase_3")) setPhase(3); else if (data.includes("phase_4")) setPhase(4); else if (data.includes("phase_1")) setPhase(1);
          } else if (event === "agent_completed") {
            try { const p = JSON.parse(data); if (p.agent) setAgentStatus(prev => ({ ...prev, [p.agent]: p.status })); } catch {}
          } else if (event === "complete") {
            setLogs(prev => [...prev, "✓ 报告生成完成"]); setTimeout(() => goReport(res.task_id), 800);
          } else if (event === "error") {
            setMode("error");
            setErrorMessage(data || "报告生成失败");
            setLogs(prev => [...prev, `✗ ${data || "报告生成失败"}`]);
          }
        });
      } catch (e) {
        const message = e instanceof Error ? e.message : "后端未连接，真实报告未生成";
        setMode("error");
        setErrorMessage(message);
        setLogs(prev => [...prev, `✗ ${message}`]);
      }
    })();
  }, [depth, goReport, template, ticker]);

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div><h1 className="text-2xl font-bold text-[#1C2434]">正在分析 {ticker}</h1><p className="text-sm text-[#64748B] mt-1">多 Agent 协作生成报告中</p></div>

      {mode === "error" && (
        <Card className="border-[#FCA5A5] bg-[#FEF2F2]">
          <CardContent className="p-4">
            <div className="text-sm font-semibold text-[#991B1B]">真实报告未生成</div>
            <div className="text-xs text-[#B91C1C] mt-1">
              {errorMessage || "后端连接失败。系统已停止，不会静默展示 Demo 报告。"}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Phase Progress */}
      <Card className="border-[#E2E8F0]">
        <CardContent className="p-5">
          <div className="flex gap-2 mb-4">
            {phases.map((p, i) => (
              <div key={p.num} className="flex-1 h-1.5 rounded-full" style={{ background: i <= phase ? "#3B82F6" : "#E2E8F0" }} />
            ))}
          </div>
          <div className="grid grid-cols-5 gap-2">
            {phases.map((p, i) => (
              <div key={p.num} className={`p-2 rounded-lg text-center ${i === phase ? "bg-[#EFF6FF] border border-[#BFDBFE]" : i < phase ? "bg-[#F0FDF4]" : "bg-[#F8FAFC]"}`}>
                <div className="text-[10px] text-[#64748B] font-mono mb-0.5">{p.num}</div>
                <div className="text-xs font-medium text-[#1C2434]">{p.name}</div>
                {p.agents.map(a => (
                  <div key={a} className="text-[9px] text-[#94A3B8] mt-0.5 flex items-center gap-1 justify-center">
                    <span className={`w-1.5 h-1.5 rounded-full ${i < phase ? "bg-[#22C55E]" : i === phase ? "bg-[#3B82F6] animate-pulse" : "bg-[#E2E8F0]"}`} />
                    {a}
                  </div>
                ))}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Agent Status */}
      {Object.keys(agentStatus).length > 0 && (
        <Card className="border-[#E2E8F0]">
          <CardContent className="p-4">
            <h3 className="text-xs font-semibold text-[#64748B] mb-2">AGENT 完成状态</h3>
            <div className="flex flex-wrap gap-2">
              {Object.entries(agentStatus).map(([name, status]) => (
                <Badge key={name} variant={status === "done" ? "positive" : "secondary"} className={`text-[10px] ${status === "done" ? "bg-[#F0FDF4] text-[#22C55E]" : "bg-[#F8FAFC] text-[#64748B]"}`}>{name}: {status === "done" ? "✓" : status}</Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Log */}
      <Card className="border-[#E2E8F0]">
        <CardContent className="p-4 max-h-40 overflow-y-auto">
          {logs.map((l, i) => <div key={i} className="text-xs text-[#64748B] py-0.5 font-mono">{l}</div>)}
        </CardContent>
      </Card>
    </div>
  );
}

export default function ProgressPage() {
  return <Suspense fallback={<div className="text-center py-12 text-[#94A3B8]">加载中…</div>}><ProgressContent /></Suspense>;
}
