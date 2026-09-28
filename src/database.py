import sqlite3
import json
from typing import List, Dict, Optional, Any
from pathlib import Path
from src.config import DB_PATH
from src.schemas import AcquirerProfile, EmbeddedPrecedent

def get_connection() -> sqlite3.Connection:
    """Returns a SQLite connection with WAL mode enabled for concurrency."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def init_db() -> None:
    """Initializes tables for raw transactions, hybrid acquirer profiles, and run history."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Raw transactions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS raw_transactions (
        transaction_id TEXT PRIMARY KEY,
        target_company TEXT NOT NULL,
        acquirer TEXT NOT NULL,
        sector TEXT NOT NULL,
        deal_type TEXT NOT NULL,
        geography TEXT NOT NULL,
        financing_type TEXT,
        deal_size_mm REAL NOT NULL,
        target_revenue_mm REAL,
        target_ebitda_mm REAL,
        ebitda_margin_pct REAL,
        revenue_growth_pct REAL,
        ev_ebitda_multiple REAL,
        ev_revenue_multiple REAL,
        synergy_pct_of_deal REAL,
        outcome TEXT NOT NULL,
        strategic_rationale_tags TEXT,
        acquirer_type TEXT NOT NULL
    );
    """)

    # 2. Check and migrate acquirer_profiles to hybrid schema if needed
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='acquirer_profiles';")
    table_exists = cursor.fetchone()
    if table_exists:
        cursor.execute("PRAGMA table_info(acquirer_profiles);")
        col_names = [col["name"] for col in cursor.fetchall()]
        if "total_deals_count" not in col_names:
            cursor.execute("DROP TABLE acquirer_profiles;")

    # Hybrid Acquirer Profiles Table:
    # 1-to-1 scalar metrics are proper SQL columns for fast querying & indexing;
    # 1-to-many / nested structures remain clean JSON columns.
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS acquirer_profiles (
        acquirer_name TEXT PRIMARY KEY,
        acquirer_type TEXT NOT NULL,
        total_deals_count INTEGER NOT NULL,
        total_capital_deployed_mm REAL NOT NULL,
        min_deal_size_mm REAL NOT NULL,
        median_deal_size_mm REAL NOT NULL,
        max_deal_size_mm REAL NOT NULL,
        primary_sector TEXT NOT NULL,
        median_ev_ebitda REAL,
        median_ev_revenue REAL,
        median_target_ebitda_margin_pct REAL,
        sector_deal_counts TEXT NOT NULL,     -- JSON dict: {"Healthcare Services": 2, ...}
        deal_type_counts TEXT NOT NULL,       -- JSON dict: {"Bolt-on": 3, ...}
        tag_frequencies TEXT NOT NULL,        -- JSON dict: {"Geographic Expansion": 5, ...}
        geographies_active TEXT NOT NULL,     -- JSON list: ["Southeast", "Northeast"]
        embedded_precedents TEXT NOT NULL,    -- JSON list of top closed precedents
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Relational indexes for fast query performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_acq_primary_sector ON acquirer_profiles(primary_sector);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_acq_median_size ON acquirer_profiles(median_deal_size_mm);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_acq_total_capital ON acquirer_profiles(total_capital_deployed_mm);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_acq_deals_count ON acquirer_profiles(total_deals_count);")

    # 3. Sector benchmarks
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sector_benchmarks (
        sector TEXT PRIMARY KEY,
        median_ev_ebitda REAL,
        median_ev_revenue REAL,
        deal_count INTEGER
    );
    """)

    # 4. Recommendation run history
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS recommendation_runs (
        report_id TEXT PRIMARY KEY,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        target_profile_json TEXT NOT NULL,
        top_k INTEGER NOT NULL,
        recommendations_json TEXT NOT NULL,
        pdf_path TEXT
    );
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trans_acquirer ON raw_transactions(acquirer);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trans_sector ON raw_transactions(sector);")
    
    conn.commit()
    conn.close()

def get_existing_transaction_ids() -> set:
    """Returns set of all transaction_ids currently in raw_transactions."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT transaction_id FROM raw_transactions;")
    rows = cursor.fetchall()
    conn.close()
    return {r["transaction_id"] for r in rows}

def save_acquirer_profile(profile: AcquirerProfile) -> None:
    """
    Upserts an AcquirerProfile into acquirer_profiles with structured scalar columns
    and JSON-encoded nested collections.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO acquirer_profiles (
        acquirer_name, acquirer_type, total_deals_count, total_capital_deployed_mm,
        min_deal_size_mm, median_deal_size_mm, max_deal_size_mm, primary_sector,
        median_ev_ebitda, median_ev_revenue, median_target_ebitda_margin_pct,
        sector_deal_counts, deal_type_counts, tag_frequencies, geographies_active,
        embedded_precedents, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ON CONFLICT(acquirer_name) DO UPDATE SET
        acquirer_type=excluded.acquirer_type,
        total_deals_count=excluded.total_deals_count,
        total_capital_deployed_mm=excluded.total_capital_deployed_mm,
        min_deal_size_mm=excluded.min_deal_size_mm,
        median_deal_size_mm=excluded.median_deal_size_mm,
        max_deal_size_mm=excluded.max_deal_size_mm,
        primary_sector=excluded.primary_sector,
        median_ev_ebitda=excluded.median_ev_ebitda,
        median_ev_revenue=excluded.median_ev_revenue,
        median_target_ebitda_margin_pct=excluded.median_target_ebitda_margin_pct,
        sector_deal_counts=excluded.sector_deal_counts,
        deal_type_counts=excluded.deal_type_counts,
        tag_frequencies=excluded.tag_frequencies,
        geographies_active=excluded.geographies_active,
        embedded_precedents=excluded.embedded_precedents,
        updated_at=CURRENT_TIMESTAMP;
    """, (
        profile.acquirer_name,
        profile.acquirer_type,
        profile.total_deals_count,
        profile.total_capital_deployed_mm,
        profile.min_deal_size_mm,
        profile.median_deal_size_mm,
        profile.max_deal_size_mm,
        profile.primary_sector,
        profile.median_ev_ebitda,
        profile.median_ev_revenue,
        profile.median_target_ebitda_margin_pct,
        json.dumps(profile.sector_deal_counts),
        json.dumps(profile.deal_type_counts),
        json.dumps(profile.tag_frequencies),
        json.dumps(profile.geographies_active),
        json.dumps([p.model_dump() for p in profile.embedded_precedents])
    ))
    conn.commit()
    conn.close()

def get_all_acquirer_profiles() -> List[AcquirerProfile]:
    """Retrieves all aggregated acquirer profiles from SQLite, rehydrating Pydantic models."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM acquirer_profiles;")
    rows = cursor.fetchall()
    conn.close()
    
    profiles = []
    for r in rows:
        precedents_raw = json.loads(r["embedded_precedents"])
        precedents = [EmbeddedPrecedent(**p) for p in precedents_raw]

        profile = AcquirerProfile(
            acquirer_name=r["acquirer_name"],
            acquirer_type=r["acquirer_type"],
            total_deals_count=r["total_deals_count"],
            total_capital_deployed_mm=r["total_capital_deployed_mm"],
            min_deal_size_mm=r["min_deal_size_mm"],
            median_deal_size_mm=r["median_deal_size_mm"],
            max_deal_size_mm=r["max_deal_size_mm"],
            primary_sector=r["primary_sector"],
            median_ev_ebitda=r["median_ev_ebitda"],
            median_ev_revenue=r["median_ev_revenue"],
            median_target_ebitda_margin_pct=r["median_target_ebitda_margin_pct"],
            sector_deal_counts=json.loads(r["sector_deal_counts"]),
            deal_type_counts=json.loads(r["deal_type_counts"]),
            tag_frequencies=json.loads(r["tag_frequencies"]),
            geographies_active=json.loads(r["geographies_active"]),
            embedded_precedents=precedents
        )
        profiles.append(profile)
    return profiles

def get_sector_benchmarks() -> Dict[str, Dict[str, Any]]:
    """Returns benchmark median multiples per sector."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT sector, median_ev_ebitda, median_ev_revenue, deal_count FROM sector_benchmarks;")
    rows = cursor.fetchall()
    conn.close()
    
    benchmarks = {}
    for r in rows:
        benchmarks[r["sector"].strip().lower()] = {
            "median_ev_ebitda": r["median_ev_ebitda"],
            "median_ev_revenue": r["median_ev_revenue"],
            "deal_count": r["deal_count"]
        }
    return benchmarks

def save_recommendation_run(report_id: str, target_profile_dict: dict, top_k: int, recommendations: list, pdf_path: str = "") -> None:
    """Persists a recommendation execution for audit and download retrieval."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT OR REPLACE INTO recommendation_runs (report_id, target_profile_json, top_k, recommendations_json, pdf_path)
    VALUES (?, ?, ?, ?, ?);
    """, (
        report_id,
        json.dumps(target_profile_dict),
        top_k,
        json.dumps([r.model_dump() if hasattr(r, 'model_dump') else r for r in recommendations]),
        pdf_path
    ))
    conn.commit()
    conn.close()

def get_recommendation_run(report_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a past recommendation run."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM recommendation_runs WHERE report_id = ?;", (report_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

