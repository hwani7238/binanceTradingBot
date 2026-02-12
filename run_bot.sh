#!/bin/bash
cd "$(dirname "$0")"

# Activate Virtual Environment
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "Virtual environment 'venv' not found. Please setup first."
    exit 1
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# 1. Run Streamlit with nohup so it survives terminal closure
nohup streamlit run src/app.py > logs/streamlit.log 2>&1 &
STREAMLIT_PID=$!
echo $STREAMLIT_PID > .streamlit.pid
echo "✅ Streamlit started with PID: $STREAMLIT_PID"
echo "   Logs: logs/streamlit.log"
disown $STREAMLIT_PID

# 2. Wait a moment for it to start
sleep 2

# 3. Force Open Google Chrome
echo "Opening in Google Chrome..."
open -a "Google Chrome" http://localhost:8501

echo ""
echo "🟢 Bot is running independently. You can close this terminal safely."
echo "   To stop: ./stop_bot.sh"
