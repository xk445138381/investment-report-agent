"""Default configuration values.

Used as fallback when config.json fields are missing.
"""

from copy import deepcopy

DEFAULT_LLM_PROVIDERS = {
    "provider_deep": {
        "provider": "deepseek",
        "model": "deepseek-chat",
        "temperature": 0.3,
        "max_tokens": 16000,
        "api_key_source": "env:DEEPSEEK_API_KEY",
        "timeout_seconds": 180,
    },
    "provider_quick": {
        "provider": "deepseek",
        "model": "deepseek-chat",
        "temperature": 0.3,
        "max_tokens": 8000,
        "api_key_source": "env:DEEPSEEK_API_KEY",
        "timeout_seconds": 60,
    },
}

DEFAULT_DATA_PROVIDERS = {
    "providers": {
        "akshare": {
            "enabled": True,
            "priority": 1,
            "markets": ["CN"],
            "timeout_seconds": 30,
            "retry_count": 3,
            "cooldown_seconds": 2.0,
        },
        "yahoo_finance": {
            "enabled": True,
            "priority": 1,
            "markets": ["US", "HK"],
            "timeout_seconds": 20,
            "retry_count": 2,
            "cooldown_seconds": 1.5,
        },
        "user_upload": {
            "enabled": True,
            "priority": 0,
            "markets": ["CN", "US", "HK"],
            "timeout_seconds": 60,
            "retry_count": 1,
        },
    },
    "fallback_chain": {
        "CN": ["user_upload", "akshare"],
        "US": ["user_upload", "yahoo_finance"],
        "HK": ["user_upload", "yahoo_finance"],
    },
    "local_database": {
        "enabled": True,
        "path": "~/.investment_report_agent/local_data",
        "engines": ["sqlite"],
        "auto_sync_sources": ["akshare", "yahoo_finance"],
        "sync_schedule": "daily_at_20:00",
        "ttl_config": {
            "prices_daily": 86400,
            "prices_intraday": 300,
            "financials_quarterly": 86400,
            "financials_annual": 604800,
            "news": 1800,
            "macro": 86400,
            "industry_classification": 604800,
        },
    },
}

DEFAULT_PIPELINES = {
    "deep_dive": {
        "name": "深度研报",
        "phases": {
            "phase_1_data_aggregation": {
                "parallel": True,
                "agents": ["price_data", "financial_data", "news_data", "macro_data"],
            },
            "phase_2_analysis": {
                "parallel": True,
                "agents": ["financial_analysis", "valuation", "industry_competition", "corporate_governance"],
            },
            "phase_3_debate": {
                "parallel": False,
                "agents": ["bull_case", "bear_case", "risk_judge"],
                "debate_rounds": 2,
            },
            "phase_4_assembly": {
                "parallel": False,
                "agents": ["section_writer", "chart_generator", "title_summary"],
                "export": ["pdf", "docx"],
            },
        },
    },
    "brief": {
        "name": "快速简报",
        "phases": {
            "phase_1_data_aggregation": {
                "parallel": True,
                "agents": ["price_data", "financial_data", "news_data"],
            },
            "phase_2_analysis": {
                "parallel": True,
                "agents": ["financial_analysis", "valuation"],
            },
            "phase_3_debate": {
                "parallel": False,
                "agents": ["bull_case", "bear_case", "risk_judge"],
                "debate_rounds": 1,
            },
            "phase_4_assembly": {
                "parallel": False,
                "agents": ["section_writer", "title_summary"],
                "export": ["pdf"],
            },
        },
    },
}

DEFAULT_AGENTS = {
    "price_data": {
        "llm": "provider_quick",
        "output_schema": "PriceDataResult",
        "timeout_seconds": 60,
    },
    "financial_data": {
        "llm": "provider_quick",
        "output_schema": "FinancialDataResult",
        "timeout_seconds": 60,
    },
    "news_data": {
        "llm": "provider_quick",
        "tools": ["get_recent_news", "get_announcements"],
        "output_schema": "NewsAggregation",
        "timeout_seconds": 60,
    },
    "macro_data": {
        "llm": "provider_quick",
        "output_schema": "MacroDataResult",
        "timeout_seconds": 60,
    },
    "financial_analysis": {
        "llm": "provider_deep",
        "python_calculator": "financial_health_calculator",
        "output_schema": "FinancialHealthResult",
        "timeout_seconds": 120,
    },
    "valuation": {
        "llm": "provider_deep",
        "python_calculator": "valuation_engine",
        "output_schema": "ValuationResult",
        "timeout_seconds": 180,
    },
    "industry_competition": {
        "llm": "provider_deep",
        "output_schema": "IndustryCompetitionResult",
        "timeout_seconds": 120,
    },
    "corporate_governance": {
        "llm": "provider_deep",
        "output_schema": "GovernanceResult",
        "timeout_seconds": 120,
    },
    "bull_case": {
        "llm": "provider_deep",
        "tools": ["query_additional_data"],
        "output_schema": "DebateArguments",
        "timeout_seconds": 120,
    },
    "bear_case": {
        "llm": "provider_deep",
        "tools": ["query_additional_data"],
        "output_schema": "DebateArguments",
        "timeout_seconds": 120,
    },
    "risk_judge": {
        "llm": "provider_deep",
        "output_schema": "RiskJudgeResult",
        "timeout_seconds": 120,
    },
    "section_writer": {
        "llm": "provider_deep",
        "output_schema": "ReportSections",
        "timeout_seconds": 300,
    },
    "chart_generator": {
        "llm": "provider_quick",
        "output_schema": "ChartOutputs",
        "timeout_seconds": 60,
    },
    "title_summary": {
        "llm": "provider_quick",
        "output_schema": "ReportMetadata",
        "timeout_seconds": 30,
    },
}
