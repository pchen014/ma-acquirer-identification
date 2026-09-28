from typing import List, Dict, Optional, Literal, Any, Union
from pydantic import BaseModel, Field, field_validator

class TargetProfile(BaseModel):
    sector: str = Field(default="Healthcare Services", description="Core industry sector")
    deal_size_mm: float = Field(default=200.0, description="Target enterprise value in USD millions")
    geography: Optional[str] = Field(default="Southeast", description="Target primary operating region")
    ebitda_margin_pct: Optional[float] = Field(default=20.0, description="Target EBITDA margin percentage")
    target_revenue_mm: Optional[float] = Field(default=25.0, description="Target annual revenue in USD millions")
    target_ownership_pre: Optional[str] = Field(default="Private", description="Pre-deal ownership: Private, PE-Backed, Public")
    strategic_rationale_tags: List[str] = Field(
        default_factory=lambda: ["Geographic Expansion", "Cost Synergies", "Platform Build"],
        description="Target strategic tags"
    )

    @field_validator("deal_size_mm", mode="before")
    def parse_deal_size(cls, v):
        if v is None:
            return 200.0
        try:
            return float(v)
        except (ValueError, TypeError):
            return 200.0

    @field_validator("ebitda_margin_pct", mode="before")
    def parse_margin(cls, v):
        if v is None:
            return 20.0
        try:
            return float(v)
        except (ValueError, TypeError):
            return 20.0


class RawDealRecord(BaseModel):
    transaction_id: str
    target_company: str
    acquirer: str
    sector: str
    deal_type: str
    geography: str
    financing_type: Optional[str] = None
    deal_size_mm: float
    target_revenue_mm: Optional[float] = None
    target_ebitda_mm: Optional[float] = None
    ebitda_margin_pct: Optional[float] = None
    revenue_growth_pct: Optional[float] = None
    ev_ebitda_multiple: Optional[float] = None
    ev_revenue_multiple: Optional[float] = None
    synergy_pct_of_deal: Optional[float] = None
    outcome: Literal["Closed"]
    strategic_rationale_tags: List[str] = Field(default_factory=list)
    acquirer_type: Literal["Strategic", "Financial Sponsor"]

    @field_validator("strategic_rationale_tags", mode="before")
    def parse_tags(cls, v):
        if isinstance(v, str):
            return [tag.strip() for tag in v.split("|") if tag.strip()]
        if isinstance(v, list):
            return v
        return []

    @field_validator("deal_size_mm", "target_revenue_mm", "target_ebitda_mm", 
                     "ebitda_margin_pct", "revenue_growth_pct", "ev_ebitda_multiple", 
                     "ev_revenue_multiple", "synergy_pct_of_deal", mode="before")
    def parse_floats(cls, v):
        if v is None or v == "" or str(v).lower() in ("nan", "null", "none"):
            return None
        try:
            return float(v)
        except (ValueError, TypeError):
            return None


class EmbeddedPrecedent(BaseModel):
    transaction_id: str
    target_company: str
    sector: str
    deal_size_mm: float
    ev_ebitda_multiple: Optional[float] = None
    ev_revenue_multiple: Optional[float] = None
    deal_type: str
    geography: str
    strategic_rationale_tags: List[str] = Field(default_factory=list)


class AcquirerProfile(BaseModel):
    acquirer_name: str
    acquirer_type: Literal["Strategic", "Financial Sponsor"]
    total_deals_count: int
    total_capital_deployed_mm: float
    min_deal_size_mm: float
    median_deal_size_mm: float
    max_deal_size_mm: float
    
    # Sector distributions
    sector_deal_counts: Dict[str, int]
    primary_sector: str
    
    # Valuation and margins
    median_ev_ebitda: Optional[float] = None
    median_ev_revenue: Optional[float] = None
    median_target_ebitda_margin_pct: Optional[float] = None
    
    # Strategy footprint
    deal_type_counts: Dict[str, int]
    tag_frequencies: Dict[str, int]
    geographies_active: List[str]
    
    # Top 3-5 representative closed precedents
    embedded_precedents: List[EmbeddedPrecedent]


class AssembledCandidateContext(BaseModel):
    acquirer_name: str
    acquirer_type: str
    composite_score: float
    conviction_level: Literal["High", "Medium", "Low"]
    conviction_summary: str
    
    # Valuation metrics vs sector benchmark
    acquirer_median_ev_ebitda: Optional[float]
    acquirer_median_ev_revenue: Optional[float]
    sector_benchmark_ev_ebitda: float
    sector_benchmark_ev_revenue: float
    ebitda_multiple_delta: Optional[float]
    
    # Verified precedents table
    verified_precedents: List[Dict[str, Any]]
    
    # Rule-based risk flags
    rule_risk_flags: List[str]


class AcquirerRationale(BaseModel):
    acquirer_name: str
    acquirer_type: Literal["Strategic", "Financial Sponsor"]
    composite_score: float = Field(default=0.0, description="Quantitative 5-factor match score (0.0 to 1.0)")
    conviction_level: Literal["High", "Medium", "Low"]
    conviction_rationale: str = Field(
        ..., 
        description="1-2 sentence data-grounded rationale citing verified deal counts and capacity."
    )
    acquirer_overview: str = Field(
        ..., 
        description="Summary of acquirer size, core sector focus, and closed transaction profile."
    )
    strategic_fit_thesis: str = Field(
        ..., 
        description="Specific thesis on why this target makes strategic sense for this acquirer."
    )
    precedent_activity: str = Field(
        ..., 
        description="Exact precedent transaction citations from provided verified data (target names, EV, multiples)."
    )
    valuation_context: str = Field(
        ..., 
        description="EV/EBITDA and EV/Revenue comparison against closed comps and pricing tolerance."
    )
    risk_flags: List[str] = Field(
        ..., 
        min_items=2, 
        description="At least 2 concrete risks synthesized from deterministic risk rules."
    )


class RecommendationRequest(BaseModel):
    target_input: Union[str, Dict[str, Any], TargetProfile] = Field(
        default="A $200M healthcare services company in the Southeast with 20% EBITDA margin, private, mid-market profile.",
        description="Free text prompt or structured target profile dictionary"
    )
    top_k: int = Field(default=10, ge=1, le=100, description="Number of top potential acquirers to return")


class TopAcquirersResponse(BaseModel):
    report_id: str
    target_profile: TargetProfile
    total_recommended: int
    pdf_download_url: Optional[str] = None
    recommendations: List[AcquirerRationale]
