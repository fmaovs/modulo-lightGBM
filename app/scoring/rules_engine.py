import sys

def _get_variable_value(var_key: str, data: dict):
    """Get raw value in original scale matching backend range definitions.

    This function unifies multiple legacy keys used across backend and frontend.
    """

    # Primary keys used in backend parametric engine
    if var_key == "DAYS_PAST_DUE":
        return float(data.get("dias_vencidos") or 0.0)

    if var_key == "AMOUNT_DUE":
        return float(data.get("monto_adeudado") or 0.0)

    if var_key == "CONTACTABILITY":
        # Contactability heuristic: mobile and email presence
        score = 0.0
        if data.get("mobile") and str(data.get("mobile")).strip():
            score += 1.0
        if data.get("email") and str(data.get("email")).strip():
            score += 1.0
        return score

    if var_key == "DEFAULT_FREQUENCY":
        return float(data.get("default_frequency") or 0.0)

    if var_key == "SENIORITY":
        return float(data.get("seniority_days") or 0.0)

    if var_key == "PAYMENT_HISTORY":
        return float(data.get("payment_history") or 0.0)

    # Legacy or supplementary keys
    if var_key == "BROKEN_PROMISES":
        return float(data.get("broken_promises") or 0.0)

    if var_key == "SENIORITY_MONTHS":
        return float(data.get("seniority_months") or 0.0)

    # Fallback to lowercase match
    return float(data.get(var_key.lower()) or 0.0)


def calculate_rules_score(data: dict, config: dict = None) -> int:
    """
    Rules-based scoring matching backend configuration with ranges in original scales.
    """
    if not config:
        # Fallback to simple risk rules. Higher output means higher risk;
        # callers invert it to a quality score.
        dias = int(data.get("dias_vencidos") or 0)
        monto = float(data.get("monto_adeudado") or 0.0)
        pct_on_time = data.get("pct_pagos_on_time")

        if dias <= 0:
            part_dias = 20
        elif dias <= 30:
            part_dias = 120
        elif dias <= 90:
            part_dias = 300
        elif dias <= 180:
            part_dias = 550
        else:
            part_dias = 800

        if monto <= 100000:
            part_monto = 20
        elif monto <= 1000000:
            part_monto = 80
        else:
            part_monto = 160

        if pct_on_time is None:
            part_hist = 100
        else:
            pct = float(pct_on_time) if pct_on_time else 0.0
            part_hist = int(max(0, min(200, (1.0 - pct) * 200)))

        total = part_dias + part_monto + part_hist
        return max(0, min(1000, int(total)))

    # Config-driven scoring
    variables = config.get("variables") or []
    if not variables:
        return calculate_rules_score(data, None)

    total_weighted = 0.0
    total_weights = 0.0
    
    print(f"[IA-FLOW] Iniciando cálculo de REGLAS con {len(variables)} variables", file=sys.stderr)
    for var in variables:
        key = var.get("variableKey") or var.get("key") or var.get("name")
        weight = float(var.get("weight") or 0.0)
        if weight <= 0:
            continue
        
        value = _get_variable_value(key, data)
        base = None
        matched_range_str = "None"
        ranges = var.get("ranges") or []
        
        # Match value against ranges
        for r in ranges:
            minv = float(r.get("minValue", 0.0))
            maxv = float(r.get("maxValue", float('inf')))
            if value >= minv and value <= maxv:
                base = float(r.get("baseScore", 0.0))
                matched_range_str = f"[{minv}, {maxv if maxv != float('inf') else 'inf'}]"
                break
        
        # If no range matched, use default or last range
        if base is None:
            base = float(ranges[-1].get("baseScore", 0.0)) if ranges else 0.0
            matched_range_str = "Default/Fallback"
        
        contrib = base * weight
        total_weighted += contrib
        total_weights += weight
        print(f"[IA-FLOW]  - Var: {key:18} | Val: {value:10.2f} | Range: {matched_range_str:20} | Base: {base:5} | W: {weight:.2f} | C: {contrib:.2f}", file=sys.stderr)

    if total_weights <= 0:
        return calculate_rules_score(data, None)
    
    score = int(max(0, min(1000, total_weighted / total_weights)))
    print(f"[IA-FLOW] Score de REGLAS final: {score} (total_weighted={total_weighted:.2f}, total_weights={total_weights:.2f})", file=sys.stderr)
    return score


def evaluate_rules_with_details(data: dict, config: dict = None) -> dict:
    """
    Returns a dict with 'score' and 'details' list describing for each variable the matched range and contribution.
    """
    if not config:
        # reuse existing simple score but provide minimal details
        score = calculate_rules_score(data, None)
        return {"score": score, "details": []}

    variables = config.get("variables") or []
    if not variables:
        score = calculate_rules_score(data, None)
        return {"score": score, "details": []}

    details = []
    total_weighted = 0.0
    total_weights = 0.0

    print(f"[IA-FLOW] Iniciando evaluación detallada con {len(variables)} variables", file=sys.stderr)
    for var in variables:
        key = var.get("variableKey") or var.get("key") or var.get("name")
        weight = float(var.get("weight") or 0.0)
        if weight <= 0:
            continue

        value = _get_variable_value(key, data)
        matched = None
        ranges = var.get("ranges") or []
        base = None
        matched_range_str = "None"

        for r in ranges:
            minv = float(r.get("minValue", 0.0))
            maxv = float(r.get("maxValue", float('inf')))
            if value >= minv and value <= maxv:
                base = float(r.get("baseScore", 0.0))
                matched = {"min": minv, "max": maxv, "baseScore": base}
                matched_range_str = f"[{minv}, {maxv if maxv != float('inf') else 'inf'}]"
                break

        if base is None:
            base = float(ranges[-1].get("baseScore", 0.0)) if ranges else 0.0
            matched = {"min": None, "max": None, "baseScore": base}
            matched_range_str = "Default/Fallback"

        contrib = base * weight
        total_weighted += contrib
        total_weights += weight

        print(f"[IA-FLOW]  - Var: {key:18} | Val: {value:10.2f} | Range: {matched_range_str:20} | Base: {base:5} | W: {weight:.2f} | C: {contrib:.2f}", file=sys.stderr)

        details.append({
            "variable": key,
            "weight": weight,
            "value": value,
            "matched_range": matched,
            "baseScore": base,
            "contribution": contrib,
        })

    if total_weights <= 0:
        score = calculate_rules_score(data, None)
        return {"score": score, "details": details}

    # IMPORTANT: The backend parametric engine returns a QUALITY score (higher is better).
    # If the ranges are defined as RISK (higher is worse), we would need to invert it.
    # However, for logical parity, we will just return the weighted average.
    score = int(max(0, min(1000, total_weighted / total_weights)))
    print(f"[IA-FLOW] Resultado final REGLAS: {score}", file=sys.stderr)
    return {"score": score, "details": details}
