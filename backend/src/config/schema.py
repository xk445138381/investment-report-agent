"""Config JSON Schema — Pydantic models for config.json validation.

All configuration is driven by this schema. No hardcoded values in code.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class LLMProvider(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    OLLAMA = "ollama"
    GROQ = "groq"
    GOOGLE = "google"


class LLMProviderConfig(BaseModel):
    """Single LLM provider configuration."""
    provider: LLMProvider
    model: str
    temperature: float = 0.3
    max_tokens: int = 16000
    api_key_source: str = ""  # "env:VAR_NAME" or ""
    timeout_seconds: int = 120
    base_url: Optional[str] = None


class DataProviderConfig(BaseModel):
    """Single data provider configuration."""
    enabled: bool = True
    priority: int = 10
    markets: list[str]  # ["CN", "US", "HK"]
    timeout_seconds: int = 30
    retry_count: int = 3
    api_key_source: Optional[str] = None
    cooldown_seconds: Optional[float] = None


class DataProvidersSection(BaseModel):
    """Data providers configuration section."""
    providers: dict[str, DataProviderConfig] = Field(default_factory=dict)
    fallback_chain: dict[str, list[str]] = Field(default_factory=dict)
    local_database: Optional[dict] = None


class PipelinePhaseConfig(BaseModel):
    """A single phase within a report pipeline."""
    parallel: bool = False
    agents: list[str]
    debate_rounds: Optional[int] = None
    export: Optional[list[str]] = None


class PipelineConfig(BaseModel):
    """A complete report generation pipeline."""
    name: str
    phases: dict[str, PipelinePhaseConfig]


class AgentConfig(BaseModel):
    """Agent-specific configuration."""
    llm: Optional[str] = None  # llm_providers key (None for data-only agents)
    python_calculator: Optional[str] = None
    tools: list[str] = Field(default_factory=list)
    output_schema: str
    timeout_seconds: int = 120


class GlobalConfig(BaseModel):
    """Global / cross-cutting configuration."""
    language: str = "zh-CN"
    default_market: str = "auto"
    data_priority: str = "local_first"
    cache_root: str = "~/.investment_report_agent/cache"
    max_report_token_budget: int = 200000


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = "INFO"
    output: list[str] = Field(default_factory=lambda: ["console", "file"])
    file_path: str = "~/.investment_report_agent/logs/agent.log"


class Config(BaseModel):
    """Root configuration model — matches config.json structure."""
    version: str
    global_: GlobalConfig = Field(alias="global")
    llm_providers: dict[str, LLMProviderConfig] = Field(default_factory=dict)
    data_providers: DataProvidersSection = Field(default_factory=DataProvidersSection)
    pipelines: dict[str, PipelineConfig] = Field(default_factory=dict)
    agents: dict[str, AgentConfig] = Field(default_factory=dict)
    templates_dir: str = "~/.investment_report_agent/templates"
    reports_output_dir: str = "~/.investment_report_agent/reports"
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
