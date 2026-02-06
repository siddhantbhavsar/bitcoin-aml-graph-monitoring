"""
LLM Investigator Copilot for Bitcoin AML alerts.

Usage:
    from src.llm.investigator import build_alert_payload, investigate_alert
    payload = build_alert_payload(row_dict)
    report = investigate_alert(payload, model="gpt-4o-mini")
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Literal, Optional, Union

from openai import OpenAI
from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except Exception:
    pass


SYSTEM_PROMPT = """You are an AML transaction monitoring investigator for Bitcoin.

You MUST only use the fields provided in the input payload.
Do NOT guess unseen facts (no addresses, no amounts, no exchange attribution, no real-world identities).

IMPORTANT LANGUAGE RULES:
- Do NOT claim a transaction is illicit. Describe risk signals and proximity to *labeled-illicit* nodes in the dataset.
- When referencing labels, say "labeled illicit" / "illicit-labeled in the dataset" (avoid implying real-world guilt).
- If something is unknown or not computable (null/None/NaN), explicitly state it is unknown/not computable.

OPERATIONAL RULES:
- Do NOT recommend actions outside an investigator workflow (e.g., do not suggest "freeze the transaction").
- Recommended next steps MUST be chosen from the provided ACTION_LIBRARY
  (you may lightly rephrase but must not invent new actions).
- Only include typologies if supported by evidence fields; otherwise use "unknown".

Return a structured investigation report that matches the required schema.
Use concise, analyst-style language.
"""

# Allowed recommendation menu. The model must choose from these (and may rephrase slightly).
ACTION_LIBRARY = [
    "Review top illicit-linked 1-hop neighbors contributing to exposure",
    "Review top illicit-linked strict 2-hop neighbors contributing to exposure",
    "Check whether exposure is concentrated in a single neighbor vs distributed",
    "Validate whether the alert is driven by missing/unknown neighbor labels",
    "Queue entity/tx for enhanced monitoring and watchlist",
    "Escalate to compliance review if critical/high severity and evidence is computable",
    "Document rationale and close (monitor only) if severity is low or evidence is insufficient",
]

# ✅ Non-recursive JSON-safe primitive value
JsonPrimitive = Union[str, int, float, bool, None]


class EvidenceItem(BaseModel):
    field: str
    value: JsonPrimitive  # ✅ schema-valid, no recursion
    note: str


class InvestigationReport(BaseModel):
    alert_id: str
    txId: str
    severity: Literal["low", "medium", "high", "critical"]
    risk_score: int

    executive_summary: str

    why_flagged: List[str] = Field(min_length=1)
    likely_typologies: List[
        Literal["aggregation", "distribution", "layering", "service_activity", "unknown"]
    ] = Field(min_length=1)

    # Require ≥3 actions for more useful ops output
    recommended_next_steps: List[str] = Field(min_length=3)

    evidence: List[EvidenceItem] = Field(min_length=3)

    confidence: Literal["low", "medium", "high"]
    confidence_rationale: str

    limitations: List[str] = Field(min_length=1)


def build_alert_payload(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Builds a safe, consistent payload for the LLM. Aligns field names with your feature pipeline:
    - nbr_count_1hop / nbr_count_2hop_strict
    - illicit_nbr_count_1hop / illicit_nbr_count_2hop_strict
    - illicit_nbr_ratio_1hop / illicit_nbr_ratio_2hop_strict
    """

    def _safe_int(x: Any, default: int = 0) -> int:
        try:
            if x is None:
                return default
            return int(x)
        except Exception:
            return default

    def _safe_float(x: Any, default: float = 0.0) -> float:
        try:
            if x is None:
                return default
            return float(x)
        except Exception:
            return default

    def _ratio(illicit: Optional[int], total: Optional[int]) -> Optional[float]:
        if illicit is None or total is None:
            return None
        if total <= 0:
            return None
        return float(illicit) / float(total)

    alert_id = row.get("alert_id", "")
    txid = row.get("txId", "")

    # Totals: prefer explicit total_neighbors_* if present; else use feature names
    total_1hop_raw = row.get("total_neighbors_1hop", row.get("nbr_count_1hop", None))
    total_2hop_raw = row.get(
        "total_neighbors_2hop_strict", row.get("nbr_count_2hop_strict", None)
    )

    # Illicit counts: align to your real feature names
    illicit_1hop_raw = row.get(
        "illicit_neighbors_1hop", row.get("illicit_nbr_count_1hop", None)
    )
    illicit_2hop_raw = row.get(
        "illicit_neighbors_2hop_strict", row.get("illicit_nbr_count_2hop_strict", None)
    )

    total_1hop = None if total_1hop_raw is None else _safe_int(total_1hop_raw, default=0)
    total_2hop = None if total_2hop_raw is None else _safe_int(total_2hop_raw, default=0)

    illicit_1hop = (
        None if illicit_1hop_raw is None else _safe_int(illicit_1hop_raw, default=0)
    )
    illicit_2hop = (
        None if illicit_2hop_raw is None else _safe_int(illicit_2hop_raw, default=0)
    )

    # Prefer deterministic ratios from counts; else fall back to any precomputed ratios
    computed_ratio_1hop = _ratio(illicit_1hop, total_1hop)
    computed_ratio_2hop = _ratio(illicit_2hop, total_2hop)

    row_ratio_1hop = (
        _safe_float(row.get("illicit_nbr_ratio_1hop", None), default=0.0)
        if row.get("illicit_nbr_ratio_1hop", None) is not None
        else None
    )
    row_ratio_2hop = (
        _safe_float(row.get("illicit_nbr_ratio_2hop_strict", None), default=0.0)
        if row.get("illicit_nbr_ratio_2hop_strict", None) is not None
        else None
    )

    illicit_ratio_1hop = (
        computed_ratio_1hop if computed_ratio_1hop is not None else row_ratio_1hop
    )
    illicit_ratio_2hop = (
        computed_ratio_2hop if computed_ratio_2hop is not None else row_ratio_2hop
    )

    # If totals are explicitly zero, ratios are not computable
    if total_1hop == 0:
        illicit_ratio_1hop = None
    if total_2hop == 0:
        illicit_ratio_2hop = None

    payload: Dict[str, Any] = {
        "alert_id": str(alert_id) if alert_id is not None else "",
        "txId": str(txid),
        "time_step": _safe_int(row.get("time_step", -1), default=-1),
        "severity": str(row.get("severity", "low")),
        "risk_score": _safe_int(row.get("risk_score", 0), default=0),
        "alert_reasons": row.get("alert_reasons", []),
        "fan_in_1hop": _safe_int(row.get("fan_in_1hop", 0), default=0),
        "fan_out_1hop": _safe_int(row.get("fan_out_1hop", 0), default=0),
        # Clear counts + totals (not "legitimate")
        "total_neighbors_1hop": total_1hop,
        "total_neighbors_2hop_strict": total_2hop,
        "illicit_neighbors_1hop": illicit_1hop,
        "illicit_neighbors_2hop_strict": illicit_2hop,
        # Ratios (None when not computable)
        "illicit_nbr_ratio_1hop": illicit_ratio_1hop,
        "illicit_nbr_ratio_2hop_strict": illicit_ratio_2hop,
        "top_illicit_neighbors_1hop": row.get("top_illicit_neighbors_1hop", []),
        "top_illicit_neighbors_2hop_strict": row.get("top_illicit_neighbors_2hop_strict", []),

    }

    for k in ["top_illicit_neighbors_1hop", "top_illicit_neighbors_2hop_strict"]:
        if not isinstance(payload.get(k), list):
            payload[k] = []


    if not isinstance(payload["alert_reasons"], list):
        payload["alert_reasons"] = [str(payload["alert_reasons"])]

    return payload


def investigate_alert(
    payload: Dict[str, Any],
    model: str = "gpt-4o-mini",
    temperature: float = 0.0,
) -> Dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY not found. Set it as an environment variable or in a .env file."
        )

    client = OpenAI(api_key=api_key)

    user_prompt = (
        "Create an AML investigation summary for the following alert payload.\n"
        "Rules:\n"
        "- Use only the provided fields.\n"
        "- Always use 'illicit-labeled' when describing nodes/neighbors (avoid 'illicit nodes').\n"
        "- If total_neighbors_2hop_strict is very small (<=2), mention that 2-hop evidence is based on a limited strict 2-hop neighborhood size.\n"
        "- In confidence_rationale, distinguish confidence in graph-label proximity vs confidence in real-world attribution (amounts/entities absent).\n"
        "- If exposure ratios are high and counts are available, prefer including both 1-hop and strict 2-hop neighbor review actions.\n"
        "- Do not infer addresses, entities, amounts, or attribution.\n"
        "- When discussing labels, use 'labeled illicit' or 'illicit-labeled in the dataset'.\n"
        "- Do NOT claim the transaction is illicit; describe risk signals and graph exposure only.\n"
        "- If total_neighbors_* or illicit_neighbors_* is null/None, do NOT say 'all neighbors'; "
        "instead state counts are unavailable.\n"
        "- likely_typologies must be evidence-backed:\n"
        "  * aggregation requires fan_in_1hop support\n"
        "  * distribution requires fan_out_1hop support\n"
        "  * layering requires elevated strict 2-hop exposure (and mention the exposure evidence)\n"
        "  Otherwise include 'unknown'.\n"
        "- Recommended next steps MUST be chosen from ACTION_LIBRARY "
        "(you may lightly rephrase but do not invent new actions).\n"
        "- In the 'evidence' array, use primitive values only (string/int/float/bool/null).\n\n"
        f"ACTION_LIBRARY:\n{ACTION_LIBRARY}\n\n"
        f"ALERT_PAYLOAD:\n{payload}"
    )

    resp = client.responses.parse(
        model=model,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        text_format=InvestigationReport,
        temperature=temperature,
    )

    return resp.output_parsed.model_dump()
