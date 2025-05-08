import logging
import logging.handlers
import os
from datetime import datetime

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Configure logging
def setup_logging():
    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )

    # Create handlers
    # File handler for all logs
    all_handler = logging.handlers.RotatingFileHandler(
        'logs/all.log',
        maxBytes=10485760,  # 10MB
        backupCount=5
    )
    all_handler.setFormatter(file_formatter)
    all_handler.setLevel(logging.INFO)

    # File handler for errors
    error_handler = logging.handlers.RotatingFileHandler(
        'logs/error.log',
        maxBytes=10485760,  # 10MB
        backupCount=5
    )
    error_handler.setFormatter(file_formatter)
    error_handler.setLevel(logging.ERROR)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)

    # Create logger
    logger = logging.getLogger('market_dashboard')
    logger.setLevel(logging.INFO)
    logger.addHandler(all_handler)
    logger.addHandler(error_handler)
    logger.addHandler(console_handler)

    return logger

# Create performance monitoring logger
def setup_performance_logging():
    perf_logger = logging.getLogger('performance')
    perf_logger.setLevel(logging.INFO)
    
    # Create performance log file
    perf_handler = logging.handlers.RotatingFileHandler(
        'logs/performance.log',
        maxBytes=10485760,  # 10MB
        backupCount=5
    )
    perf_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(message)s'
    ))
    perf_logger.addHandler(perf_handler)
    
    return perf_logger 