import json
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Tuple
from collections import Counter
from src.schemas import RawDealRecord, AcquirerProfile, EmbeddedPrecedent
from src.database import get_connection, save_acquirer_profile, init_db

def ingest_and_recompute_profiles(records: List[RawDealRecord]) -> int:
    """
    Appends new closed deal records to raw_transactions,
    and performs O(K) incremental profile recomputation for affected acquirers.
    
    Returns:
        number of acquirers updated
    """
    if not records:
        return 0

    init_db()
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Insert new raw transactions
    insert_sql = """
    INSERT OR REPLACE INTO raw_transactions (
        transaction_id, target_company, acquirer, sector, deal_type, geography,
        financing_type, deal_size_mm, target_revenue_mm, target_ebitda_mm,
        ebitda_margin_pct, revenue_growth_pct, ev_ebitda_multiple, ev_revenue_multiple,
        synergy_pct_of_deal, outcome, strategic_rationale_tags, acquirer_type
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """
    
    affected_acquirers = set()
    for r in records:
        affected_acquirers.add(r.acquirer)
        cursor.execute(insert_sql, (
            r.transaction_id, r.target_company, r.acquirer, r.sector, r.deal_type, r.geography,
            r.financing_type, r.deal_size_mm, r.target_revenue_mm, r.target_ebitda_mm,
            r.ebitda_margin_pct, r.revenue_growth_pct, r.ev_ebitda_multiple, r.ev_revenue_multiple,
            r.synergy_pct_of_deal, r.outcome, json.dumps(r.strategic_rationale_tags), r.acquirer_type
        ))
    
    conn.commit()

    # 2. Recompute affected acquirer profiles O(K)
    for acquirer_name in affected_acquirers:
        cursor.execute("""
        SELECT * FROM raw_transactions WHERE acquirer = ? AND outcome = 'Closed';
        """, (acquirer_name,))
        rows = cursor.fetchall()
        if not rows:
            continue

        deal_sizes = [float(r["deal_size_mm"]) for r in rows]
        acquirer_type = rows[0]["acquirer_type"]
        
        # Sector counts & primary sector
        sector_list = [r["sector"].strip() for r in rows]
        sector_counts = dict(Counter(sector_list))
        primary_sector = Counter(sector_list).most_common(1)[0][0]

        # Multiples and margins (exclude nulls)
        ev_ebitda_vals = [float(r["ev_ebitda_multiple"]) for r in rows if r["ev_ebitda_multiple"] is not None]
        ev_rev_vals = [float(r["ev_revenue_multiple"]) for r in rows if r["ev_revenue_multiple"] is not None]
        margin_vals = [float(r["ebitda_margin_pct"]) for r in rows if r["ebitda_margin_pct"] is not None]

        # Deal types & tags
        deal_types = [r["deal_type"].strip() for r in rows]
        deal_type_counts = dict(Counter(deal_types))

        all_tags = []
        geos = set()
        for r in rows:
            if r["geography"]:
                geos.add(r["geography"].strip())
            if r["strategic_rationale_tags"]:
                try:
                    tags = json.loads(r["strategic_rationale_tags"])
                    if isinstance(tags, list):
                        all_tags.extend([t.strip() for t in tags if t])
                except Exception:
                    pass
        tag_counts = dict(Counter(all_tags))

        # Top 3-5 embedded precedents (representative closed transactions)
        # Sort by deal size descending to prioritize significant platforms/acquisitions
        sorted_rows = sorted(rows, key=lambda x: float(x["deal_size_mm"]), reverse=True)[:5]
        embedded_precedents = []
        for sr in sorted_rows:
            tags_list = []
            if sr["strategic_rationale_tags"]:
                try:
                    tags_list = json.loads(sr["strategic_rationale_tags"])
                except Exception:
                    pass
            embedded_precedents.append(EmbeddedPrecedent(
                transaction_id=sr["transaction_id"],
                target_company=sr["target_company"],
                sector=sr["sector"],
                deal_size_mm=float(sr["deal_size_mm"]),
                ev_ebitda_multiple=float(sr["ev_ebitda_multiple"]) if sr["ev_ebitda_multiple"] is not None else None,
                ev_revenue_multiple=float(sr["ev_revenue_multiple"]) if sr["ev_revenue_multiple"] is not None else None,
                deal_type=sr["deal_type"],
                geography=sr["geography"],
                strategic_rationale_tags=tags_list
            ))

        profile = AcquirerProfile(
            acquirer_name=acquirer_name,
            acquirer_type=acquirer_type if acquirer_type in ("Strategic", "Financial Sponsor") else "Strategic",
            total_deals_count=len(rows),
            total_capital_deployed_mm=float(np.sum(deal_sizes)),
            min_deal_size_mm=float(np.min(deal_sizes)),
            median_deal_size_mm=float(np.median(deal_sizes)),
            max_deal_size_mm=float(np.max(deal_sizes)),
            sector_deal_counts=sector_counts,
            primary_sector=primary_sector,
            median_ev_ebitda=float(np.median(ev_ebitda_vals)) if ev_ebitda_vals else None,
            median_ev_revenue=float(np.median(ev_rev_vals)) if ev_rev_vals else None,
            median_target_ebitda_margin_pct=float(np.median(margin_vals)) if margin_vals else None,
            deal_type_counts=deal_type_counts,
            tag_frequencies=tag_counts,
            geographies_active=list(geos),
            embedded_precedents=embedded_precedents
        )
        save_acquirer_profile(profile)

    # 3. Recompute sector benchmarks
    cursor.execute("""
    SELECT sector, ev_ebitda_multiple, ev_revenue_multiple
    FROM raw_transactions
    WHERE outcome = 'Closed';
    """)
    all_closed = cursor.fetchall()
    sector_groups: Dict[str, Dict[str, list]] = {}
    for r in all_closed:
        sec = r["sector"].strip().lower()
        if sec not in sector_groups:
            sector_groups[sec] = {"ebitda": [], "rev": []}
        if r["ev_ebitda_multiple"] is not None:
            sector_groups[sec]["ebitda"].append(float(r["ev_ebitda_multiple"]))
        if r["ev_revenue_multiple"] is not None:
            sector_groups[sec]["rev"].append(float(r["ev_revenue_multiple"]))

    for sec, data in sector_groups.items():
        med_ebitda = float(np.median(data["ebitda"])) if data["ebitda"] else 12.5
        med_rev = float(np.median(data["rev"])) if data["rev"] else 2.0
        deal_count = max(len(data["ebitda"]), len(data["rev"]))
        cursor.execute("""
        INSERT INTO sector_benchmarks (sector, median_ev_ebitda, median_ev_revenue, deal_count)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(sector) DO UPDATE SET
            median_ev_ebitda=excluded.median_ev_ebitda,
            median_ev_revenue=excluded.median_ev_revenue,
            deal_count=excluded.deal_count;
        """, (sec, med_ebitda, med_rev, deal_count))

    conn.commit()
    conn.close()

    return len(affected_acquirers)
