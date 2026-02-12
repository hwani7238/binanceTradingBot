#!/bin/bash

# Activate virtual environment
source venv/bin/activate

# Add current directory to PYTHONPATH
export PYTHONPATH=$PYTHONPATH:$(pwd)

echo "🚀 Starting Training Process..."
python -m src.agent.train

if [ $? -eq 0 ]; then
    echo "✅ Training completed successfully."
    echo "🔄 Starting Trading Bot..."
    python src/main.py
else
    echo "❌ Training failed. Bot will not start."
fi
