import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Automatically load .env file from project root if present
def _load_env_file():
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k and k not in os.environ:
                        os.environ[k] = v

_load_env_file()

DATA_DIR = BASE_DIR / "data"
DATA_RAW_DIR = DATA_DIR / "raw"
DATA_STORE_DIR = DATA_DIR / "store"
REPORTS_DIR = BASE_DIR / "reports"
STATIC_DIR = BASE_DIR / "src" / "static"

# Ensure directories exist
DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_STORE_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Database
DB_PATH = Path(os.getenv("DATABASE_PATH", str(DATA_STORE_DIR / "acquirer_profiles.db")))

# Scoring Weights
WEIGHT_SECTOR = 0.30
WEIGHT_SIZE = 0.30
WEIGHT_STRATEGY = 0.20
WEIGHT_GEO = 0.10
WEIGHT_FIN = 0.10

# Statutory & Risk Thresholds
HSR_ANTITRUST_THRESHOLD_MM = 133.9
FINANCING_CAPACITY_MULTIPLE = 1.3
DEFAULT_TOP_K = 10

# LLM Configuration
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Default Target Benchmark
DEFAULT_TARGET_PROFILE = {
    "sector": "Healthcare Services",
    "deal_size_mm": 200.0,
    "geography": "Southeast",
    "ebitda_margin_pct": 20.0,
    "target_revenue_mm": 25.0,
    "target_ownership_pre": "Private",
    "strategic_rationale_tags": ["Geographic Expansion", "Cost Synergies", "Platform Build"],
}

# Domain Adjacency Graph (Generalizable to any input sector)
# Maps a target sector to its direct match (1.00), Tier 1 care delivery / core adjacencies (0.85), Tier 2 enablement (0.65)
SECTOR_ADJACENCY_GRAPH = {
    "healthcare services": {
        "tier1": ["physician groups", "dental", "behavioral health", "home health/hospice", "outpatient care"],
        "tier2": ["health it", "revenue cycle", "healthcare analytics"],
        "tier3": ["medical devices", "pharma/biotech"]
    },
    "physician groups": {
        "tier1": ["healthcare services", "dental", "behavioral health", "home health/hospice", "outpatient care"],
        "tier2": ["health it", "revenue cycle"],
        "tier3": ["medical devices", "pharma/biotech"]
    },
    "dental": {
        "tier1": ["healthcare services", "physician groups", "outpatient care"],
        "tier2": ["health it", "revenue cycle"],
        "tier3": ["medical devices"]
    },
    "behavioral health": {
        "tier1": ["healthcare services", "physician groups", "home health/hospice"],
        "tier2": ["health it"],
        "tier3": ["pharma/biotech"]
    },
    "home health/hospice": {
        "tier1": ["healthcare services", "behavioral health", "physician groups"],
        "tier2": ["health it"],
        "tier3": ["medical devices"]
    },
    "health it": {
        "tier1": ["revenue cycle", "healthcare analytics", "healthcare services"],
        "tier2": ["physician groups", "dental"],
        "tier3": ["medical devices", "pharma/biotech"]
    },
    "medical devices": {
        "tier1": ["pharma/biotech", "diagnostics"],
        "tier2": ["health it", "healthcare services"],
        "tier3": ["dental"]
    },
    "pharma/biotech": {
        "tier1": ["medical devices", "diagnostics", "life sciences"],
        "tier2": ["healthcare services"],
        "tier3": ["health it"]
    }
}

def get_sector_proximity(target_sector: str, candidate_sector: str) -> float:
    """Calculates proximity score (0.20 to 1.00) between target and candidate sectors."""
    t_clean = (target_sector or "").strip().lower()
    c_clean = (candidate_sector or "").strip().lower()
    
    if not t_clean or not c_clean:
        return 0.50
    if t_clean == c_clean:
        return 1.00
    
    mapping = SECTOR_ADJACENCY_GRAPH.get(t_clean)
    if mapping:
        if c_clean in mapping.get("tier1", []):
            return 0.85
        if c_clean in mapping.get("tier2", []):
            return 0.65
        if c_clean in mapping.get("tier3", []):
            return 0.35
            
    # Reverse check
    c_mapping = SECTOR_ADJACENCY_GRAPH.get(c_clean)
    if c_mapping:
        if t_clean in c_mapping.get("tier1", []):
            return 0.85
        if t_clean in c_mapping.get("tier2", []):
            return 0.65
        if t_clean in c_mapping.get("tier3", []):
            return 0.35
            
    return 0.20
