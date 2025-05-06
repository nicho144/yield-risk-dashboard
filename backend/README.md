# Yield Risk Dashboard Backend

This is the backend service for the Yield Risk Dashboard that provides market data using yfinance as a fallback data source.

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the server:
```bash
python app.py
```

The server will start on http://localhost:5000

## API Endpoints

- `/api/market-data`: Get current market data including Treasury yields and market indicators
- `/api/health`: Health check endpoint

## Data Sources

The backend uses yfinance to fetch:
- Treasury yields (2Y, 5Y, 10Y, 30Y, 13W)
- Market indicators (VIX, SPY, Gold, DXY)

## Error Handling

The backend includes comprehensive error handling:
- Graceful fallback for failed data fetches
- Detailed error messages
- Health check endpoint for monitoring

## Development

To modify the data sources or add new endpoints:
1. Edit `app.py`
2. Add new dependencies to `requirements.txt`
3. Restart the server 