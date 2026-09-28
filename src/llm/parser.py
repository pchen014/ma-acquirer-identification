import re
import os
import json
from typing import Optional, Dict, Any, Union
from src.schemas import TargetProfile
from src.config import GEMINI_API_KEY, GEMINI_MODEL, DEFAULT_TARGET_PROFILE
from src.llm.prompts import SYSTEM_PARSER_PROMPT

def rule_based_target_parse(text: str) -> TargetProfile:
    """
    Robust deterministic rule-based extractor for free-text target profile.
    Used as primary or zero-latency fallback when LLM is unavailable.
    """
    t_clean = text.lower()
    
    # 1. Deal Size / EV extraction
    deal_size = 200.0
    ev_match = re.search(r'\$?(\d+(?:\.\d+)?)\s*(?:m|mm|million|mil)\b', t_clean)
    if ev_match:
        try:
            deal_size = float(ev_match.group(1))
        except ValueError:
            pass

    # 2. EBITDA Margin extraction
    margin = 20.0
    margin_match = re.search(r'(\d+(?:\.\d+)?)\s*%\s*(?:margin|ebitda)', t_clean)
    if not margin_match:
        margin_match = re.search(r'(?:margin|ebitda)\s*(?:of|at|~)?\s*(\d+(?:\.\d+)?)\s*%', t_clean)
    if margin_match:
        try:
            margin = float(margin_match.group(1))
        except ValueError:
            pass

    # 3. Sector identification
    sector = "Healthcare Services"
    sector_keywords = [
        ("Physician Groups", ["physician", "doctor", "medical practice", "specialty care"]),
        ("Dental", ["dental", "dentist", "orthodontic"]),
        ("Behavioral Health", ["behavioral", "mental health", "addiction", "psychiatric"]),
        ("Home Health/Hospice", ["home health", "hospice", "home care", "elder care"]),
        ("Health IT", ["health it", "ehr", "revenue cycle", "healthcare it", "health tech", "software"]),
        ("Medical Devices", ["medical device", "medtech", "equipment", "surgical"]),
        ("Pharma/Biotech", ["pharma", "biotech", "drug", "therapeutics", "clinical"]),
        ("Healthcare Services", ["healthcare services", "healthcare", "care delivery", "clinical services"])
    ]
    for s_name, kws in sector_keywords:
        if any(kw in t_clean for kw in kws):
            sector = s_name
            break

    # 4. Geography identification
    geography = "Southeast"
    geos = ["Northeast", "Southeast", "Midwest", "Southwest", "West", "National"]
    for g in geos:
        if g.lower() in t_clean:
            geography = g
            break

    # 5. Ownership
    ownership = "Private"
    if "pe-backed" in t_clean or "pe backed" in t_clean or "sponsor" in t_clean:
        ownership = "PE-Backed"
    elif "public" in t_clean or "publicly traded" in t_clean:
        ownership = "Public"

    # 6. Strategic Tags
    tags = []
    if "geo" in t_clean or "expansion" in t_clean or "regional" in t_clean:
        tags.append("Geographic Expansion")
    if "synerg" in t_clean or "cost" in t_clean:
        tags.append("Cost Synergies")
    if "platform" in t_clean or "build" in t_clean:
        tags.append("Platform Build")
    if "tech" in t_clean or "software" in t_clean or "capability" in t_clean:
        tags.append("Technology Capability")
    if not tags:
        tags = ["Geographic Expansion", "Cost Synergies", "Platform Build"]

    return TargetProfile(
        sector=sector,
        deal_size_mm=deal_size,
        geography=geography,
        ebitda_margin_pct=margin,
        target_revenue_mm=round(deal_size * 0.15, 1),
        target_ownership_pre=ownership,
        strategic_rationale_tags=tags
    )


async def parse_free_text_target(input_data: Union[str, Dict[str, Any], TargetProfile]) -> TargetProfile:
    """
    Parses natural language banker prompt into validated TargetProfile.
    Uses Gemini when GEMINI_API_KEY is configured, falling back smoothly to rule-based parser.
    """
    if isinstance(input_data, TargetProfile):
        return input_data
    if isinstance(input_data, dict):
        return TargetProfile(**input_data)
        
    text = str(input_data).strip()
    if not text:
        return TargetProfile(**DEFAULT_TARGET_PROFILE)

    # If Gemini API Key is configured, attempt LLM extraction
    api_key = os.getenv("GEMINI_API_KEY", GEMINI_API_KEY)
    if api_key:
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=api_key)
            prompt = f"Parse this banker target description into structured JSON:\n\n{text}"
            
            response = await client.aio.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PARSER_PROMPT,
                    response_mime_type="application/json",
                    response_schema=TargetProfile,
                    temperature=0.0
                )
            )
            if response.text:
                data = json.loads(response.text)
                return TargetProfile(**data)
        except Exception:
            # Fall back safely on error
            pass

    return rule_based_target_parse(text)
