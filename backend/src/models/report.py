"""Report models — ReportState, ReportSection, DebateState, ChartOutput."""

from datetime import date, datetime
from typing import Optional, Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class ReportSection(BaseModel):
    """A single report section/chapter."""
    title: str
    tldr: Optional[str] = None
    content: str
    word_count: int = 0
    charts: list[str] = Field(default_factory=list)  # chart IDs


class DebateState(BaseModel):
    """State of the bull/bear debate."""
    round: int = 1
    bull_arguments: list[dict] = Field(default_factory=list)
    bear_arguments: list[dict] = Field(default_factory=list)
    judge_conclusion: Optional[dict] = None
    history: list[str] = Field(default_factory=list)


class ChartOutput(BaseModel):
    """A generated chart image."""
    chart_id: str
    title: str
    caption: str
    png_base64: str
    width_px: int = 800
    height_px: int = 400
    position: Optional[str] = None  # Which section to embed in


class ReportMetadata(BaseModel):
    """Report-level metadata."""
    title: str
    subtitle: str = ""
    report_date: date = Field(default_factory=lambda: date.today())
    analyst: str = "AI Investment Report Agent"
    disclaimer: str = ("本报告由 AI 辅助生成，仅供参考，不构成投资建议。"
                       "请参阅文末完整免责声明。")
    tags: list[str] = Field(default_factory=list)
    rating: Optional[dict] = None


class ReportState(BaseModel):
    """Complete state of a report in generation — the central data structure
    passed through all Agent phases.

    Phase 1 → raw_data filled
    Phase 2 → analysis_results filled
    Phase 3 → debate_state filled
    Phase 4 → report_sections + charts + metadata filled
    """
    # Identity
    report_id: UUID = Field(default_factory=uuid4)
    ticker: str
    company_name: str
    report_type: Literal["deep_dive", "brief", "macro_weekly", "ipo"]
    template_id: str

    # Phase 1 output
    raw_data: dict = Field(default_factory=dict)

    # Phase 2 output
    analysis_results: dict = Field(default_factory=dict)

    # Phase 3 output
    debate_state: DebateState = Field(default_factory=DebateState)

    # Phase 4 output
    report_sections: dict[str, ReportSection] = Field(default_factory=dict)
    charts: list[ChartOutput] = Field(default_factory=list)
    metadata: Optional[ReportMetadata] = None

    # Status tracking
    status: Literal["queued", "running", "completed", "failed"] = "queued"
    current_phase: Optional[str] = None
    progress_pct: float = 0.0
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
