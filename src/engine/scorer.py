import math
import numpy as np
from typing import List, Tuple, Dict, Any
from src.schemas import AcquirerProfile, TargetProfile
from src.config import (
    WEIGHT_SECTOR, WEIGHT_SIZE, WEIGHT_STRATEGY, WEIGHT_GEO, WEIGHT_FIN,
    get_sector_proximity
)

def calculate_acquirer_score(profile: AcquirerProfile, target: TargetProfile) -> Tuple[float, Dict[str, float]]:
    """
    Computes normalized multi-factor composite score (0.0 to 1.0) and sub-scores.
    """
    # 1. Sector Proximity & Depth (Weight: 30%)
    best_prox = 0.20
    rel_deals_count = 0
    for sec, count in profile.sector_deal_counts.items():
        prox = get_sector_proximity(target.sector, sec)
        if prox > best_prox:
            best_prox = prox
        if prox >= 0.65:
            rel_deals_count += count
    
    volume_factor = min(1.0, 0.60 + 0.15 * rel_deals_count)
    s_sector = float(np.clip(best_prox * volume_factor, 0.0, 1.0))

    # 2. Deal Size Capacity (Weight: 30%)
    T = target.deal_size_mm
    M = profile.median_deal_size_mm
    M_max = profile.max_deal_size_mm

    if M_max < 0.60 * T:
        # Severe under-capacity penalty
        s_size = max(0.0, (M_max / T)) * 0.50
    elif 0.50 * T <= M <= 2.50 * T:
        # Sweet spot
        s_size = 1.0 - 0.25 * (abs(M - T) / T)
    else:
        # Large buyer grace
        if M > 2.50 * T:
            ratio = max(1.0, M / T)
            s_size = max(0.70, 1.0 - 0.15 * math.log(ratio))
        else:
            s_size = max(0.40, M / T)
    s_size = float(np.clip(s_size, 0.0, 1.0))

    # 3. Strategy & Deal Type Match (Weight: 20%)
    total_deals = max(1, profile.total_deals_count)
    if profile.acquirer_type == "Financial Sponsor":
        # Check platform capacity
        has_platform = any(
            (p.deal_size_mm >= 0.40 * T or "platform" in p.deal_type.lower())
            for p in profile.embedded_precedents
        )
        platform_score = 0.40 if has_platform else 0.15
        
        bolt_ons = profile.deal_type_counts.get("Bolt-on Acquisition", 0) + profile.deal_type_counts.get("Bolt-on", 0)
        bolt_on_score = 0.35 * (bolt_ons / total_deals)
        
        tags = profile.tag_frequencies
        tag_synergy = 0.25 if ("Platform Build" in tags or "Cost Synergies" in tags or "High Growth" in tags) else 0.10
        s_strategy = platform_score + bolt_on_score + tag_synergy
    else:
        # Strategic Corporate Acquirer
        strat_deals = profile.deal_type_counts.get("Strategic Acquisition", 0) + profile.deal_type_counts.get("Strategic", 0)
        strat_score = 0.50 * (strat_deals / total_deals) if strat_deals else 0.35
        
        tags = profile.tag_frequencies
        geo_tag = 0.30 if "Geographic Expansion" in tags else 0.10
        syn_tag = 0.20 if ("Cost Synergies" in tags or "Vertical Integration" in tags) else 0.05
        s_strategy = strat_score + geo_tag + syn_tag
    s_strategy = float(np.clip(s_strategy, 0.0, 1.0))

    # 4. Geographic Alignment (Weight: 10%)
    target_geo = (target.geography or "").strip().lower()
    active_geos_lower = [g.strip().lower() for g in profile.geographies_active]
    
    if not target_geo or target_geo == "national":
        s_geo = 0.85
    elif target_geo in active_geos_lower:
        s_geo = 1.00
    elif "Geographic Expansion" in profile.tag_frequencies:
        s_geo = 0.85
    elif len(profile.geographies_active) >= 3:
        s_geo = 0.80
    else:
        s_geo = 0.45
    s_geo = float(np.clip(s_geo, 0.0, 1.0))

    # 5. Financial Profile & Margin Match (Weight: 10%)
    target_margin = target.ebitda_margin_pct or 20.0
    if profile.median_target_ebitda_margin_pct is not None:
        margin_dist = abs(profile.median_target_ebitda_margin_pct - target_margin) / target_margin
        s_margin = 1.0 - min(1.0, margin_dist)
    else:
        s_margin = 0.70

    if profile.median_ev_ebitda is not None:
        if profile.median_ev_ebitda >= 12.0:
            s_multiple = 1.00
        elif profile.median_ev_ebitda >= 10.0:
            s_multiple = 0.80
        else:
            s_multiple = 0.50
    else:
        s_multiple = 0.75
        
    s_fin = float(np.clip(0.60 * s_margin + 0.40 * s_multiple, 0.0, 1.0))

    # Composite Score
    composite = (
        WEIGHT_SECTOR * s_sector +
        WEIGHT_SIZE * s_size +
        WEIGHT_STRATEGY * s_strategy +
        WEIGHT_GEO * s_geo +
        WEIGHT_FIN * s_fin
    )
    composite = float(np.clip(composite, 0.0, 1.0))

    subscores = {
        "s_sector": round(s_sector, 3),
        "s_size": round(s_size, 3),
        "s_strategy": round(s_strategy, 3),
        "s_geo": round(s_geo, 3),
        "s_fin": round(s_fin, 3)
    }

    return round(composite, 4), subscores


def rank_acquirers(profiles: List[AcquirerProfile], target: TargetProfile, top_k: int = 10) -> List[Tuple[AcquirerProfile, float, Dict[str, float]]]:
    """
    Ranks all acquirers in store and slices top_k candidates.
    """
    scored = []
    for p in profiles:
        comp_score, subscores = calculate_acquirer_score(p, target)
        scored.append((p, comp_score, subscores))
    
    # Sort descending by composite score
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]
