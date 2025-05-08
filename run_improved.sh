#!/bin/bash

# Navigate to the correct directory
cd /Users/admin/Documents/News\ Dash\ Board

# Activate the virtual environment
source venv/bin/activate

# Run the improved Streamlit app in the background on port 8503
nohup python3 -m streamlit run streamlite_financial_improved.py --server.port 8503 > dashboard_improved.log 2>&1 &

# Save the process ID
echo $! > dashboard_improved.pid

echo "Improved Dashboard started in background on port 8503. Check dashboard_improved.log for output."
echo "To stop the improved dashboard, run: kill \$(cat dashboard_improved.pid)" 