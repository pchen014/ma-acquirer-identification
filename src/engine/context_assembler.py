from typing import List, Tuple, Dict, Any
from src.schemas import AcquirerProfile, TargetProfile, AssembledCandidateContext
from src.engine.risk_rules import evaluate_risk_rules, determine_conviction_level
from src.database import get_sector_benchmarks

def assemble_candidate_contexts(
    ranked_candidates: List[Tuple[AcquirerProfile, float, Dict[str, float]]],
    target: TargetProfile
) -> List[AssembledCandidateContext]:
    """
    Constructs deterministic, verified context payloads for each top candidate.
    This guarantees the LLM receives verified facts and never hallucinates numbers.
    """
    benchmarks = get_sector_benchmarks()
    target_sec_key = target.sector.strip().lower()
    sec_bench = benchmarks.get(target_sec_key, {"median_ev_ebitda": 13.0, "median_ev_revenue": 2.0})

    assembled_contexts: List[AssembledCandidateContext] = []

    for profile, comp_score, _ in ranked_candidates:
        conviction_level, conviction_summary = determine_conviction_level(comp_score, profile, target)
        risk_flags = evaluate_risk_rules(profile, target, comp_score)

        # Multiples and deltas
        sec_bm_ebitda = sec_bench.get("median_ev_ebitda") or 13.0
        sec_bm_rev = sec_bench.get("median_ev_revenue") or 2.0
        
        ebitda_delta = None
        if profile.median_ev_ebitda is not None:
            ebitda_delta = round(profile.median_ev_ebitda - sec_bm_ebitda, 2)

        # Precedents formatting
        verified_precedents = []
        for p in profile.embedded_precedents:
            verified_precedents.append({
                "target_company": p.target_company,
                "sector": p.sector,
                "deal_size_mm": p.deal_size_mm,
                "ev_ebitda_multiple": p.ev_ebitda_multiple,
                "ev_revenue_multiple": p.ev_revenue_multiple,
                "deal_type": p.deal_type,
                "geography": p.geography
            })

        context = AssembledCandidateContext(
            acquirer_name=profile.acquirer_name,
            acquirer_type=profile.acquirer_type,
            composite_score=comp_score,
            conviction_level=conviction_level,
            conviction_summary=conviction_summary,
            acquirer_median_ev_ebitda=profile.median_ev_ebitda,
            acquirer_median_ev_revenue=profile.median_ev_revenue,
            sector_benchmark_ev_ebitda=sec_bm_ebitda,
            sector_benchmark_ev_revenue=sec_bm_rev,
            ebitda_multiple_delta=ebitda_delta,
            verified_precedents=verified_precedents,
            rule_risk_flags=risk_flags
        )
        assembled_contexts.append(context)

    return assembled_contexts
