from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import pandas as pd
import math


@dataclass(frozen=True)
class RiskConfig:
    # percentile thresholds (computed on "known" or full population)
    fan_out_p99: float
    fan_out_p95: float
    fan_in_p99: float
    fan_in_p95: float
    exp1_p99: float   # illicit_nbr_ratio_1hop
    exp1_p95: float
    exp2_p99: float   # illicit_nbr_ratio_2hop_strict
    exp2_p95: float


def fit_risk_config(
    df_feat: pd.DataFrame,
    use_known_only: bool = True,
    label_col: str = "class_name",
) -> RiskConfig:
    """
    Compute percentile-based thresholds from the dataset.
    Percentiles are robust for heavy-tailed graph features.
    """
    if use_known_only:
        base = df_feat[df_feat[label_col].isin(["illicit", "licit"])].copy()
    else:
        base = df_feat.copy()

    # Helper for safe quantiles
    def q(col: str, p: float) -> float:
        return float(base[col].quantile(p))

    return RiskConfig(
        fan_out_p99=q("fan_out_1hop", 0.99),
        fan_out_p95=q("fan_out_1hop", 0.95),
        fan_in_p99=q("fan_in_1hop", 0.99),
        fan_in_p95=q("fan_in_1hop", 0.95),
        exp1_p99=q("illicit_nbr_ratio_1hop", 0.99),
        exp1_p95=q("illicit_nbr_ratio_1hop", 0.95),
        exp2_p99=q("illicit_nbr_ratio_2hop_strict", 0.99),
        exp2_p95=q("illicit_nbr_ratio_2hop_strict", 0.95),
    )


def score_transaction(row: pd.Series, cfg: RiskConfig) -> Tuple[int, List[str]]:
    """
    Explainable rule-based score.
    Returns:
      (risk_score, reasons)
    """
    score = 0
    reasons: List[str] = []

    # 1) Illicit exposure (strongest)
    exp1_raw = row.get("illicit_nbr_ratio_1hop", None)
    exp2_raw = row.get("illicit_nbr_ratio_2hop_strict", None)

    # Treat missing/NaN exposure as "not computable" rather than 0.0
    exp1 = float(exp1_raw) if exp1_raw is not None else float("nan")
    exp2 = float(exp2_raw) if exp2_raw is not None else float("nan")

    if math.isnan(exp1):
        reasons.append("1-hop illicit exposure not computable (no labeled 1-hop neighbors or zero degree)")
    if math.isnan(exp2):
        reasons.append("2-hop illicit exposure not computable (no labeled strict 2-hop neighbors or zero degree)")

    if exp1 >= cfg.exp1_p99 and exp1 > 0:
        score += 5
        reasons.append(f"Direct illicit exposure extremely high (1-hop ratio={exp1:.3f})")
    elif exp1 >= cfg.exp1_p95 and exp1 > 0:
        score += 3
        reasons.append(f"Direct illicit exposure elevated (1-hop ratio={exp1:.3f})")

    if exp2 >= cfg.exp2_p99 and exp2 > 0:
        score += 3
        reasons.append(f"Indirect illicit exposure extremely high (2-hop ratio={exp2:.3f})")
    elif exp2 >= cfg.exp2_p95 and exp2 > 0:
        score += 2
        reasons.append(f"Indirect illicit exposure elevated (2-hop ratio={exp2:.3f})")

    # 2) Graph structure (heavy-tail)
    fan_out = int(row.get("fan_out_1hop", 0))
    fan_in = int(row.get("fan_in_1hop", 0))

    if fan_out >= cfg.fan_out_p99:
        score += 2
        reasons.append(f"Extreme fan-out (out-degree={fan_out})")
    elif fan_out >= cfg.fan_out_p95:
        score += 1
        reasons.append(f"High fan-out (out-degree={fan_out})")

    if fan_in >= cfg.fan_in_p99:
        score += 2
        reasons.append(f"Extreme fan-in (in-degree={fan_in})")
    elif fan_in >= cfg.fan_in_p95:
        score += 1
        reasons.append(f"High fan-in (in-degree={fan_in})")

    return score, reasons


def add_risk_scores(
    df_feat: pd.DataFrame,
    cfg: RiskConfig,
    txid_col: str = "txId",
) -> pd.DataFrame:
    """
    Adds:
      - risk_score (int)
      - alert_reasons (list[str])
      - severity (low/medium/high/critical)
    """
    out = df_feat.copy()

    scored = out.apply(lambda r: score_transaction(r, cfg), axis=1)
    out["risk_score"] = scored.apply(lambda x: x[0])
    out["alert_reasons"] = scored.apply(lambda x: x[1])

    # Severity bands (tweakable; these are sensible defaults)
    def severity(score: int) -> str:
        if score >= 8:
            return "critical"
        if score >= 5:
            return "high"
        if score >= 3:
            return "medium"
        return "low"

    out["severity"] = out["risk_score"].apply(severity)
    return out


def get_alerts(
    df_scored: pd.DataFrame,
    min_severity: str = "medium",
    cols: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Filter alerts at or above min_severity.
    """
    order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    cutoff = order[min_severity]

    alerts = df_scored[df_scored["severity"].map(order) >= cutoff].copy()
    alerts = alerts.sort_values(["risk_score"], ascending=False)

    if cols is None:
        cols = ["txId", "time_step", "class_name", "risk_score", "severity",
                "fan_in_1hop", "fan_out_1hop",
                "nbr_count_1hop", "illicit_nbr_count_1hop",
                "nbr_count_2hop_strict", "illicit_nbr_count_2hop_strict",
                "illicit_nbr_ratio_1hop", "illicit_nbr_ratio_2hop_strict",
                "alert_reasons"]
    return alerts[cols]
