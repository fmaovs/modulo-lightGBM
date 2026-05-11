#!/bin/bash
# 🚀 QUICKSTART: ML Training Pipeline
# Run this script to see the full training pipeline end-to-end

set -e

BASE_DIR="/home/fvillanueva/Escritorio/modulo-lightGBM"
cd "$BASE_DIR"
source .venv/bin/activate

echo "=================================="
echo "🎓 ML Training Pipeline - Full Demo"
echo "=================================="

# Step 1: Generate synthetic data
echo -e "\n📊 Step 1: Generating synthetic training data..."
python3 scripts/generate_synthetic_data.py --output data/synthetic_data.csv --n 500
echo "   ✓ Generated 500 synthetic samples"

# Step 2: Train model
echo -e "\n🔧 Step 2: Training LightGBM model..."
python3 scripts/train.py --data data/synthetic_data.csv --output app/models/model.txt
echo "   ✓ Model trained and saved"

# Step 3: Compare models
echo -e "\n📈 Step 3: Comparing Fallback vs Trained Model..."
python3 scripts/compare_models.py --data data/synthetic_data.csv --output MODEL_COMPARISON.html
echo "   ✓ Comparison report generated"

# Step 4: Show health status
echo -e "\n🏥 Step 4: Checking service health..."
sleep 1
curl -s http://localhost:9001/health | python3 -m json.tool
echo "   ✓ Service is operational"

echo -e "\n=================================="
echo "✅ Pipeline Complete!"
echo "=================================="
echo ""
echo "📋 Next steps:"
echo "   1. View comparison: open MODEL_COMPARISON.html"
echo "   2. Read demo: DEMO_ENTRENAMIENTO_VS_FALLBACK.md"
echo "   3. Restart microservice to load trained model:"
echo "      BACKEND_URL=http://localhost:8080/api BACKEND_USER=admin BACKEND_PASS=admin123 \\"
echo "      uvicorn app.main:app --port 9001"
echo "   4. Test predictions:"
echo "      curl -X POST http://localhost:9001/predict -H 'Content-Type: application/json' \\"
echo "        -d '{\"dias_vencidos\": 30, \"monto_adeudado\": 100000}'"
echo ""
