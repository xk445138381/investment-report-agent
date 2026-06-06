"use client";

import { useState, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { apiUrl } from "@/lib/api";

type ProviderInfo = { provider: string; model: string; api_key_set: boolean; note: string };
type AgentInfo = { llm: string | null; timeout_seconds: number; note: string };

export default function SettingsPage() {
  const [providers, setProviders] = useState<Record<string, ProviderInfo>>({});
  const [agents, setAgents] = useState<Record<string, AgentInfo>>({});
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState("");
  const [switching, setSwitching] = useState<string | null>(null);

  useEffect(() => {
    fetch(apiUrl("/config")).then(r => r.json()).then(d => { setProviders(d.llm_providers || {}); setAgents(d.agents || {}); }).catch(() => setMsg("无法连接后端")).finally(() => setLoading(false));
  }, []);

  const switchLLM = async (agentName: string, providerId: string) => {
    setSwitching(agentName); setMsg("");
    try {
      const r = await fetch(apiUrl("/config/switch-agent-llm"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ agent_name: agentName, llm_provider: providerId }) });
      const d = await r.json();
      if (d.ok) { setMsg(`已切换: ${agentName} → ${d.model}`); const r2 = await fetch(apiUrl("/config")); const d2 = await r2.json(); setAgents(d2.agents || {}); }
      else setMsg(`失败: ${d.error || d.detail || "后端拒绝配置变更"}`);
    } catch { setMsg("切换失败"); }
    setSwitching(null);
  };

  if (loading) return <div className="text-center py-12 text-[#94A3B8]">加载中…</div>;

  const llmAgents = Object.entries(agents).filter(([, a]) => a.llm).sort(([a], [b]) => a.localeCompare(b));
  const providerKeys = Object.keys(providers);

  return (
    <div className="max-w-3xl space-y-6">
      <div><h1 className="text-2xl font-bold text-[#1C2434]">模型与配置</h1><p className="text-sm text-[#64748B] mt-1">管理 LLM 供应商和 Agent 的模型分配</p></div>

      {msg && <div className="p-3 bg-[#EFF6FF] border border-[#BFDBFE] rounded-lg text-sm text-[#1D4ED8]">{msg}</div>}

      {/* Providers */}
      <Card className="border-[#E2E8F0]">
        <CardContent className="p-5">
          <h3 className="text-sm font-semibold text-[#1C2434] mb-4">可用供应商</h3>
          <div className="grid grid-cols-2 gap-3">
            {Object.entries(providers).map(([id, p]) => (
              <div key={id} className={`p-3 rounded-lg border ${p.api_key_set ? "border-[#22C55E] bg-[#F0FDF4]" : "border-[#E2E8F0] bg-[#F8FAFC]"}`}>
                <div className="flex items-center justify-between">
                  <div><div className="text-sm font-medium text-[#1C2434]">{id}</div><div className="text-xs text-[#64748B]">{p.provider} · <span className="font-mono">{p.model}</span></div></div>
                  {p.api_key_set ? <Badge className="bg-[#22C55E] text-white text-[10px]">已配置</Badge> : <Badge variant="outline" className="text-[#EF4444] border-[#EF4444] text-[10px]">缺 Key</Badge>}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Agent LLM assignment */}
      <Card className="border-[#E2E8F0]">
        <CardContent className="p-5">
          <h3 className="text-sm font-semibold text-[#1C2434] mb-4">LLM Agent 分配（{llmAgents.length} 个）</h3>
          <div className="space-y-1">
            {llmAgents.map(([name, agent]) => (
              <div key={name} className="flex items-center justify-between py-2.5 px-3 rounded-lg hover:bg-[#F8FAFC]">
                <div><div className="text-sm font-medium text-[#1C2434]">{name}</div><div className="text-xs text-[#64748B]">{agent.note || `超时 ${agent.timeout_seconds}s`}</div></div>
                <select
                  value={agent.llm || ""}
                  onChange={e => switchLLM(name, e.target.value)}
                  disabled={switching === name}
                  className="px-3 py-1.5 text-xs border border-[#E2E8F0] rounded-md bg-white text-[#1C2434] cursor-pointer focus:outline-none focus:ring-1 focus:ring-[#3B82F6]"
                >
                  {providerKeys.map(pid => <option key={pid} value={pid}>{pid}</option>)}
                </select>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
