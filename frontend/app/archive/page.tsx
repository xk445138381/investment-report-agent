"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Archive, Bookmark } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { apiUrl } from "@/lib/api";

type ArchiveItem = { task_id: string; ticker: string; company_name: string; verdict: string; card_summary: string; archived_at: string | null };

export default function ArchivePage() {
  const [items, setItems] = useState<ArchiveItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(apiUrl("/archive")).then(r => r.json()).then(d => setItems(d.archive || [])).catch(() => {}).finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <div><h1 className="text-2xl font-bold text-[#1C2434]">投研档案</h1><p className="text-sm text-[#64748B] mt-1">{items.length > 0 ? `${items.length} 份归档报告` : "归档的报告会显示在这里"}</p></div>

      {loading && <div className="text-center py-10 text-sm text-[#94A3B8]">加载中…</div>}

      {!loading && items.length === 0 && (
        <Card className="border-[#E2E8F0]"><CardContent className="p-10 text-center"><Archive className="w-10 h-10 text-[#94A3B8] mx-auto mb-3" /><p className="text-sm text-[#64748B]">暂无归档，在报告中点击「归档」按钮</p></CardContent></Card>
      )}

      {!loading && items.length > 0 && (
        <div className="grid grid-cols-2 gap-4">
          {items.map(item => (
            <Link key={item.task_id} href={`/report?task=${item.task_id}`} className="no-underline">
              <Card className="border-[#E2E8F0] hover:shadow-md transition-shadow cursor-pointer h-full">
                <CardContent className="p-5">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <Bookmark className="w-4 h-4 text-[#3B82F6]" />
                      <span className="font-semibold text-sm text-[#1C2434]">{item.company_name}</span>
                      <span className="text-xs text-[#94A3B8] font-mono">{item.ticker}</span>
                    </div>
                    <Badge variant={item.verdict === "Yes" ? "positive" : "secondary"} className={`text-[10px] ${item.verdict === "Yes" ? "bg-[#F0FDF4] text-[#22C55E]" : "bg-[#F8FAFC] text-[#64748B]"}`}>{item.verdict}</Badge>
                  </div>
                  {item.card_summary && <p className="text-xs text-[#64748B] leading-relaxed">{item.card_summary}</p>}
                  {item.archived_at && <div className="text-[10px] text-[#94A3B8] mt-3 font-mono">归档于 {new Date(item.archived_at).toLocaleDateString("zh-CN")}</div>}
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
