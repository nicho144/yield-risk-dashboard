#!/bin/bash

# Navigate to the correct directory
cd /Users/admin/Documents/News\ Dash\ Board

# Activate the virtual environment
source venv/bin/activate

# Run the original Streamlit app in the background on port 8502
nohup python3 -m streamlit run streamlite_financial.py --server.port 8502 > dashboard.log 2>&1 &

# Save the process ID
echo $! > dashboard.pid

echo "Original Dashboard started in background on port 8502. Check dashboard.log for output."
echo "To stop the dashboard, run: kill \$(cat dashboard.pid)" 