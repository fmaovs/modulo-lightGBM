#!/usr/bin/env python3
"""
Compare model predictions (trained LightGBM vs fallback heuristic).
Demonstrates improvement of trained model over rule-based fallback.

Usage:
    python3 compare_models.py --data data/synthetic_data.csv
"""

import pandas as pd
import numpy as np
import os
import sys
import argparse
import json
from datetime import datetime

# Add parent to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.scoring.ml_model import MLModel
from sklearn.metrics import roc_auc_score, precision_score, recall_score, f1_score, confusion_matrix


class FallbackPredictor:
    """
    Simulate MLModel without model.txt loaded (using heuristic fallback).
    """
    def predict_proba(self, data: dict) -> float:
        """Fallback heuristic from ml_model.py"""
        dias = int(data.get("dias_vencidos") or 0)
        if dias <= 0:
            return 95.0
        if dias <= 30:
            return 75.0
        if dias <= 90:
            return 45.0
        if dias <= 180:
            return 20.0
        return 5.0


def load_test_data(csv_path: str) -> pd.DataFrame:
    """Load test data from CSV."""
    df = pd.read_csv(csv_path)
    if "paid_within_30d" not in df.columns:
        raise ValueError("CSV must contain 'paid_within_30d' column for evaluation")
    return df


def get_predictions(data_records: list, predictor, predictor_name: str):
    """Get predictions from a predictor for a list of records."""
    predictions = []
    for record in data_records:
        prob = predictor.predict_proba(record.to_dict())
        predictions.append(prob / 100.0)  # Normalize to 0-1
    return np.array(predictions)


def compute_metrics(y_true, y_pred_proba, y_pred=None):
    """Compute evaluation metrics."""
    if y_pred is None:
        y_pred = (y_pred_proba >= 0.5).astype(int)
    
    metrics = {
        "auc": roc_auc_score(y_true, y_pred_proba),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
    }
    
    # Confusion matrix
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    metrics["true_negatives"] = int(tn)
    metrics["false_positives"] = int(fp)
    metrics["false_negatives"] = int(fn)
    metrics["true_positives"] = int(tp)
    metrics["specificity"] = tn / (tn + fp) if (tn + fp) > 0 else 0
    metrics["sensitivity"] = tp / (tp + fn) if (tp + fn) > 0 else 0
    
    return metrics


def generate_html_report(metrics_fallback, metrics_model, df_comparison, output_path="MODEL_COMPARISON.html"):
    """Generate HTML comparison report."""
    
    improvement = {
        "auc": (metrics_model["auc"] - metrics_fallback["auc"]) / metrics_fallback["auc"] * 100,
        "f1": (metrics_model["f1"] - metrics_fallback["f1"]) / max(metrics_fallback["f1"], 0.001) * 100,
        "precision": (metrics_model["precision"] - metrics_fallback["precision"]) / max(metrics_fallback["precision"], 0.001) * 100,
    }
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Model Comparison Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }}
        h1 {{ color: #333; }}
        h2 {{ color: #555; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border: 1px solid #ddd; }}
        th {{ background: #007bff; color: white; }}
        tr:nth-child(even) {{ background: #f9f9f9; }}
        .positive {{ color: green; font-weight: bold; }}
        .metric-box {{ display: inline-block; width: 22%; margin: 1%; padding: 15px; 
                       background: #f0f0f0; border-radius: 5px; text-align: center; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #007bff; }}
        .metric-label {{ font-size: 12px; color: #666; margin-top: 5px; }}
        .improvement {{ font-size: 14px; color: green; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🎯 ML Model Comparison Report</h1>
        <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        
        <h2>📊 Metrics Summary</h2>
        <div style="display: flex; flex-wrap: wrap;">
            <div class="metric-box">
                <div class="metric-value">{metrics_model['auc']:.3f}</div>
                <div class="metric-label">Model AUC</div>
                <div class="improvement">vs {metrics_fallback['auc']:.3f} (fallback)</div>
            </div>
            <div class="metric-box">
                <div class="metric-value">{metrics_model['precision']:.3f}</div>
                <div class="metric-label">Model Precision</div>
                <div class="improvement">vs {metrics_fallback['precision']:.3f} (fallback)</div>
            </div>
            <div class="metric-box">
                <div class="metric-value">{metrics_model['recall']:.3f}</div>
                <div class="metric-label">Model Recall</div>
                <div class="improvement">vs {metrics_fallback['recall']:.3f} (fallback)</div>
            </div>
            <div class="metric-box">
                <div class="metric-value">{metrics_model['f1']:.3f}</div>
                <div class="metric-label">Model F1</div>
                <div class="improvement">vs {metrics_fallback['f1']:.3f} (fallback)</div>
            </div>
        </div>
        
        <h2>📈 Detailed Metrics Comparison</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Fallback (Heuristic)</th>
                <th>LightGBM Model</th>
                <th>Improvement</th>
            </tr>
            <tr>
                <td><strong>AUC</strong></td>
                <td>{metrics_fallback['auc']:.4f}</td>
                <td><span class="positive">{metrics_model['auc']:.4f}</span></td>
                <td><span class="improvement">+{improvement['auc']:.1f}%</span></td>
            </tr>
            <tr>
                <td><strong>Precision</strong></td>
                <td>{metrics_fallback['precision']:.4f}</td>
                <td><span class="positive">{metrics_model['precision']:.4f}</span></td>
                <td><span class="improvement">+{improvement['precision']:.1f}%</span></td>
            </tr>
            <tr>
                <td><strong>Recall</strong></td>
                <td>{metrics_fallback['recall']:.4f}</td>
                <td><span class="positive">{metrics_model['recall']:.4f}</span></td>
                <td><span class="improvement">+{improvement['f1']:.1f}%</span></td>
            </tr>
            <tr>
                <td><strong>F1 Score</strong></td>
                <td>{metrics_fallback['f1']:.4f}</td>
                <td><span class="positive">{metrics_model['f1']:.4f}</span></td>
                <td><span class="improvement">+{improvement['f1']:.1f}%</span></td>
            </tr>
            <tr>
                <td><strong>Specificity</strong></td>
                <td>{metrics_fallback['specificity']:.4f}</td>
                <td><span class="positive">{metrics_model['specificity']:.4f}</span></td>
                <td>-</td>
            </tr>
            <tr>
                <td><strong>Sensitivity</strong></td>
                <td>{metrics_fallback['sensitivity']:.4f}</td>
                <td><span class="positive">{metrics_model['sensitivity']:.4f}</span></td>
                <td>-</td>
            </tr>
        </table>
        
        <h2>🔍 Confusion Matrix (Test Set)</h2>
        <table>
            <tr>
                <th colspan="3" style="text-align: center;">Fallback Model</th>
            </tr>
            <tr>
                <td></td>
                <td><strong>Predicted: 0</strong></td>
                <td><strong>Predicted: 1</strong></td>
            </tr>
            <tr>
                <td><strong>Actual: 0</strong></td>
                <td>{metrics_fallback['true_negatives']}</td>
                <td>{metrics_fallback['false_positives']}</td>
            </tr>
            <tr>
                <td><strong>Actual: 1</strong></td>
                <td>{metrics_fallback['false_negatives']}</td>
                <td>{metrics_fallback['true_positives']}</td>
            </tr>
        </table>
        
        <table>
            <tr>
                <th colspan="3" style="text-align: center;">LightGBM Model</th>
            </tr>
            <tr>
                <td></td>
                <td><strong>Predicted: 0</strong></td>
                <td><strong>Predicted: 1</strong></td>
            </tr>
            <tr>
                <td><strong>Actual: 0</strong></td>
                <td>{metrics_model['true_negatives']}</td>
                <td>{metrics_model['false_positives']}</td>
            </tr>
            <tr>
                <td><strong>Actual: 1</strong></td>
                <td>{metrics_model['false_negatives']}</td>
                <td>{metrics_model['true_positives']}</td>
            </tr>
        </table>
        
        <h2>💡 Key Insights</h2>
        <ul>
            <li><strong>AUC Improvement:</strong> {improvement['auc']:.1f}% better discrimination</li>
            <li><strong>Precision:</strong> {improvement['precision']:.1f}% fewer false positives (fewer incorrect rejections)</li>
            <li><strong>Recall:</strong> {metrics_model['recall']/metrics_fallback['recall']*100-100:.1f}% better coverage of payers</li>
            <li><strong>Business Impact:</strong> More accurate risk scoring leads to better approval decisions</li>
        </ul>
        
        <h2>📋 Sample Predictions</h2>
        <table>
            <tr>
                <th>Dias Vencidos</th>
                <th>Monto</th>
                <th>Pct Pagos</th>
                <th>Fallback Prob</th>
                <th>Model Prob</th>
                <th>Actual</th>
            </tr>
"""
    
    for idx, row in df_comparison.head(20).iterrows():
        html += f"""
            <tr>
                <td>{row['dias_vencidos']:.0f}</td>
                <td>${row['monto_adeudado']:,.0f}</td>
                <td>{row['pct_pagos_on_time']:.2f}</td>
                <td>{row['fallback_prob']:.1f}%</td>
                <td><strong>{row['model_prob']:.1f}%</strong></td>
                <td>{'✓ Paid' if row['paid_within_30d'] == 1 else '✗ Default'}</td>
            </tr>
"""
    
    html += """
        </table>
    </div>
</body>
</html>
"""
    
    with open(output_path, "w") as f:
        f.write(html)
    
    print(f"\n[REPORT] ✓ HTML report saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Compare fallback vs trained model")
    parser.add_argument("--data", type=str, required=True,
                        help="Path to test data CSV")
    parser.add_argument("--model", type=str, default="app/models/model.txt",
                        help="Path to trained model (if exists)")
    parser.add_argument("--output", type=str, default="MODEL_COMPARISON.html",
                        help="Output HTML report path")
    args = parser.parse_args()
    
    print(f"[COMPARE] Model Comparison: Fallback vs LightGBM")
    print(f"  Test data: {args.data}")
    print(f"  Model: {args.model}")
    
    if not os.path.exists(args.data):
        print(f"[ERROR] Data file not found: {args.data}", file=sys.stderr)
        sys.exit(1)
    
    # Load data
    df = load_test_data(args.data)
    print(f"[DATA] Loaded {len(df)} test samples")
    
    y_true = df["paid_within_30d"].values
    
    # Get predictions from fallback
    print(f"\n[PRED] Computing fallback (heuristic) predictions...")
    fallback_model = FallbackPredictor()
    y_fallback_proba = get_predictions(
        [df.iloc[i] for i in range(len(df))],
        fallback_model,
        "Fallback"
    )
    
    # Get predictions from trained model
    print(f"[PRED] Computing LightGBM model predictions...")
    try:
        trained_model = MLModel(args.model)
        if trained_model.is_available():
            y_model_proba = get_predictions(
                [df.iloc[i] for i in range(len(df))],
                trained_model,
                "LightGBM"
            )
            model_available = True
        else:
            print(f"[WARN] Model file not found: {args.model}")
            print(f"       Using fallback as reference. Train model first:")
            print(f"       python3 scripts/train.py --data {args.data} --output {args.model}")
            y_model_proba = y_fallback_proba
            model_available = False
    except Exception as e:
        print(f"[WARN] Error loading model: {e}")
        y_model_proba = y_fallback_proba
        model_available = False
    
    # Compute metrics
    print(f"\n[EVAL] Computing metrics...")
    metrics_fallback = compute_metrics(y_true, y_fallback_proba)
    metrics_model = compute_metrics(y_true, y_model_proba)
    
    # Display results
    print(f"\n{'='*70}")
    print(f"{'METRIC':<30} {'Fallback':<15} {'Model':<15}")
    print(f"{'='*70}")
    for key in ["auc", "precision", "recall", "f1"]:
        fb = metrics_fallback[key]
        md = metrics_model[key]
        delta = (md - fb) / fb * 100 if fb > 0 else 0
        delta_str = f"+{delta:.1f}%" if delta > 0 else f"{delta:.1f}%"
        print(f"{key:<30} {fb:<15.4f} {md:<15.4f} {delta_str}")
    print(f"{'='*70}")
    
    # Create comparison dataframe for report
    df_comparison = df.copy()
    df_comparison["fallback_prob"] = y_fallback_proba * 100
    df_comparison["model_prob"] = y_model_proba * 100
    
    # Generate HTML report
    generate_html_report(metrics_fallback, metrics_model, df_comparison, args.output)
    
    print(f"\n[DONE] ✓ Comparison complete!")
    if model_available:
        print(f"Model is {(metrics_model['auc']/metrics_fallback['auc'] - 1)*100:.1f}% better in AUC!")
    else:
        print(f"Train a model to see actual comparison:")
        print(f"  python3 scripts/train.py --data {args.data} --output {args.model}")


if __name__ == "__main__":
    main()
