import pandas as pd
from typing import List, Tuple, Dict, Any, Union
from io import BytesIO, StringIO
from pathlib import Path
from src.schemas import RawDealRecord
from src.database import get_existing_transaction_ids

def parse_and_validate_csv(csv_source: Union[str, Path, bytes, BytesIO]) -> Tuple[List[RawDealRecord], int, int]:
    """
    Parses a CSV file, enforces:
    1. Mandatory transaction_id (drops missing)
    2. Strict filter: outcome == 'Closed' (case-insensitive)
    3. Deduplication against already stored transaction_ids
    
    Returns:
        (valid_records: List[RawDealRecord], total_rows: int, duplicates_skipped: int)
    """
    if isinstance(csv_source, (str, Path)):
        df = pd.read_csv(csv_source)
    elif isinstance(csv_source, bytes):
        df = pd.read_csv(BytesIO(csv_source))
    else:
        df = pd.read_csv(csv_source)
        
    total_rows = len(df)
    if total_rows == 0:
        return [], 0, 0

    # Normalize column names (strip whitespace)
    df.columns = [c.strip().lower() for c in df.columns]

    # Required columns check
    req_cols = ["transaction_id", "target_company", "acquirer", "sector", "deal_type", "deal_size_mm", "outcome"]
    for col in req_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column in CSV: {col}")

    # 1. Filter out records missing transaction_id
    df = df.dropna(subset=["transaction_id"])
    df["transaction_id"] = df["transaction_id"].astype(str).str.strip()
    df = df[df["transaction_id"] != ""]

    # 2. Strict filter for outcome == 'Closed'
    df["outcome_clean"] = df["outcome"].astype(str).str.strip().str.capitalize()
    df_closed = df[df["outcome_clean"] == "Closed"].copy()

    # 3. Deduplicate against existing SQLite records
    existing_ids = get_existing_transaction_ids()
    new_mask = ~df_closed["transaction_id"].isin(existing_ids)
    duplicates_skipped = int((~new_mask).sum())
    df_to_ingest = df_closed[new_mask].copy()

    # Ingestion validation via Pydantic
    valid_records: List[RawDealRecord] = []
    for _, row in df_to_ingest.iterrows():
        try:
            record_dict = {
                "transaction_id": str(row["transaction_id"]),
                "target_company": str(row["target_company"]).strip(),
                "acquirer": str(row["acquirer"]).strip(),
                "sector": str(row["sector"]).strip(),
                "deal_type": str(row["deal_type"]).strip(),
                "geography": str(row.get("geography", "National")).strip(),
                "financing_type": str(row.get("financing_type", "")) if pd.notna(row.get("financing_type")) else None,
                "deal_size_mm": row["deal_size_mm"],
                "target_revenue_mm": row.get("target_revenue_mm"),
                "target_ebitda_mm": row.get("target_ebitda_mm"),
                "ebitda_margin_pct": row.get("ebitda_margin_pct"),
                "revenue_growth_pct": row.get("revenue_growth_pct"),
                "ev_ebitda_multiple": row.get("ev_ebitda_multiple"),
                "ev_revenue_multiple": row.get("ev_revenue_multiple"),
                "synergy_pct_of_deal": row.get("synergy_pct_of_deal"),
                "outcome": "Closed",
                "strategic_rationale_tags": row.get("strategic_rationale_tags", ""),
                "acquirer_type": str(row.get("acquirer_type", "Strategic")).strip()
            }
            validated = RawDealRecord(**record_dict)
            valid_records.append(validated)
        except Exception as e:
            # Skip invalid schema rows safely
            continue

    return valid_records, total_rows, duplicates_skipped
