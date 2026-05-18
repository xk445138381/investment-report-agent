const TEMPLATES = [
  { id: "default", name: "深度研报（默认）", desc: "7 章节 · 10 图表 · 约 7000 字", markets: "A/港/美" },
  { id: "brief", name: "快速简报", desc: "4 章节 · 4 图表 · 约 2500 字", markets: "A/港/美" },
  { id: "cn", name: "A 股专用模板", desc: "含行业对标、申万分类、政策分析章节", markets: "A 股" },
];

export default function TemplatesPage() {
  return (
    <div className="max-w-[720px] mx-auto px-8 py-12">
      <div className="font-serif text-[22px] font-bold text-ink-primary mb-1.5">模板管理</div>
      <div className="text-[13px] text-ink-secondary mb-7">选择或自定义报告模板。自定义模板编辑器 (Phase 2)。</div>

      {TEMPLATES.map((t) => (
        <div key={t.id} className="p-4 mb-2 bg-bg-surface border border-border-light flex justify-between items-center">
          <div>
            <div className="font-serif text-sm font-semibold text-ink-primary mb-0.5">{t.name}</div>
            <div className="text-xs text-ink-secondary leading-relaxed">{t.desc}</div>
          </div>
          <div className="text-[10px] font-mono text-ink-tertiary border border-border-light px-2 py-0.5">
            {t.markets}
          </div>
        </div>
      ))}

      <div className="text-center py-10 text-xs text-ink-tertiary">
        JSON 配置驱动 · 自定义模板编辑器 (Phase 2) · <code className="font-mono text-[11px]">GET /api/v1/template</code>
      </div>
    </div>
  );
}
