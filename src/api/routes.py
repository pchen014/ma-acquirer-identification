from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse
from pathlib import Path
from src.schemas import RecommendationRequest, TopAcquirersResponse
from src.ingestion.validator import parse_and_validate_csv
from src.ingestion.aggregator import ingest_and_recompute_profiles
from src.pipeline import run_recommendation_pipeline
from src.database import get_all_acquirer_profiles, get_connection
from src.config import REPORTS_DIR, DATA_RAW_DIR

router = APIRouter(prefix="/api")

@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ma-acquirer-engine"}

@router.get("/stats")
async def get_database_stats():
    """Returns database summary statistics for the frontend header."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM raw_transactions WHERE outcome = 'Closed';")
    total_closed_deals = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM acquirer_profiles;")
    total_acquirers = cursor.fetchone()[0]

    cursor.execute("SELECT DISTINCT sector FROM raw_transactions WHERE outcome = 'Closed';")
    sectors = [r[0] for r in cursor.fetchall()]
    conn.close()

    return {
        "total_closed_deals": total_closed_deals,
        "total_acquirers": total_acquirers,
        "sectors": sectors
    }

@router.post("/deals/upload")
async def upload_deals_csv(file: UploadFile = File(...)):
    """
    Ingests deals CSV file, archives raw upload to data/raw/, filters outcome == 'Closed',
    deduplicates on transaction_id, and recomputes affected acquirer profiles.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a CSV.")
    
    content = await file.read()
    
    # Save the raw uploaded file to data/raw/
    try:
        DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
        raw_target_path = DATA_RAW_DIR / file.filename
        with open(raw_target_path, "wb") as f:
            f.write(content)
    except Exception:
        pass

    try:
        valid_records, total_rows, duplicates_skipped = parse_and_validate_csv(content)
        acquirers_updated = ingest_and_recompute_profiles(valid_records)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process CSV: {str(e)}")

    return {
        "status": "success",
        "filename": file.filename,
        "raw_saved_path": f"data/raw/{file.filename}",
        "total_rows_received": total_rows,
        "closed_records_ingested": len(valid_records),
        "duplicates_skipped": duplicates_skipped,
        "acquirers_updated": acquirers_updated
    }

@router.post("/recommend", response_model=TopAcquirersResponse)
async def recommend_acquirers(request: RecommendationRequest):
    """
    Unified atomic recommendation endpoint:
    Parses target, evaluates multi-factor scoring, runs Gemini structured rationale synthesis,
    compiles 1-page-per-acquirer PDF, and returns interactive JSON + download URL.
    """
    try:
        response = await run_recommendation_pipeline(
            target_input=request.target_input,
            top_k=request.top_k,
            export_pdf=True
        )
        return response
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recommendation pipeline error: {str(e)}")

@router.get("/reports/{filename}")
async def download_report_pdf(filename: str):
    """Streams generated ReportLab PDF files."""
    file_path = REPORTS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Requested PDF report does not exist.")
    
    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=filename
    )
