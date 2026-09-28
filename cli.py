#!/usr/bin/env python3
import sys
import argparse
import asyncio
from datetime import datetime
from pathlib import Path
from src.database import init_db
from src.ingestion.validator import parse_and_validate_csv
from src.ingestion.aggregator import ingest_and_recompute_profiles
from src.pipeline import run_recommendation_pipeline
from src.schemas import TargetProfile
from src.config import REPORTS_DIR

def run_digest(csv_path: str):
    """Executes the CSV digest and acquirer profile aggregation."""
    init_db()
    path = Path(csv_path)
    if not path.exists():
        print(f"[ERROR] CSV file not found: {csv_path}")
        sys.exit(1)

    print(f"\n=======================================================")
    print(f"  M&A ACQUIRER ENGINE - CSV DIGEST & AGGREGATION")
    print(f"=======================================================")
    print(f"[INFO] Reading file: {path.resolve()}")

    try:
        from src.config import DATA_RAW_DIR
        import shutil
        
        # If incoming file is outside data/raw, copy it to data/raw/
        raw_dest = DATA_RAW_DIR / path.name
        if path.resolve() != raw_dest.resolve():
            shutil.copy2(path, raw_dest)

        valid_records, total_rows, duplicates_skipped = parse_and_validate_csv(path)
        print(f"[INFO] Total rows parsed: {total_rows}")
        print(f"[INFO] Valid Closed records: {len(valid_records)}")
        print(f"[INFO] Duplicates skipped: {duplicates_skipped}")

        acquirers_updated = ingest_and_recompute_profiles(valid_records)
        print(f"[SUCCESS] Recomputed & updated {acquirers_updated} acquirer profiles in SQLite.")
        print(f"[INFO] Raw file archived at: data/raw/{path.name}")
        print(f"=======================================================\n")
    except Exception as e:
        print(f"[ERROR] Failed to digest CSV: {e}")
        sys.exit(1)


def run_recommend(args):
    """Executes acquirer identification and rationale generation."""
    init_db()

    target_input = None
    if args.text:
        target_input = args.text
    elif args.sector and args.size:
        target_input = TargetProfile(
            sector=args.sector,
            deal_size_mm=args.size,
            geography=args.geo or "North America",
            ebitda_margin_pct=args.margin if args.margin is not None else 15.0
        )
    else:
        print("[ERROR] Please provide a target company profile using either:")
        print("        --text \"<description>\"")
        print("        OR explicit parameters (at minimum: --sector \"...\" --size <number>)")
        sys.exit(1)

    # Unique timestamp-based PDF filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_out = str(REPORTS_DIR / f"acquirer_recommendations_{timestamp}.pdf")

    print(f"\n=======================================================")
    print(f"  M&A ACQUIRER IDENTIFICATION & RATIONALE ENGINE")
    print(f"=======================================================")
    print(f"[INFO] Initializing recommendation pipeline (Top-{args.top_k})...")

    async def _execute():
        return await run_recommendation_pipeline(
            target_input=target_input,
            top_k=args.top_k,
            export_pdf=True,
            output_pdf_path=pdf_out
        )

    try:
        response = asyncio.run(_execute())
        tp = response.target_profile
        print(f"[INFO] Evaluated Target Profile:")
        print(f"       • Sector: {tp.sector}")
        print(f"       • Deal Size (EV): ${tp.deal_size_mm:,.1f}M")
        print(f"       • Geography: {tp.geography}")
        print(f"       • EBITDA Margin: {tp.ebitda_margin_pct:.1f}%")
        print(f"       • Ownership: {tp.target_ownership_pre}\n")

        print(f"-------------------------------------------------------")
        print(f"  TOP {len(response.recommendations)} RANKED POTENTIAL ACQUIRERS")
        print(f"-------------------------------------------------------")

        for idx, rec in enumerate(response.recommendations, 1):
            score_pct = f"{rec.composite_score * 100:.1f}%" if rec.composite_score > 0 else "N/A"
            print(f"\n[{idx}] {rec.acquirer_name.upper()} ({rec.acquirer_type}) | Match Score: {score_pct}")
            print(f"    Conviction: {rec.conviction_level.upper()} - {rec.conviction_rationale}")
            print(f"    1. Overview: {rec.acquirer_overview[:140]}...")
            print(f"    2. Strategic Fit: {rec.strategic_fit_thesis[:140]}...")
            print(f"    3. Precedents: {rec.precedent_activity[:140]}...")
            print(f"    4. Valuation Context: {rec.valuation_context[:140]}...")
            print(f"    5. Risk Flags:")
            for r in rec.risk_flags:
                print(f"       - {r}")

        print(f"\n[SUCCESS] MD-Ready One-Page-Per-Acquirer PDF exported to:")
        print(f"          -> {Path(pdf_out).resolve()}")
        print(f"=======================================================\n")

    except Exception as e:
        print(f"[ERROR] Pipeline execution failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="M&A Acquirer Identification Engine CLI (FastAPI, Python 3.14, Gemini 3.8 Flash, SQLite)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Command 1: digest
    digest_parser = subparsers.add_parser("digest", help="Digest and aggregate deals CSV into acquirer profiles")
    digest_parser.add_argument("--csv", required=True, help="Path to raw deals CSV file")

    # Command 2: recommend
    rec_parser = subparsers.add_parser("recommend", help="Identify potential acquirers and synthesize MD rationales")
    rec_parser.add_argument("--text", type=str, help="Free-text target company description")
    rec_parser.add_argument("--sector", type=str, help="Target sector (e.g. 'Healthcare Services')")
    rec_parser.add_argument("--size", type=float, help="Target deal size / EV in USD millions")
    rec_parser.add_argument("--geo", type=str, help="Target primary operating region (default: 'North America')")
    rec_parser.add_argument("--margin", type=float, help="Target EBITDA margin percentage (default: 15.0)")
    rec_parser.add_argument("--top-k", type=int, default=10, help="Number of top candidates to recommend (default: 10)")

    args = parser.parse_args()

    if args.command == "digest":
        run_digest(args.csv)
    elif args.command == "recommend":
        run_recommend(args)

if __name__ == "__main__":
    main()
