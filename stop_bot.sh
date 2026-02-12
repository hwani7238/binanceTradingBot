#!/bin/bash
cd "$(dirname "$0")"

PID_FILE=".streamlit.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "Stopping Streamlit (PID: $PID)..."
        kill "$PID"
        rm "$PID_FILE"
        echo "✅ Stopped."
    else
        echo "Process $PID is not running. Cleaning up PID file."
        rm "$PID_FILE"
    fi
else
    echo "No PID file found. Trying to find Streamlit process..."
    PIDS=$(pgrep -f "streamlit run src/app.py")
    if [ -n "$PIDS" ]; then
        echo "Found Streamlit process(es): $PIDS"
        kill $PIDS
        echo "✅ Stopped."
    else
        echo "No Streamlit process found."
    fi
fi
