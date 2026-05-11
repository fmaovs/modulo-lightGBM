#!/usr/bin/env python3
"""
Generate synthetic training data for LightGBM bootstrap.
Simulates realistic obligaciones and payment outcomes based on business rules.

Usage:
    python3 generate_synthetic_data.py [--output data/synthetic_data.csv] [--n 1000]
"""

import pandas as pd
import numpy as np
import os
import argparse
from datetime import datetime, timedelta


def generate_synthetic_data(n_samples: int = 1000, seed: int = 42) -> pd.DataFrame:
    """
    Generate synthetic obligaciones dataset with realistic patterns.
    
    Returns:
        DataFrame with features + label (paid_within_30d)
    """
    np.random.seed(seed)
    
    data = []
    
    for i in range(n_samples):
        # --- Feature Generation ---
        
        # dias_vencidos: Exponential distribution (most recent, some old)
        dias_vencidos = int(np.random.exponential(scale=20))
        dias_vencidos = min(dias_vencidos, 365)  # Cap at 1 year
        
        # monto_adeudado: Log-normal (most small, some large)
        monto_adeudado = np.random.lognormal(mean=10, sigma=1.5)  # ~$22k median
        monto_adeudado = max(1000, min(monto_adeudado, 50_000_000))  # Cap 1k - 50M
        
        # pct_pagos_on_time: Beta distribution (bimodal: good vs bad payers)
        if np.random.rand() < 0.7:  # 70% tend to pay on time
            pct_pagos_on_time = np.random.beta(5, 2)  # Skew high
        else:  # 30% tend to default
            pct_pagos_on_time = np.random.beta(2, 5)  # Skew low
        
        # seniority_months: Exponential (mix of new and old customers)
        seniority_months = int(np.random.exponential(scale=24))
        seniority_months = min(seniority_months, 360)  # Max 30 years
        
        # default_frequency: Higher if more days overdue
        base_default_freq = dias_vencidos / 180.0  # Scale to 0-2
        default_frequency = min(1.0, np.random.beta(2, 3) + base_default_freq * 0.3)
        
        # Contactability: Binary flags
        has_telefono = np.random.rand() < 0.8  # 80% have phone
        has_email = np.random.rand() < 0.6    # 60% have email
        
        # broken_promises: Correlated with default_frequency
        if default_frequency > 0.7:
            broken_promises = int(np.random.poisson(lam=3))
        elif default_frequency > 0.4:
            broken_promises = int(np.random.poisson(lam=1))
        else:
            broken_promises = int(np.random.poisson(lam=0.2))
        
        # --- Label Generation (paid_within_30d) ---
        # Simulate payment probability based on features (business rules)
        
        prob_pay = 0.85  # Base probability
        
        # Penalty for days overdue (strongest signal)
        if dias_vencidos > 180:
            prob_pay *= 0.10
        elif dias_vencidos > 90:
            prob_pay *= 0.30
        elif dias_vencidos > 30:
            prob_pay *= 0.60
        
        # Bonus for payment history
        prob_pay *= (0.5 + pct_pagos_on_time * 0.5)
        
        # Penalty for large amount (harder to collect)
        if monto_adeudado > 5_000_000:
            prob_pay *= 0.70
        elif monto_adeudado > 1_000_000:
            prob_pay *= 0.85
        
        # Bonus for seniority (loyal customers more likely to pay)
        prob_pay *= (0.7 + (seniority_months / 360.0) * 0.3)
        
        # Penalty for default history
        prob_pay *= (1.0 - default_frequency * 0.4)
        
        # Penalty for broken promises
        if broken_promises > 0:
            prob_pay *= (1.0 - min(0.5, broken_promises * 0.15))
        
        # Contactability helps (people you can reach are more likely to pay)
        contact_score = (0.6 if has_telefono else 0) + (0.4 if has_email else 0)
        prob_pay *= (0.6 + contact_score * 0.4)
        
        # Clamp to [0, 1]
        prob_pay = max(0.05, min(0.95, prob_pay))
        
        # Binary label: stochastic based on prob_pay
        paid_within_30d = int(np.random.rand() < prob_pay)
        
        data.append({
            "dias_vencidos": dias_vencidos,
            "monto_adeudado": monto_adeudado,
            "pct_pagos_on_time": pct_pagos_on_time,
            "seniority_months": seniority_months,
            "default_frequency": default_frequency,
            "has_telefono": int(has_telefono),
            "has_email": int(has_email),
            "broken_promises_count": broken_promises,
            "paid_within_30d": paid_within_30d,
        })
    
    df = pd.DataFrame(data)
    return df


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic training data")
    parser.add_argument("--output", type=str, default="data/synthetic_data.csv",
                        help="Output CSV file path")
    parser.add_argument("--n", type=int, default=1000,
                        help="Number of samples to generate")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility")
    args = parser.parse_args()
    
    print(f"[GENERATE] Creating {args.n} synthetic samples...")
    df = generate_synthetic_data(n_samples=args.n, seed=args.seed)
    
    # Create output directory if needed
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    
    # Save
    df.to_csv(args.output, index=False)
    print(f"[GENERATE] ✓ Saved to {args.output}")
    
    # Stats
    print(f"\n--- Dataset Stats ---")
    print(f"Shape: {df.shape}")
    print(f"Class balance (paid_within_30d): {df['paid_within_30d'].value_counts().to_dict()}")
    print(f"\nFeature ranges:")
    print(df.describe())
    
    # Correlation with target
    print(f"\nCorrelation with paid_within_30d:")
    corr = df.corr()["paid_within_30d"].sort_values(ascending=False)
    print(corr)


if __name__ == "__main__":
    main()
