#!/usr/bin/env python3
"""
Train LightGBM model for payment prediction (binary classification).
Prepares data, trains model, evaluates, and saves to model.txt for production use.

Usage:
    python3 train.py --data data/synthetic_data.csv --output app/models/model.txt
"""

import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, precision_score, recall_score, f1_score
from sklearn.preprocessing import StandardScaler
import os
import argparse
import sys
from datetime import datetime


def load_and_prepare_data(csv_path: str, test_size: float = 0.2, val_size: float = 0.1):
    """
    Load CSV and prepare train/val/test splits.
    
    Returns:
        (X_train, y_train), (X_val, y_val), (X_test, y_test), feature_names
    """
    df = pd.read_csv(csv_path)
    
    # Features (in order - must match ml_model.py predict_proba)
    feature_cols = [
        "dias_vencidos",
        "monto_adeudado",
        "pct_pagos_on_time",
        "seniority_months",
        "default_frequency",
        "has_telefono",
        "has_email",
        "broken_promises_count",
    ]
    
    # Ensure all features exist
    missing = [f for f in feature_cols if f not in df.columns]
    if missing:
        raise ValueError(f"Missing features in data: {missing}")
    
    X = df[feature_cols].fillna(0)
    y = df["paid_within_30d"]
    
    # Train/val/test split
    X_temp, X_test, y_temp, y_test = train_test_split(
        X, y, test_size=test_size, random_state=42, stratify=y
    )
    
    val_size_adjusted = val_size / (1 - test_size)
    X_train, X_val, y_train, y_val = train_test_split(
        X_temp, y_temp, test_size=val_size_adjusted, random_state=42, stratify=y_temp
    )
    
    print(f"[TRAIN] Data split:")
    print(f"  Train: {X_train.shape[0]} samples")
    print(f"  Val:   {X_val.shape[0]} samples")
    print(f"  Test:  {X_test.shape[0]} samples")
    print(f"  Class balance (train): {y_train.value_counts().to_dict()}")
    
    return (X_train, y_train), (X_val, y_val), (X_test, y_test), feature_cols


def train_lightgbm(X_train, y_train, X_val, y_val, feature_names: list):
    """
    Train LightGBM model with early stopping.
    
    Returns:
        Trained Booster object
    """
    # Create LightGBM datasets
    dtrain = lgb.Dataset(
        X_train, label=y_train,
    )
    dval = lgb.Dataset(
        X_val, label=y_val,
        reference=dtrain,
    )
    
    # Hyperparameters (optimized for interpretability + performance)
    params = {
        "objective": "binary",
        "metric": "auc",
        "num_leaves": 31,
        "learning_rate": 0.05,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 5,
        "verbosity": 0,
        "seed": 42,
        # For imbalanced data (if needed, adjust scale_pos_weight)
        # "scale_pos_weight": (y_train == 0).sum() / (y_train == 1).sum(),
    }
    
    print(f"\n[TRAIN] Starting LightGBM training...")
    print(f"  Params: {params}")
    
    callbacks = [
        lgb.log_evaluation(period=10),
        lgb.early_stopping(stopping_rounds=10),
    ]
    
    bst = lgb.train(
        params,
        dtrain,
        valid_sets=[dval],
        num_boost_round=200,
        callbacks=callbacks,
    )
    
    print(f"[TRAIN] ✓ Training complete. Rounds: {bst.num_trees()}")
    
    return bst


def evaluate_model(bst, X_test, y_test, X_train=None, y_train=None):
    """
    Evaluate model on test set and return metrics.
    """
    y_pred_proba = bst.predict(X_test)
    y_pred = (y_pred_proba >= 0.5).astype(int)
    
    metrics = {
        "auc": roc_auc_score(y_test, y_pred_proba),
        "precision": precision_score(y_test, y_pred, zero_division=0),
        "recall": recall_score(y_test, y_pred, zero_division=0),
        "f1": f1_score(y_test, y_pred, zero_division=0),
    }
    
    # Also compute on train to check overfitting
    if X_train is not None and y_train is not None:
        y_train_proba = bst.predict(X_train)
        train_auc = roc_auc_score(y_train, y_train_proba)
        metrics["train_auc"] = train_auc
        metrics["test_auc"] = metrics["auc"]
        metrics["overfitting"] = train_auc - metrics["auc"]
    
    print(f"\n[EVAL] Test Set Metrics:")
    for key, val in metrics.items():
        if isinstance(val, float):
            print(f"  {key:20s}: {val:.4f}")
    
    return metrics


def save_model(bst, output_path: str):
    """Save model to file for production use."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    bst.save_model(output_path)
    print(f"\n[SAVE] ✓ Model saved to {output_path}")
    print(f"       File size: {os.path.getsize(output_path) / 1024:.1f} KB")


def main():
    parser = argparse.ArgumentParser(description="Train LightGBM scoring model")
    parser.add_argument("--data", type=str, required=True,
                        help="Path to training CSV (e.g. data/synthetic_data.csv)")
    parser.add_argument("--output", type=str, default="app/models/model.txt",
                        help="Path to save trained model")
    parser.add_argument("--test-size", type=float, default=0.2,
                        help="Fraction of data for testing")
    args = parser.parse_args()
    
    print(f"[TRAIN] LightGBM Training Pipeline")
    print(f"  Timestamp: {datetime.now().isoformat()}")
    print(f"  Data: {args.data}")
    print(f"  Output: {args.output}")
    
    if not os.path.exists(args.data):
        print(f"[ERROR] Data file not found: {args.data}", file=sys.stderr)
        sys.exit(1)
    
    # Load and prepare
    (X_train, y_train), (X_val, y_val), (X_test, y_test), features = load_and_prepare_data(
        args.data, test_size=args.test_size
    )
    
    # Train
    bst = train_lightgbm(X_train, y_train, X_val, y_val, features)
    
    # Evaluate
    metrics = evaluate_model(bst, X_test, y_test, X_train, y_train)
    
    # Feature importance
    print(f"\n[INFO] Top 5 Features (importance):")
    importance_df = pd.DataFrame({
        "feature": features,
        "importance": bst.feature_importance(),
    }).sort_values("importance", ascending=False)
    for idx, row in importance_df.head(5).iterrows():
        print(f"  {row['feature']:30s}: {row['importance']:.2f}")
    
    # Save
    save_model(bst, args.output)
    
    print(f"\n[DONE] ✓ Training pipeline complete!")
    print(f"\nNext steps:")
    print(f"  1. Restart microservice: uvicorn app.main:app --port 9000")
    print(f"  2. Test: curl -X POST http://localhost:9000/predict ...")
    print(f"  3. Compare: python3 scripts/compare_models.py --data {args.data}")


if __name__ == "__main__":
    main()
