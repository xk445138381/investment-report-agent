"use client";

import { useState, useEffect } from "react";

type ProviderInfo = { provider: string; model: string; timeout_seconds: number; api_key_set: boolean; note: string };
type AgentInfo = { llm: string | null; timeout_seconds: number; note: string };
type ConfigData = { version: string; pipelines: string[]; llm_providers: Record<string, ProviderInfo>; agents: Record<string, AgentInfo> };

export default function SettingsPage() {
  const [config, setConfig] = useState<ConfigData | null>(null);
  const [switching, setSwitching] = useState<string | null>(null);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    fetch("http://localhost:8000/api/v1/config")
      .then(r => r.json())
      .then(setConfig)
      .catch(e => setMsg("无法连接后端: " + e));
  }, []);

  const switchLLM = async (agentName: string, providerId: string) => {
    setSwitching(agentName);
    setMsg("");
    try {
      const r = await fetch("http://localhost:8000/api/v1/config/switch-agent-llm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agent_name: agentName, llm_provider: providerId }),
      });
      const d = await r.json();
      if (d.ok) {
        setMsg(`已切换: ${agentName} → ${d.model}`);
        const r2 = await fetch("http://localhost:8000/api/v1/config");
        setConfig(await r2.json());
      } else {
        setMsg(`失败: ${d.error || JSON.stringify(d)}`);
      }
    } catch {
      setMsg("切换失败，后端是否运行？");
    }
    setSwitching(null);
  };

  if (!config) return (
    <div className="max-w-[720px] mx-auto px-8 py-16 text-center text-ink-tertiary">
      {msg || "加载配置…"}
    </div>
  );

  const llmAgents = Object.entries(config.agents).filter(([, a]) => a.llm).sort(([a], [b]) => a.localeCompare(b));
  const dataAgents = Object.entries(config.agents).filter(([, a]) => !a.llm).sort(([a], [b]) => a.localeCompare(b));

  return (
    <div className="max-w-[720px] mx-auto px-8 py-12">
      <h2 className="font-serif text-[24px] font-bold text-ink-primary mb-2">AI 模型配置</h2>
      <p className="text-sm text-ink-secondary mb-8">切换即时生效。当前测试用 DeepSeek，后续可加 MiniMax / GPT-4o 等。</p>

      {msg && (
        <div className="mb-4 p-3 bg-accent-soft border-l-2 border-accent text-[13px] text-ink-primary font-mono">{msg}</div>
      )}

      {/* Providers */}
      <div className="mb-8">
        <div className="font-mono text-[10px] text-ink-tertiary tracking-[0.06em] mb-2">可用供应商</div>
        <div className="grid grid-cols-2 gap-2">
          {Object.entries(config.llm_providers).map(([id, p]) => (
            <div key={id} className={`p-3 border ${p.api_key_set ? 'border-data-positive' : 'border-border-light'} bg-bg-surface`}>
              <div className="flex justify-between items-start">
                <div>
                  <div className="font-mono text-[12px] font-medium text-ink-primary">{id}</div>
                  <div className="text-[10px] text-ink-tertiary">{p.provider} · {p.model}</div>
                  {p.note && <div className="text-[10px] text-ink-tertiary mt-0.5">{p.note}</div>}
                </div>
                <div className={`text-[10px] font-mono ${p.api_key_set ? 'text-data-positive' : 'text-accent'}`}>
                  {p.api_key_set ? '已配置' : '缺 Key'}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Agent LLM assignment */}
      <div className="mb-8">
        <div className="font-mono text-[10px] text-ink-tertiary tracking-[0.06em] mb-2">
          LLM Agent 分配（{llmAgents.length} 个）
        </div>
        <div className="space-y-1">
          {llmAgents.map(([name, agent]) => (
            <div key={name} className="flex items-center justify-between p-2.5 bg-bg-surface border border-border-light">
              <div className="flex-1 min-w-0">
                <div className="font-mono text-[12px] text-ink-primary truncate">{name}</div>
                <div className="text-[10px] text-ink-tertiary">{agent.note || `超时 ${agent.timeout_seconds}s`}</div>
              </div>
              <select
                value={agent.llm || ""}
                onChange={e => switchLLM(name, e.target.value)}
                disabled={switching === name}
                className="ml-3 px-2 py-1.5 text-[11px] font-mono border border-border bg-bg-elevated text-ink-primary cursor-pointer"
              >
                {Object.keys(config.llm_providers).map(pid => (
                  <option key={pid} value={pid}>{pid}</option>
                ))}
              </select>
            </div>
          ))}
        </div>
      </div>

      {/* Data agents (no LLM) */}
      <div>
        <div className="font-mono text-[10px] text-ink-tertiary tracking-[0.06em] mb-2">
          数据 Agent（{dataAgents.length} 个，无需 LLM）
        </div>
        <div className="text-[12px] text-ink-secondary">
          {dataAgents.map(([name]) => (
            <span key={name} className="inline-block mr-3 font-mono text-[11px] text-ink-tertiary">{name}</span>
          ))}
        </div>
      </div>
    </div>
  );
}
