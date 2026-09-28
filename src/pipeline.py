import uuid
import asyncio
from typing import Union, Dict, Any, Optional
from pathlib import Path
from src.schemas import TargetProfile, TopAcquirersResponse
from src.config import DEFAULT_TOP_K, DB_PATH, DATA_RAW_DIR
from src.database import init_db, get_all_acquirer_profiles, save_recommendation_run
from src.ingestion.validator import parse_and_validate_csv
from src.ingestion.aggregator import ingest_and_recompute_profiles
from src.engine.scorer import rank_acquirers
from src.engine.context_assembler import assemble_candidate_contexts
from src.llm.parser import parse_free_text_target
from src.llm.gemini_client import synthesize_all_rationales
from src.reporting.pdf_generator import generate_acquirer_pdf

async def run_recommendation_pipeline(
    target_input: Union[str, Dict[str, Any], TargetProfile],
    top_k: int = DEFAULT_TOP_K,
    export_pdf: bool = True,
    output_pdf_path: str = ""
) -> TopAcquirersResponse:
    """
    Unified atomic recommendation orchestrator:
    1. Parses target input (free-text or dictionary).
    2. Ranks candidate acquirers using Stage 1 multi-factor scoring.
    3. Assembles verified precedent comps and deterministic risk rules (Stage 2).
    4. Synthesizes MD-ready rationales using Gemini 3.8 Flash (Stage 3).
    5. Compiles 1-page-per-acquirer PDF and records run in SQLite.
    """
    init_db()

    # Step 1: Parse target profile
    target = await parse_free_text_target(target_input)

    # Step 2: Fetch pre-aggregated acquirer profiles
    profiles = get_all_acquirer_profiles()
    if not profiles:
        # Auto-bootstrap with sample CSV if available
        sample_path = DATA_RAW_DIR / "ma_deals_sample.csv"
        if not sample_path.exists():
            sample_path = Path("ma_deals_sample.csv")
        if sample_path.exists():
            records, _, _ = parse_and_validate_csv(sample_path)
            ingest_and_recompute_profiles(records)
            profiles = get_all_acquirer_profiles()

    if not profiles:
        raise ValueError("No closed acquirer profiles found in database. Please upload a deals CSV first.")

    # Step 3: Stage 1 Vectorized Scoring (< 50ms)
    ranked = rank_acquirers(profiles, target, top_k=top_k)

    # Step 4: Stage 2 Deterministic Context Assembly (< 20ms)
    candidate_contexts = assemble_candidate_contexts(ranked, target)

    # Step 5: Stage 3 LLM Structured Synthesis (Gemini 3.8 Flash)
    rationales = await synthesize_all_rationales(candidate_contexts, target)

    # Step 6: Generate PDF Report & Persist Run
    report_id = f"rep_{uuid.uuid4().hex[:10]}"
    pdf_download_url = None
    pdf_file_path = ""

    if export_pdf:
        pdf_file_path = generate_acquirer_pdf(
            recommendations=rationales,
            target=target,
            report_id=report_id,
            output_path=output_pdf_path
        )
        pdf_download_url = f"/api/reports/{Path(pdf_file_path).name}"

    save_recommendation_run(
        report_id=report_id,
        target_profile_dict=target.model_dump(),
        top_k=len(rationales),
        recommendations=rationales,
        pdf_path=pdf_file_path
    )

    return TopAcquirersResponse(
        report_id=report_id,
        target_profile=target,
        total_recommended=len(rationales),
        pdf_download_url=pdf_download_url,
        recommendations=rationales
    )
