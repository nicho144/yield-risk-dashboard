#!/bin/bash

# Check if the dashboard is running
check_dashboard() {
    if pgrep -f "streamlit run streamlite_financial_improved.py" > /dev/null; then
        echo "Dashboard is running"
        return 0
    else
        echo "Dashboard is not running"
        return 1
    fi
}

# Check system resources
check_resources() {
    echo "CPU Usage:"
    top -l 1 | grep "CPU usage"
    
    echo "Memory Usage:"
    top -l 1 | grep "PhysMem"
    
    echo "Disk Usage:"
    df -h | grep "/dev/disk1s1"
}

# Check log files
check_logs() {
    echo "Recent Errors:"
    tail -n 5 logs/error.log 2>/dev/null || echo "No error log found"
    
    echo "Recent Performance Issues:"
    tail -n 5 logs/performance.log 2>/dev/null || echo "No performance log found"
}

# Main monitoring function
monitor() {
    echo "=== Dashboard Health Check ==="
    echo "Time: $(date)"
    echo
    
    check_dashboard
    echo
    
    echo "=== System Resources ==="
    check_resources
    echo
    
    echo "=== Log Analysis ==="
    check_logs
    echo
    
    echo "=== Backup Status ==="
    ls -l backups/*.tar.gz 2>/dev/null || echo "No backups found"
}

# Run monitoring
monitor 