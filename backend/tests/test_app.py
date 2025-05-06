import pytest
from app import app, socketio
import json
from unittest.mock import patch, MagicMock
import pandas as pd

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def mock_yfinance():
    with patch('yfinance.Ticker') as mock:
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame({
            'Close': [100.0],
            'Open': [99.0],
            'Volume': [1000000],
            'High': [101.0],
            'Low': [98.0]
        })
        mock.return_value = mock_ticker
        yield mock

def test_health_check(client):
    response = client.get('/api/health')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'status' in data
    assert 'timestamp' in data

def test_market_data(client, mock_yfinance):
    response = client.get('/api/market-data')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'treasury' in data
    assert 'market' in data
    assert 'timestamp' in data

def test_rate_limiting(client):
    # Make multiple requests to test rate limiting
    for _ in range(31):  # Should be limited at 30 per minute
        client.get('/api/market-data')
    
    response = client.get('/api/market-data')
    assert response.status_code == 429  # Too Many Requests

def test_websocket_connection():
    client = socketio.test_client(app)
    assert client.is_connected()
    
    # Test receiving market updates
    received = client.get_received()
    assert len(received) > 0
    assert received[0]['name'] == 'market_update'
    
    client.disconnect()
    assert not client.is_connected()

def test_cache_mechanism(client, mock_yfinance):
    # First request should hit the API
    response1 = client.get('/api/market-data')
    assert response1.status_code == 200
    
    # Second request should use cache
    response2 = client.get('/api/market-data')
    assert response2.status_code == 200
    
    # Verify the data is the same
    assert response1.data == response2.data

def test_error_handling(client):
    with patch('yfinance.Ticker', side_effect=Exception('API Error')):
        response = client.get('/api/market-data')
        assert response.status_code == 500
        data = json.loads(response.data)
        assert 'error' in data

def test_metrics_endpoint(client):
    response = client.get('/metrics')
    assert response.status_code == 200
    assert 'http_requests_total' in response.data.decode()
    assert 'http_request_duration_seconds' in response.data.decode() 