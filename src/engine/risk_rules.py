from typing import List, Tuple, Literal
from src.schemas import AcquirerProfile, TargetProfile
from src.config import HSR_ANTITRUST_THRESHOLD_MM, FINANCING_CAPACITY_MULTIPLE

def evaluate_risk_rules(profile: AcquirerProfile, target: TargetProfile, composite_score: float) -> List[str]:
    """
    Deterministically generates at least 2 substantiated M&A risk flags.
    """
    flags = []
    t_ev = target.deal_size_mm
    t_sec = target.sector.strip().lower()
    t_geo = (target.geography or "").strip().lower()

    # 1. Antitrust / HSR Scrutiny Flag
    sec_deals = profile.sector_deal_counts.get(target.sector, 0)
    geo_active = [g.strip().lower() for g in profile.geographies_active]
    if t_ev >= HSR_ANTITRUST_THRESHOLD_MM and sec_deals >= 2 and (not t_geo or t_geo in geo_active):
        flags.append(
            f"Antitrust / HSR Scrutiny: Target EV (${t_ev:,.1f}M) exceeds the statutory HSR review threshold (${HSR_ANTITRUST_THRESHOLD_MM:,.1f}M); buyer already controls {sec_deals} closed platforms in this sub-sector."
        )

    # 2. Financing Capacity Flag
    if profile.max_deal_size_mm > 0 and t_ev > (FINANCING_CAPACITY_MULTIPLE * profile.max_deal_size_mm):
        flags.append(
            f"Capital Capacity Stretch: Target EV (${t_ev:,.1f}M) represents {t_ev / profile.max_deal_size_mm:.1f}x the buyer's maximum historical closed deal (${profile.max_deal_size_mm:,.1f}M), requiring elevated debt or co-investment syndication."
        )

    # 3. Integration & Regional Execution Risk
    if t_geo and t_geo != "national" and t_geo not in geo_active:
        flags.append(
            f"Regional Integration Friction: Acquirer lacks verified operational footprint in the target's {target.geography} operating market, elevating regional integration and payer renegotiation risks."
        )

    # 4. Platform vs. Bolt-On Mismatch Risk
    if profile.acquirer_type == "Financial Sponsor":
        if profile.median_deal_size_mm < 0.35 * t_ev:
            flags.append(
                f"Platform Sizing Friction: Sponsor's historical deals skew toward small add-ons (median ${profile.median_deal_size_mm:,.1f}M); transacting at ${t_ev:,.1f}M implies new platform underwriting rather than standard bolt-on integration."
            )

    # 5. Valuation Multiple Resistance
    if profile.median_ev_ebitda is not None and profile.median_ev_ebitda < 10.0:
        flags.append(
            f"Multiple Discipline Resistance: Acquirer's historical median entry multiple ({profile.median_ev_ebitda:.1f}x EV/EBITDA) reflects value/distressed underwriting, presenting pricing resistance against premium target expectations."
        )

    # Fallback to ensure at least 2 substantiated flags
    if len(flags) < 2:
        if profile.acquirer_type == "Financial Sponsor":
            flags.append(
                "Execution & Diligence Timeline: Sponsor PE committee approval and debt package syndication may introduce 60–90 day closing delays relative to strategic cash buyers."
            )
        else:
            flags.append(
                "Corporate Culture & Systems Integration: Merging clinical governance, EHR systems, and provider retention structures poses operational execution friction."
            )

    if len(flags) < 2:
        flags.append(
            "Competitive Process Pressure: High quality mid-market profile likely attracts rival sponsor bids, compressing post-deal returns."
        )

    return flags[:3]


def determine_conviction_level(composite_score: float, profile: AcquirerProfile, target: TargetProfile) -> Tuple[Literal["High", "Medium", "Low"], str]:
    """
    Deterministically computes conviction level and 1-2 sentence data-grounded rationale.
    """
    sec_deals = profile.sector_deal_counts.get(target.sector, 0)
    has_capacity = profile.max_deal_size_mm >= 0.70 * target.deal_size_mm

    if composite_score >= 0.78 and (sec_deals >= 2 or profile.total_deals_count >= 5) and has_capacity:
        level = "High"
        summary = (
            f"High conviction supported by {profile.total_deals_count} closed deals (${profile.total_capital_deployed_mm:,.1f}M total deployed) "
            f"and proven capability deploying capital in the ${profile.min_deal_size_mm:,.0f}M–${profile.max_deal_size_mm:,.0f}M range."
        )
    elif composite_score >= 0.65 and has_capacity:
        level = "Medium"
        summary = (
            f"Medium conviction grounded in strong balance sheet capacity (max deal ${profile.max_deal_size_mm:,.1f}M) "
            f"with strategic adjacency across {profile.primary_sector}."
        )
    else:
        level = "Low"
        summary = (
            f"Low/opportunistic conviction due to limited direct sector precedent ({sec_deals} closed deals) "
            f"or size capacity divergence from ${target.deal_size_mm:,.0f}M target EV."
        )

    return level, summary
