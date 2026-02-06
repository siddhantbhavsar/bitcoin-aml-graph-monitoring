def compute_risk_score(row):
    score = 0
    reasons = []

    if row["fan_out_1hop"] >= 20:
        score += 2
        reasons.append("High transaction fan-out")

    if row["fan_in_1hop"] >= 20:
        score += 2
        reasons.append("High transaction fan-in")

    if row["illicit_nbr_ratio_1hop"] > 0.2:
        score += 3
        reasons.append("Direct exposure to illicit transactions")

    if row.get("illicit_nbr_ratio_2hop_strict", 0) > 0.2:
        score += 1
        reasons.append("Indirect exposure to illicit activity")

    return score, reasons
