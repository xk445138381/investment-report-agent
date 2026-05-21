"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";

type Depth = "brief" | "deep" | "custom";

const PIPELINE_PHASES = [
  { id: "p1", num: "01", name: "数据聚合", agents: ["行情数据", "财报数据", "公告新闻", "宏观行业"] },
  { id: "p2", num: "02", name: "深度分析", agents: ["财务分析", "估值建模", "行业竞争", "公司治理"] },
  { id: "p3", num: "03", name: "多空辩论", agents: ["多头论点", "空头论点", "风险裁判"] },
  { id: "p4", num: "04", name: "统稿排版", agents: ["章节撰写", "图表生成", "标题摘要"] },
];

const ALL_AGENTS = PIPELINE_PHASES.flatMap((p) => p.agents);

const SUGGESTIONS = ["贵州茅台", "宁德时代", "AAPL", "五粮液", "MSFT", "恒瑞医药"];

const DEPTHS: { id: Depth; name: string; time: string; desc: string }[] = [
  { id: "brief", name: "快速简报", time: "约 45s", desc: "精简版：核心财务 + 简要估值 + 关键风险。6 Agent 管线。" },
  { id: "deep", name: "深度研报", time: "约 2min", desc: "全流程分析：四阶段管线、牛熊辩论、完整估值模型。14 Agent。" },
  { id: "custom", name: "自定义", time: "按配置", desc: "自由选择 Agent 组合、调整辩论轮次、指定 LLM 模型。" },
];

const TEMPLATES = [
  { id: "default", name: "深度研报（默认）", desc: "7 章节，10 图表" },
  { id: "brief_tpl", name: "快速简报", desc: "4 章节，4 图表" },
  { id: "cn_equity", name: "A 股专用", desc: "含行业对标、政策分析" },
];

export default function HomePage() {
  const router = useRouter();
  const [ticker, setTicker] = useState("");
  const [depth, setDepth] = useState<Depth>("deep");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [wizardStep, setWizardStep] = useState(1);
  const [template, setTemplate] = useState("default");
  const [selectedAgents, setSelectedAgents] = useState<string[]>([...ALL_AGENTS]);

  const handleStart = useCallback(() => {
    if (!ticker.trim()) return;
    router.push(`/progress?ticker=${encodeURIComponent(ticker)}&depth=${depth}`);
  }, [ticker, depth, router]);

  const toggleAgent = (name: string) => {
    setSelectedAgents((prev) =>
      prev.includes(name) ? prev.filter((a) => a !== name) : [...prev, name]
    );
  };

  return (
    <div className="max-w-[720px] mx-auto px-8 py-12">
      {/* Hero */}
      <div className="text-center mb-10">
        <h2 className="font-serif text-[28px] font-bold text-ink-primary tracking-[0.04em] mb-2">
          生成专业投资研究报告
        </h2>
        <p className="text-sm text-ink-secondary max-w-[420px] mx-auto leading-relaxed">
          多 Agent 协作 — 数据聚合、深度分析、多空辩论、统稿排版，四阶段管线产出机构级研报。
        </p>
      </div>

      {/* Command bar */}
      <div
        className={`flex items-center gap-2 max-w-[520px] mx-auto bg-bg-elevated border px-4 py-0.5 transition-colors duration-300 ${
          ticker ? "border-accent" : "border-border-light"
        }`}
      >
        <span className="font-mono text-[15px] text-ink-tertiary">$</span>
        <input
          type="text"
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleStart()}
          placeholder="输入公司名称或股票代码…"
          autoFocus
          className="flex-1 border-none outline-none text-sm font-sans bg-transparent text-ink-primary py-2.5 placeholder:text-ink-tertiary"
        />
        <button
          onClick={handleStart}
          disabled={!ticker.trim()}
          className="px-5 py-2 text-[13px] font-medium font-sans border-none cursor-pointer bg-accent text-white transition-colors duration-200 hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
        >
          生成报告 →
        </button>
      </div>

      {/* Suggestions */}
      <div className="flex justify-center gap-1.5 mt-3 flex-wrap">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => setTicker(s)}
            className="px-3.5 py-1 text-[11px] font-sans bg-bg-surface text-ink-secondary border border-border-light cursor-pointer transition-all duration-150 hover:border-border hover:text-ink-primary"
          >
            {s}
          </button>
        ))}
      </div>

      {/* Depth selector */}
      <div className="mt-8">
        <div className="text-center font-serif text-[15px] text-ink-primary mb-3.5 font-semibold">
          分析深度
        </div>
        <div className="flex gap-2.5 justify-center">
          {DEPTHS.map((d) => (
            <div
              key={d.id}
              onClick={() => setDepth(d.id)}
              className={`w-[200px] p-3.5 cursor-pointer transition-all duration-200 ${
                depth === d.id
                  ? "bg-accent-soft border-accent"
                  : "bg-bg-surface border-border-light"
              } border`}
            >
              <div className="font-serif text-sm font-semibold text-ink-primary mb-1">{d.name}</div>
              <div className="font-mono text-[10px] text-ink-tertiary mb-1.5">{d.time}</div>
              <div className="text-[11px] text-ink-secondary leading-relaxed">{d.desc}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Advanced toggle */}
      <div className="text-center mt-6">
        <button
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="text-xs text-ink-tertiary cursor-pointer bg-transparent border-none font-sans py-1 transition-colors duration-200 hover:text-accent"
        >
          {showAdvanced ? "收起高级配置 ▲" : "高级配置… ▼"}
        </button>
      </div>

      {/* Advanced wizard */}
      {showAdvanced && (
        <div className="mt-5 p-6 bg-bg-surface border border-border-light animate-[slideIn_0.3s_ease]">
          {/* Step indicator */}
          <div className="flex items-center justify-center gap-0 mb-6">
            {[
              { n: 1, t: "模板" },
              { n: 2, t: "Agent" },
              { n: 3, t: "参数" },
            ].map((s, i) => (
              <div key={s.n} className="flex items-center gap-0">
                {i > 0 && (
                  <div
                    className={`w-9 h-px ${
                      wizardStep > i ? "bg-accent" : "bg-border-light"
                    }`}
                  />
                )}
                <div
                  className={`w-7 h-7 rounded-full flex items-center justify-center font-mono text-[11px] font-medium ${
                    wizardStep >= s.n
                      ? "bg-accent text-white"
                      : "bg-bg-surface text-ink-tertiary border border-border-light"
                  }`}
                >
                  {wizardStep > s.n ? "✓" : s.n}
                </div>
                <span
                  className={`text-[10px] ml-1.5 ${
                    wizardStep >= s.n
                      ? "text-ink-primary font-semibold"
                      : "text-ink-tertiary"
                  }`}
                >
                  {s.t}
                </span>
              </div>
            ))}
          </div>

          {/* Step 1: Template */}
          {wizardStep === 1 &&
            TEMPLATES.map((t) => (
              <div
                key={t.id}
                onClick={() => {
                  setTemplate(t.id);
                  setWizardStep(2);
                }}
                className={`p-3 mb-1.5 cursor-pointer flex justify-between items-center ${
                  template === t.id
                    ? "bg-accent-soft border border-accent"
                    : "bg-bg-elevated border border-border-light"
                }`}
              >
                <div>
                  <div className="font-serif text-[13px] font-semibold text-ink-primary">{t.name}</div>
                  <div className="text-[11px] text-ink-secondary mt-0.5">{t.desc}</div>
                </div>
                <div className="font-mono text-[11px] text-ink-tertiary">
                  {template === t.id ? "✓" : ""}
                </div>
              </div>
            ))}

          {/* Step 2: Agents */}
          {wizardStep === 2 && (
            <div>
              <div className="text-xs text-ink-secondary mb-3 text-center">
                勾选要运行的 Agent（默认全选）
              </div>
              <div className="grid grid-cols-2 gap-1 mb-3.5">
                {PIPELINE_PHASES.map((p) => (
                  <div key={p.id} className="contents">
                    <div className="col-span-2 text-[10px] text-ink-tertiary mt-1.5 font-mono">
                      Phase {p.num} · {p.name}
                    </div>
                    {p.agents.map((a) => (
                      <label
                        key={a}
                        className={`flex items-center gap-1.5 px-1.5 py-1 text-[11px] cursor-pointer text-ink-secondary font-sans ${
                          selectedAgents.includes(a) ? "bg-accent-soft" : ""
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={selectedAgents.includes(a)}
                          onChange={() => toggleAgent(a)}
                          className="accent-accent"
                        />
                        {a}
                      </label>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Step 3: Confirm */}
          {wizardStep === 3 && (
            <div className="text-center">
              <div className="text-xs text-ink-secondary mb-4">配置摘要</div>
              <div className="text-[13px] text-ink-primary bg-bg-elevated p-3 border border-border-light text-left leading-loose">
                模板：<span className="font-mono text-[11px]">{template}</span>
                <br />
                Agent：<span className="font-mono text-[11px]">{selectedAgents.length} / {ALL_AGENTS.length}</span>
                <br />
                LLM：<span className="font-mono text-[11px]">DeepSeek V4 Pro</span>
              </div>
              <div className="mt-4 text-[11px] text-ink-tertiary">
                准备好后关闭高级配置，点击命令栏「生成报告」启动。
              </div>
            </div>
          )}

          {/* Wizard navigation */}
          <div className="flex justify-center gap-2.5 mt-4">
            {wizardStep > 1 && (
              <button
                onClick={() => setWizardStep(wizardStep - 1)}
                className="px-4 py-1.5 text-[11px] cursor-pointer font-sans border border-border-light bg-bg-elevated text-ink-secondary"
              >
                ← 上一步
              </button>
            )}
            {wizardStep < 3 && (
              <button
                onClick={() => setWizardStep(wizardStep + 1)}
                className="px-5 py-1.5 text-[11px] font-medium cursor-pointer font-sans border-none bg-accent text-white"
              >
                下一步 →
              </button>
            )}
          </div>
        </div>
      )}

      {/* Pipeline preview */}
      <div className="flex items-start justify-center gap-0 mt-8">
        {PIPELINE_PHASES.map((p, i) => (
          <div key={p.id} className="flex items-start gap-0">
            {i > 0 && <div className="px-1 py-2 text-xs text-border">→</div>}
            <div className="text-center w-16">
              <div className="font-mono text-[9px] text-ink-tertiary mb-0.5">{p.num}</div>
              <div className="text-[10px] text-ink-secondary font-medium">{p.name}</div>
              <div className="text-[8px] text-ink-tertiary mt-1 leading-[1.4]">
                {p.agents.map((a) => (
                  <div key={a}>{a}</div>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
