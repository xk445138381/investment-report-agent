from agents.assembly.report_engine import CompanyContext, _parse_sections


def test_value_report_parser_returns_all_eight_sections():
    ctx = CompanyContext("600519.SH", "贵州茅台")
    ctx.current_price = 1400
    ctx.weighted_value = 1600
    ctx.upside_pct = 14.2
    ctx.judge_verdict = "Too Hard"
    ctx.ownership = "股权结构稳定"

    report = """
## 投资判定与摘要
贵州茅台是白酒龙头，当前判定 Too Hard，估值安全边际不足。这里补充足够长的文字用于解析。

## 商业模式分析
商业模式依赖品牌、渠道和高端白酒定价权，护城河较强。这里补充足够长的文字用于解析。

## 财务健康评估
财务健康、现金流、ROE 和负债指标整体优秀。这里补充足够长的文字用于解析。

## 估值与安全边际
估值、买价、内在价值和安全边际需要谨慎。这里补充足够长的文字用于解析。

## 逆向风险清单
逆向思考这笔投资怎么死，重点是需求下滑和估值收缩。这里补充足够长的文字用于解析。

## 双视角裁决
段永平和芒格视角均认为需要关注价格，共识是好公司不等于好股票。这里补充足够长的文字用于解析。
"""

    sections = _parse_sections(report, ctx)

    assert set(sections) == {
        "executive_summary",
        "business_model",
        "corporate_character",
        "financial_health",
        "valuation",
        "inversion_checklist",
        "dual_verdict",
        "final_judgment",
    }
    assert sections["corporate_character"]["title"] == "企业文化与本分"
    assert "Too Hard" in sections["final_judgment"]["content"]
