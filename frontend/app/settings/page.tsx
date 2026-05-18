export default function SettingsPage() {
  return (
    <div className="max-w-[720px] mx-auto px-8 py-12">
      <div className="font-serif text-[22px] font-bold text-ink-primary mb-1.5">模型与配置</div>
      <div className="text-[13px] text-ink-secondary mb-7">当前生效的 LLM 和数据源配置。通过 <code className="font-mono text-[11px]">config.json</code> 管理。</div>

      {/* LLM */}
      <div className="p-4 bg-bg-surface border border-border-light mb-3">
        <div className="font-mono text-[10px] text-ink-tertiary tracking-[0.06em] mb-2">LLM 配置</div>
        <div className="text-[13px] text-ink-primary leading-[2]">
          <div>深度模型：<span className="font-mono text-xs">DeepSeek V4 Pro (provider_deep)</span></div>
          <div>快速模型：<span className="font-mono text-xs">DeepSeek V4 Pro (provider_quick)</span></div>
          <div>Temperature：<span className="font-mono text-xs">0.3</span></div>
        </div>
      </div>

      {/* Data sources */}
      <div className="p-4 bg-bg-surface border border-border-light mb-3">
        <div className="font-mono text-[10px] text-ink-tertiary tracking-[0.06em] mb-2">数据源</div>
        <div className="text-[13px] text-ink-primary leading-[2]">
          <div>A 股：<span className="font-mono text-xs">AkShare → Tushare (fallback)</span></div>
          <div>港股：<span className="font-mono text-xs">Yahoo Finance</span></div>
          <div>美股：<span className="font-mono text-xs">Yahoo Finance → SEC EDGAR</span></div>
        </div>
      </div>

      <div className="text-center py-10 text-xs text-ink-tertiary">
        完整配置编辑器 (Phase 2) · 当前通过 <code className="font-mono text-[11px]">backend/config.json</code> 文件管理
      </div>
    </div>
  );
}
