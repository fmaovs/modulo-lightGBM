def _get_variable_value(var_key: str, data: dict):
    """Get raw value in original scale matching backend range definitions."""
    if var_key == "DAYS_PAST_DUE":
        return float(data.get("dias_vencidos") or 0)
    if var_key == "AMOUNT_DUE":
        return float(data.get("monto_adeudado") or 0.0)
    if var_key == "PAYMENT_HISTORY":
        pct = data.get("pct_pagos_on_time")
        return max(0.0, min(1.0, float(pct))) if pct else 0.5
    if var_key == "SENIORITY_MONTHS":
        return float(data.get("seniority_months") or 0)
    if var_key == "DEFAULT_FREQUENCY":
        freq = data.get("default_frequency")
        return max(0.0, min(1.0, float(freq))) if freq else 0.5
    if var_key == "CONTACTABILITY":
        score = 0.0
        if data.get("mobile") or data.get("telefono"):
            score += 0.6
        if data.get("email"):
            score += 0.4
        return max(0.0, min(1.0, score))
    if var_key == "BROKEN_PROMISES":
        promises = data.get("broken_promises") or 0
        val = float(promises) if promises else 0.0
        return val if val <= 1.0 else min(1.0, val / 10.0)
    return float(data.get(var_key.lower()) or 0)


def calculate_rules_score(data: dict, config: dict = None) -> int:
    """
    Rules-based scoring matching backend configuration with ranges in original scales.
    """
    if not config:
        # Fallback to simple rules
        dias = int(data.get("dias_vencidos") or 0)
        monto = float(data.get("monto_adeudado") or 0.0)
        pct_on_time = data.get("pct_pagos_on_time")

        if dias <= 0:
            part_dias = 500
        elif dias <= 30:
            part_dias = 400
        elif dias <= 90:
            part_dias = 250
        elif dias <= 180:
            part_dias = 120
        else:
            part_dias = 10

        if monto <= 100000:
            part_monto = 250
        elif monto <= 1000000:
            part_monto = 160
        else:
            part_monto = 80

        if pct_on_time is None:
            part_hist = 200
        else:
            pct = float(pct_on_time) if pct_on_time else 0.0
            part_hist = int(max(0, min(250, pct * 2.5)))

        total = part_dias + part_monto + part_hist
        return max(0, min(1000, int(total)))

    # Config-driven scoring
    variables = config.get("variables") or []
    if not variables:
        return calculate_rules_score(data, None)

    total_weighted = 0.0
    total_weights = 0.0
    
    for var in variables:
        key = var.get("variableKey") or var.get("key") or var.get("name")
        weight = float(var.get("weight") or 0.0)
        if weight <= 0:
            continue
        
        value = _get_variable_value(key, data)
        base = None
        ranges = var.get("ranges") or []
        
        # Match value against ranges
        for r in ranges:
            minv = float(r.get("minValue", 0.0))
            maxv = float(r.get("maxValue", float('inf')))
            if value >= minv and value <= maxv:
                base = float(r.get("baseScore", 0.0))
                break
        
        # If no range matched, use default or last range
        if base is None:
            base = float(ranges[-1].get("baseScore", 0.0)) if ranges else 0.0
        
        total_weighted += base * weight
        total_weights += weight

    if total_weights <= 0:
        return calculate_rules_score(data, None)
    
    score = int(max(0, min(1000, total_weighted / total_weights)))
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

    for var in variables:
        key = var.get("variableKey") or var.get("key") or var.get("name")
        weight = float(var.get("weight") or 0.0)
        if weight <= 0:
            continue

        value = _get_variable_value(key, data)
        matched = None
        ranges = var.get("ranges") or []
        base = None

        for r in ranges:
            minv = float(r.get("minValue", 0.0))
            maxv = float(r.get("maxValue", float('inf')))
            if value >= minv and value <= maxv:
                base = float(r.get("baseScore", 0.0))
                matched = {"min": minv, "max": maxv, "baseScore": base}
                break

        if base is None:
            base = float(ranges[-1].get("baseScore", 0.0)) if ranges else 0.0
            matched = {"min": None, "max": None, "baseScore": base}

        contrib = base * weight
        total_weighted += contrib
        total_weights += weight

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

    score = int(max(0, min(1000, total_weighted / total_weights)))
    return {"score": score, "details": details}
