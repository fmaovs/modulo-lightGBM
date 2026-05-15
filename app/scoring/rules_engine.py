def _get_variable_value(var_key: str, data: dict):
    """
    Get raw value in original scale matching backend logic in NativeScoringEngine.java
    """
    if var_key == "DPD" or var_key == "DAYS_PAST_DUE":
        return float(data.get("dias_vencidos") or 0)
    
    if var_key == "BALANCE" or var_key == "AMOUNT_DUE":
        return float(data.get("monto_adeudado") or 0.0)
    
    if var_key == "ANTIGUEDAD" or var_key == "SENIORITY":
        # Java uses ChronoUnit.DAYS between createdAt and now
        return float(data.get("seniority_days") or 0)
    
    if var_key == "FRECUENCIA" or var_key == "DEFAULT_FREQUENCY":
        # Java counts obligations with dpd > 0
        return float(data.get("default_frequency") or 0)
    
    if var_key == "CONTACTABILITY":
        # Java: 1.0 for mobile + 1.0 for email (max 2.0)
        score = 0.0
        if data.get("mobile") or data.get("telefono"):
            score += 1.0
        if data.get("email"):
            score += 1.0
        return score
    
    if var_key == "BROKEN_PROMISES":
        return float(data.get("broken_promises") or 0)
    
    # Fallback for any other keys
    return float(data.get(var_key.lower()) or 0)


def calculate_rules_score(data: dict, config: dict = None) -> int:
    """
    Rules-based scoring matching backend configuration with ranges in original scales.
    """
    if not config:
        # No burned data allowed. If no config, return 0.
        return 0

    # Config-driven scoring
    variables = config.get("variables") or []
    if not variables:
        return 0

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
        return 0
    
    score = int(max(0, min(1000, total_weighted / total_weights)))
    return score


def evaluate_rules_with_details(data: dict, config: dict = None) -> dict:
    """
    Returns a dict with 'score' and 'details' list describing for each variable the matched range and contribution.
    """
    if not config:
        return {"score": 0, "details": []}

    variables = config.get("variables") or []
    if not variables:
        return {"score": 0, "details": []}

    details = []
    total_weighted = 0.0
    total_weights = 0.0

    import sys
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

        # Required Log Format: [IA-FLOW]  - Var: SENIORITY | Val: 450.00 | Range: [365, 730] | Base: 800
        print(f"[IA-FLOW]  - Var: {key:18} | Val: {value:10.2f} | Range: {matched_range_str:20} | Base: {base:5.0f}", file=sys.stderr)

        details.append({
            "variable": key,
            "weight": weight,
            "value": value,
            "matched_range": matched,
            "baseScore": base,
            "contribution": contrib,
        })

    if total_weights <= 0:
        return {"score": 0, "details": details}

    score = int(max(0, min(1000, total_weighted / total_weights)))
    print(f"[IA-FLOW] Resultado final REGLAS: {score}", file=sys.stderr)
    return {"score": score, "details": details}
