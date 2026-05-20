"""Data models for the weekly funnel report generator."""

from typing import Optional
from pydantic import BaseModel, Field


class SkillGroup(BaseModel):
    """A row in the pipeline slate table."""
    skill_group: str = Field(..., description="e.g. NA-AWS, FA-II, L5")
    demands: int = 0
    rr_awaiting: int = 0
    rr_incline: int = 0
    rr_reject: int = 0
    oa_scheduled: int = 0
    oa_incline: int = 0
    oa_reject: int = 0
    bps_awaiting: int = 0
    bps_scheduled: int = 0
    bps_incline: int = 0
    bps_reject: int = 0
    os_awaiting: int = 0
    os_scheduled: int = 0
    os_incline: int = 0
    os_reject: int = 0
    offer_made: int = 0
    offer_accept: int = 0
    offer_renege: int = 0
    onboard: int = 0


class MonthlyDelivery(BaseModel):
    """Month-on-month glidepath row."""
    month: str
    num_sourcers: float = 0
    os_inclines_actual: int = 0
    onsite_completed: int = 0
    offer_accepts_actual: int = 0
    offer_accept_target: int = 0


class BusinessUpdate(BaseModel):
    """Business-wise update section."""
    business_name: str
    os_inclines: int = 0
    offer_accepts: int = 0
    offer_declines: int = 0
    offer_stage: int = 0
    os_completed: int = 0
    incline_conversion_pct: Optional[float] = None
    conversion_goal_pct: float = 35.0
    pipeline_onsite: int = 0
    pipeline_bps: int = 0
    pipeline_assessment: int = 0
    pipeline_hm_review: int = 0
    notes: Optional[str] = None


class CTCInsight(BaseModel):
    """Capture-the-Conversation insight."""
    reason: str
    count: int = 0
    total: int = 0

    @property
    def percentage(self) -> float:
        return round((self.count / self.total) * 100, 1) if self.total else 0


class FunnelReport(BaseModel):
    """Complete weekly funnel report data."""
    report_year: int = 2026
    report_title: str = "Weekly Funnel Report"
    # High-level summary
    ytd_os_inclines: int = 0
    ytd_offer_accepts: int = 0
    ytd_offer_stage: int = 0
    ytd_offer_declines: int = 0
    total_requisitions: int = 0
    total_active_pipeline: int = 0
    # Conversion metrics
    bps_to_os_pct: Optional[float] = None
    os_to_incline_pct: Optional[float] = None
    offer_acceptance_pct: Optional[float] = None
    # Detailed data
    skill_groups: list[SkillGroup] = Field(default_factory=list)
    monthly_delivery: list[MonthlyDelivery] = Field(default_factory=list)
    business_updates: list[BusinessUpdate] = Field(default_factory=list)
    ctc_insights: list[CTCInsight] = Field(default_factory=list)
    # Source mix
    source_hire_pct: Optional[float] = None
    source_linkedin_pct: Optional[float] = None
    total_sourced: int = 0
    # Support items
    support_items: list[str] = Field(default_factory=list)
    # ASTA comparison
    asta_comparison: Optional[dict] = None
