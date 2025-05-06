from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from cachetools import TTLCache
from tenacity import retry, stop_after_attempt, wait_exponential
import prometheus_client
from prometheus_client import Counter, Histogram
import redis
import json
import logging
from logging.handlers import RotatingFileHandler
import asyncio
import threading
import time

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize rate limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Configure logging
logging.basicConfig(level=logging.INFO)
handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=3)
handler.setFormatter(logging.Formatter(
    '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
))
app.logger.addHandler(handler)

# Initialize Redis for caching
redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST', 'localhost'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    db=0,
    decode_responses=True
)

# Initialize Prometheus metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'HTTP request latency', ['endpoint'])
WEBSOCKET_CONNECTIONS = Counter('websocket_connections_total', 'Total WebSocket connections')
WEBSOCKET_MESSAGES = Counter('websocket_messages_total', 'Total WebSocket messages sent')

# Initialize in-memory cache
cache = TTLCache(maxsize=100, ttl=300)  # 5 minutes TTL

# Global variables for real-time updates
connected_clients = set()
update_thread = None
stop_update_thread = False

# Retry decorator for API calls
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def fetch_with_retry(ticker, period='1d'):
    return ticker.history(period=period)

def get_cached_data(key):
    # Try Redis first
    cached = redis_client.get(key)
    if cached:
        return json.loads(cached)
    
    # Try in-memory cache
    if key in cache:
        return cache[key]
    
    return None

def set_cached_data(key, data, ttl=300):
    # Cache in Redis
    redis_client.setex(key, ttl, json.dumps(data))
    # Cache in memory
    cache[key] = data

def get_treasury_data():
    cache_key = 'treasury_data'
    cached_data = get_cached_data(cache_key)
    if cached_data:
        return cached_data

    symbols = {
        '^TNX': '10Y',  # 10-year Treasury
        '^TYX': '30Y',  # 30-year Treasury
        '^IRX': '13W',  # 13-week Treasury
        '^FVX': '5Y',   # 5-year Treasury
        '^TXX': '2Y'    # 2-year Treasury
    }
    
    data = {}
    for symbol, name in symbols.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = fetch_with_retry(ticker)
            if not hist.empty:
                data[name] = hist['Close'].iloc[-1]
        except Exception as e:
            app.logger.error(f"Error fetching {name}: {str(e)}")
            data[name] = None
    
    set_cached_data(cache_key, data)
    return data

def get_market_data():
    cache_key = 'market_data'
    cached_data = get_cached_data(cache_key)
    if cached_data:
        return cached_data

    symbols = {
        '^VIX': 'VIX',
        'SPY': 'SPY',
        'GC=F': 'GOLD',
        'DX-Y.NYB': 'DXY',
        '^TNX': 'TNX',  # 10-year Treasury yield
        '^TYX': 'TYX',  # 30-year Treasury yield
        '^FVX': 'FVX',  # 5-year Treasury yield
        '^TXX': 'TXX'   # 2-year Treasury yield
    }
    
    data = {}
    for symbol, name in symbols.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = fetch_with_retry(ticker)
            if not hist.empty:
                data[name] = {
                    'current': hist['Close'].iloc[-1],
                    'change': hist['Close'].iloc[-1] - hist['Open'].iloc[0],
                    'change_percent': ((hist['Close'].iloc[-1] - hist['Open'].iloc[0]) / hist['Open'].iloc[0]) * 100,
                    'volume': hist['Volume'].iloc[-1],
                    'high': hist['High'].iloc[-1],
                    'low': hist['Low'].iloc[-1]
                }
        except Exception as e:
            app.logger.error(f"Error fetching {name}: {str(e)}")
            data[name] = None
    
    set_cached_data(cache_key, data)
    return data

def background_update():
    """Background thread for real-time updates"""
    global stop_update_thread
    while not stop_update_thread:
        try:
            data = {
                'treasury': get_treasury_data(),
                'market': get_market_data(),
                'timestamp': datetime.now().isoformat()
            }
            socketio.emit('market_update', data)
            WEBSOCKET_MESSAGES.inc()
            time.sleep(5)  # Update every 5 seconds
        except Exception as e:
            app.logger.error(f"Error in background update: {str(e)}")
            time.sleep(1)

@socketio.on('connect')
def handle_connect():
    global update_thread, stop_update_thread
    connected_clients.add(request.sid)
    WEBSOCKET_CONNECTIONS.inc()
    
    # Start background thread if not running
    if update_thread is None or not update_thread.is_alive():
        stop_update_thread = False
        update_thread = threading.Thread(target=background_update)
        update_thread.daemon = True
        update_thread.start()

@socketio.on('disconnect')
def handle_disconnect():
    connected_clients.remove(request.sid)
    if not connected_clients:
        global stop_update_thread
        stop_update_thread = True

@app.route('/api/market-data')
@limiter.limit("30 per minute")
def market_data():
    REQUEST_COUNT.labels(method='GET', endpoint='/api/market-data', status='200').inc()
    with REQUEST_LATENCY.labels(endpoint='/api/market-data').time():
        try:
            treasury_data = get_treasury_data()
            market_data = get_market_data()
            
            response = {
                'treasury': treasury_data,
                'market': market_data,
                'timestamp': datetime.now().isoformat()
            }
            
            return jsonify(response)
        except Exception as e:
            app.logger.error(f"Error in market_data endpoint: {str(e)}")
            REQUEST_COUNT.labels(method='GET', endpoint='/api/market-data', status='500').inc()
            return jsonify({
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }), 500

@app.route('/api/health')
@limiter.limit("60 per minute")
def health_check():
    REQUEST_COUNT.labels(method='GET', endpoint='/api/health', status='200').inc()
    with REQUEST_LATENCY.labels(endpoint='/api/health').time():
        try:
            # Check Redis connection
            redis_status = redis_client.ping()
            
            # Check yfinance connection
            test_ticker = yf.Ticker('^GSPC')
            yf_status = not test_ticker.history(period='1d').empty
            
            return jsonify({
                'status': 'healthy',
                'redis': 'connected' if redis_status else 'disconnected',
                'yfinance': 'connected' if yf_status else 'disconnected',
                'websocket_clients': len(connected_clients),
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            app.logger.error(f"Error in health check: {str(e)}")
            REQUEST_COUNT.labels(method='GET', endpoint='/api/health', status='500').inc()
            return jsonify({
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }), 500

@app.route('/metrics')
def metrics():
    return prometheus_client.generate_latest()

if __name__ == '__main__':
    # Start Prometheus metrics server
    prometheus_client.start_http_server(8000)
    
    # Run Flask app with SocketIO
    port = int(os.getenv('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True) 